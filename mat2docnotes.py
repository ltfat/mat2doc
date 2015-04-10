#!/usr/bin/python

# Copyright (C) 2010-2013 Peter L. Soendergaard <soender@users.sourceforge.net>.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# Global config file
#    Mandatory:
#       prefix 
#       outputdir -- output directory for all targets
#                    target directory name is [prefix]-[target]
#
# Target config file
#    Mandatory:
#       hostname  -- server address
#       hostdir   -- path on the server
#
#       hostname and hostdir are only used in the final rsync command        
#
#    Optional:
#       template  -- path to a template to be used 
#
# Note config file
#    Mandatory:
#       type [documentation,article,poster]
#       title The LTFAT Notes series
#       author jv ps
#       year current or number
#    Optional:
#       URL [URL] # use external link instead of pdf
#       web [www|auto] #use www subdir as a webpage for the paper, auto will generate a
#                       generic page with link to the archive
#       archive toarchive # pack contents of toarchive subdir and include it in www 


from __future__ import print_function
import sys,os,os.path,time,shutil,distutils.core
import argparse
import zipfile
import zlib




# Target types
targettypes = ['html','php']

# ------------------ read the configuration files ------------------------

# --- Exact sames function as in mat2doc.py, included verbatim to not
# --- depend on modules 
def findMat2docDir(searchdir):
    head=os.path.abspath(os.path.expanduser(searchdir))

    if not os.path.exists(head):
        print('{} does not exist.'.format(head));
        sys.exit(-1);

    if not os.path.isdir(head):
        (head,tail)=os.path.split(head)

    while 1:
        s=os.path.join(head,'mat2doc')
        if os.path.isdir(s):
            # Found it
            break
        else:
            (newhead,tail)=os.path.split(head)
            if newhead==head:
                print("Not found")
                sys.exit()
            else:
                head=newhead


    # Absolute path to the configuration directory
    confdir=s

    # Absolute path to the project directory
    projectdir=os.path.dirname(confdir)

    # Name of the project (the directory name)
    projectname=os.path.basename(projectdir)

    return (projectname,projectdir,confdir)


# Empty type to hold a global and a local configuration object
class ConfContainer:
    pass

# This is the base class for deriving all configuration objects.
class ConfType:

    includeoutput=True
    def __init__(self,confdir):
        self.confdir=confdir

        s=os.path.join(self.confdir,'conf.py')

        if os.path.exists(s):
            newlocals=locals()

            execfile(s,globals(),newlocals)

            # Update the object with the dictionary of keys read from
            # the configuration file
            for k, v in newlocals.items():
                setattr(self, k, v)        

        s=os.path.join(self.confdir,'confshadow.py')

        if os.path.exists(s):
            newlocals=locals()

            execfile(s,globals(),newlocals)

            # Update the object with the dictionary of keys read from
            # the configuration file
            for k, v in newlocals.items():
                setattr(self, k, v)        

# rm -Rf
# Does not remove the directory itself
def rmrf(s):
    for root, dirs, files in os.walk(s, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))

# ---------- end of verbatim input --------------------------------


class NotesError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


def getnotenumbers(notesdir):

    allnotes=os.listdir(notesdir)
    allnotes = filter(lambda x: (os.path.isdir(os.path.join(notesdir,x)) and (x[0].isdigit())),allnotes)

    return allnotes


def parseconfigfiles(noteprefix,notesdir,authdict):

    notes=getnotenumbers(notesdir)

    # Like notes, but cleaned of notes without a config file
    notes_found=[]

    allnotesdict={}

    for note in notes:

        notedict={}

        conffilename=os.path.join(notesdir,note,'config')
        if not os.path.exists(conffilename):
            print('Skipping note',note,'config file missing')
            continue

        notes_found.append(note)

        with open(conffilename,'r') as f: buf = f.readlines()

        # Initialize notedict with the information from the config file
        for line in buf:
            s=line.split(' ')
            # Join add a newline at the end, remove this when joining
            notedict[s[0]]=' '.join(s[1:])[:-1]

        # If year is 'current', update the year with the year of the .pdf file
        if notedict['year']=='current':
            modtime=os.path.getmtime(os.path.join(notesdir,note,noteprefix+note+'.pdf'))
            year=time.localtime(modtime)[0]
            notedict['year']=str(year)

        # Expand the authors
        authlist=[]
        for author in notedict['author'].split():
            if not authdict.has_key(author):
                raise NotesError('Note %s: Author %s not found in dict.' % (note, author))
            authlist.append(authdict[author])

        notedict['author']=authlist

        # Look for bibtex entry
        notedict['bibentry']=os.path.exists(os.path.join(notesdir,note,'bibentry'))

        # Look for poster
        notedict['poster']=os.path.exists(os.path.join(notesdir,note,'poster.pdf'))

        # Look for slides
        notedict['slides']=os.path.exists(os.path.join(notesdir,note,'slides.pdf'))

        # Generate list of obsoleted notes
        if 'obsoletes' in notedict:
            notedict['obsoletes']=notedict['obsoletes'].split(' ')
        else:
            notedict['obsoletes']=[]

        # Create empty list
        notedict['obsoletedby']=[]
        allnotesdict[note]=notedict

    # Reverse-index the obsoletes field
    for note in notes_found:
        for obs in allnotesdict[note]['obsoletes']:
            allnotesdict[obs]['obsoletedby'].append(note)

    return allnotesdict

# Return the number of the current notes, given a dictionary of all
# notes, as returned by parseconfigfiles
def getcurrentnotes(allnotesdict):
    allnotes=allnotesdict.keys()
    currentnotes=set(allnotes)

    for note in allnotes:
        currentnotes=currentnotes.difference(set(allnotesdict[note]['obsoletes']))

    return list(currentnotes)


def parseauthors(authorfile):
    with open(authorfile,'r') as f: buf = f.readlines()

    authdict={}
    for line in buf:
        fields = line.split(',')
        key  = fields[0].strip()
        name = fields[1].strip()
        if len(fields)>2:
            email = fields[2].strip()
        else:
            email=''
        if len(fields)>3:
            homepage = fields[3].strip()
        else:
            homepage=''

        authdict[key]={}
        authdict[key]['name']=name
        authdict[key]['email']=email
        authdict[key]['homepage']=homepage

    return authdict

def createindexpage(noteprefix,notesdir,allnotes,keys,filename,targettype=''):

    obuf=[]

    # Open table, and append header and first horizontal line
    obuf.append('<table cellpadding=5><tr valign=top><td>')   
    obuf.append('<tr valign="top" align="left"><th><a '
            'href=".">No.</a></th><th><a '
            'href="index_author.'+targettype+'">Name</a></th><th><a '
            'href="index_year.'+targettype+'">Year</a></th><th><a '
            'href="index_type.'+targettype+'">Type</a></th></tr>')

    obuf.append('<tr><td colspan=4><hr /></td></tr>')

    for note in keys:
        notedict = allnotes[note]

        obuf.append('<tr valign="top"><td>')
        obuf.append(note+'</td><td>')

        if 'URL' not in notedict:
            obuf.append('<notes_title><a href="'+noteprefix+note+'.pdf">'+notedict['title']+'</a></notes_title><br>')
        else:
            obuf.append('<notes_title><a href="'+notedict['URL']+'">'+notedict['title']+'</a></notes_title><br>') 

        # Print the author line
        first_author=1;
        s='<notes_author>'
        for author in notedict['author']:
            if first_author:
                first_author=0
            else:
                #s=s+' and '
                s=s+', '
            if len(author['homepage'])==0:
                s=s+author['name']
            else:
                s=s+'<a href="'+author['homepage']+'">'+author['name']+'</a>'
        obuf.append(s+'</notes_author><br>')

        if notedict['poster']:
            obuf.append('<notes_third>Download <a href="'+noteprefix+note+'_poster.pdf">poster</a></notes_third><br>')

        if notedict['slides']:
            obuf.append('<notes_third>Download <a href="'+noteprefix+note+'_slides.pdf">slides</a></notes_third><br>')

        if notedict['bibentry']:
            obuf.append('<notes_third><a href="'+noteprefix+note+'.bib">Cite this paper</a></notes_third><br>')

        if 'web' in notedict:
            obuf.append('<notes_third><a href="'+note+'">Webpage</a></notes_third><br>')

        if len(notedict['obsoletedby'])>0:
            obuf.append('<notes_third>This note has been made obsolete by ')
            for obs in notedict['obsoletedby']:
                obuf.append(obs+' ')
            obuf.append('</notes_third>')

        obuf.append('</td><td>')
        obuf.append(notedict['year'])
        obuf.append('</td><td>')
        obuf.append(notedict['type']+'</tr>')


        # Horizontal line
        obuf.append('<tr><td colspan=4><hr /></td></tr>')

    obuf.append('</table>')

    # Write obuf to filename
    with open(filename,'w') as f: f.writelines(obuf)


def printnoteshtml(noteprefix,notesdir,notehtml,targettype,t):

    # Parse the authors file in the mat2doc directory
    authdict = parseauthors(os.path.join(notesdir,'mat2doc/authors'))

    # Get information from all the note 'config' files
    allnotesdict=parseconfigfiles(noteprefix,notesdir,authdict)

    notes=allnotesdict.keys()

    if not os.path.exists(notehtml):
        print('Creating directory ' + notehtml)
        os.makedirs(notehtml)

    # Clear the target directory
    rmrf(notehtml)

    #keys=getcurrentnotes(allnotesdict)
    keys=allnotesdict.keys()
    keys.sort()

    # Put the newest papers first
    keys.reverse()

    createindexpage(noteprefix,notesdir,allnotesdict,keys,os.path.join(notehtml,'by_number.'+targettype),targettype)

    keys.sort(key=lambda x: allnotesdict[x]['year'])

    createindexpage(noteprefix,notesdir,allnotesdict,keys,os.path.join(notehtml,'by_year.'+targettype),targettype)

    keys.sort()
    keys.sort(key=lambda x: allnotesdict[x]['type'])

    createindexpage(noteprefix,notesdir,allnotesdict,keys,os.path.join(notehtml,'by_type.'+targettype),targettype)

    keys.sort()
    keys.sort(key=lambda x: allnotesdict[x]['author'][0]['name'].split(' ')[:-1])

    createindexpage(noteprefix,notesdir,allnotesdict,keys,os.path.join(notehtml,'by_author.'+targettype),targettype)


    # The following loop takes one note at a time
    for note in notes:
        notename=noteprefix+note


        if 'URL' not in allnotesdict[note]:
            shutil.copy2(os.path.join(notesdir,note,notename+'.pdf'),
                    os.path.join(notehtml,notename+'.pdf'))

        if allnotesdict[note]['bibentry']:
            shutil.copy2(os.path.join(notesdir,note,'bibentry'),
                    os.path.join(notehtml,notename+'.bib'))

        if allnotesdict[note]['poster']:
            shutil.copy2(os.path.join(notesdir,note,+'poster.pdf'),
                    os.path.join(notehtml,notename+'_poster.pdf'))

        if allnotesdict[note]['slides']:
            shutil.copy2(os.path.join(notesdir,note,'slides.pdf'),
                    os.path.join(notehtml,notename+'_slides.pdf'))

        if 'web' in allnotesdict[note]:
            webdirpath = os.path.join(notesdir,note,allnotesdict[note]['web'])
            targetwebdirpath = os.path.join(notehtml,note)

            if not os.path.exists(webdirpath):
                print('    Directory '+webdirpath+' does not exist.')
            else:
                webdirlist = os.listdir(webdirpath)

                othertargettypes = list(targettypes)
                othertargettypes.remove(targettype)
                ignorefiles = [f for f in webdirlist
                               if any(f.endswith(suffix) for suffix in othertargettypes)]

                if not 'index.'+targettype in webdirlist:
                    # If there is no index file, search for include_ files
                    incfiles = filter(lambda f: f.startswith('include_'), webdirlist)
                    inccontentfile = os.path.join(webdirpath,'include_content.html')
                    ignorefiles.extend(incfiles)

                othertargettypes = list(targettypes)
                othertargettypes.remove(targettype)
                shutil.copytree(webdirpath,targetwebdirpath,
                        ignore=lambda d, files: [f for f in files if f in ignorefiles])

                if not 'index.'+targettype in webdirlist:
                    if not 'include_content.html' in incfiles:
                        print('{} not found.'.format(inccontentfile))
                        sys.exit(-1)

                    # Try to read template from the conf object and fallback
                    # to target/template.hml if .template is not defined.
                    templatepath = getattr(t,'template',os.path.join(t.confdir,'template.'+targettype))

                    if not os.path.exists(templatepath):
                        print('{} not found.'.format(templatepath))
                        sys.exit(-1)

                    with open(inccontentfile,'r') as inccont:
                        include_content = inccont.read()

                    with open(templatepath,'r') as tt:
                        authornames = [f['name'] for f in allnotesdict[note]['author']]
                        repldict = {'TITLE'   : noteprefix+note,
                                    'NAME'    : allnotesdict[note]['title'],
                                    'CITATION': ', '.join(authornames) + ': ' + allnotesdict[note]['title'],
                                    'CONTENT' : include_content
                                }
                        template = tt.read();
                        for kv, expansion in repldict.items():
                            template = template.replace('{'+kv+'}',expansion)

                        # The following crashes with KeyError if any of the keywords 
                        # is not found in the template
                        #template = tt.read().format(TITLE= noteprefix+note,
                        #                           NAME= allnotesdict[note]['title'],
                        #                           CITATION=', '.join(authornames) + ': '
                        #                           + allnotesdict[note]os.path.join(notehtml,note,noteprefix+note+'.zip')['title'],
                        #                           CONTENT=include_content)

                    with open(os.path.join(targetwebdirpath,'index.'+targettype),'w') as tt:
                        tt.write(template)


        if 'archive' in allnotesdict[note]:
            archivepath = os.path.join(notesdir,note,allnotesdict[note]['archive'])
            targetarchivepath = os.path.join(notehtml,note,noteprefix+note+'.zip') 

            if not os.path.exists(archivepath):
                print('    Directory '+archivepath+' does not exist.')
            else:
                # pack contents of archivepath directory to 
                #packcommand = 'zip -jr ' + os.path.join(notehtml,note,noteprefix+note+'.zip') + ' ' + archivepath
                #print(packcommand)
                #os.system(packcommand)
                with zipfile.ZipFile(targetarchivepath, mode='w') as zf:
                    for f in os.listdir(archivepath):
                        zf.write(os.path.join(archivepath,f),
                                compress_type=zipfile.ZIP_DEFLATED,
                                arcname=f)

def do_the_stuff(projectdir,args):
    # This directory exists for sure
    confdir = os.path.join(projectdir,'mat2doc')
    target = args.target

    # Target type from target
    targettype = filter(lambda prefix:
            target.startswith(prefix),targettypes+['make','clean'])[0]

    # Just empty object
    conf=ConfContainer()

    # Read global config
    conf.g=ConfType(confdir)

    if targettype in targettypes:
        # Read target specific config if target is not 'make' or 'clean'
        conf.t=ConfType(os.path.join(confdir,target))


    if 'make' in targettype:
        notes=getnotenumbers(projectdir)
        notes = filter(lambda x: (os.path.exists(os.path.join(projectdir,x,'Makefile'))), notes)

        for notenumber in notes:
            print('Trying to make '+conf.g.prefix+notenumber)
            os.system('cd '+os.path.join(projectdir,notenumber)+'; make')

    if 'clean' in targettype:
        notes=getnotenumbers(projectdir)

        notes = filter(lambda x: (os.path.exists(os.path.join(projectdir,x,'Makefile'))), notes)

        for notenumber in notes:
            os.system('cd '+os.path.join(projectdir,notenumber)+'; make texclean')


    if targettype in targettypes:
        # Sanitize the output directory for safety
        noteshtml=os.path.join(os.path.abspath(os.path.expanduser(conf.g.outputdir)),conf.g.prefix+'-'+target)

        printnoteshtml(conf.g.prefix,projectdir,noteshtml,targettype,conf.t)

        # Add a final / to the path, otherwise rsync upload incorrectly
        if noteshtml[-1]!=os.sep: noteshtml=noteshtml+os.sep
        hostname = conf.t.hostname.strip()+':' if conf.t.hostname.strip() else '';
        command= 'rsync -av '+noteshtml+' '+hostname+conf.g.hostdir
        print('Run:\n    {}\nTo upload.'.format(command));

def main():
    # Search for targets first
    if(len(sys.argv)<2):
        print('Not enough input arguments.')
        sys.exit(-1);

    # Locate the mat2doc configuration directory
    projectname,projectdir,confdir=findMat2docDir(sys.argv[1])

    # Gather ponential targets
    targets = [x for x in os.listdir(confdir)
                        if os.path.isdir(os.path.join(confdir,x))
                        and 'conf.py' in os.listdir(os.path.join(confdir,x))]

    print(', '.join(targets))

    # Filter out those which are not recognized as valid targets according to target types 
    wrongtargets = filter(lambda x: not any(x.startswith(prefix) for prefix in targettypes),targets)

    if wrongtargets:
        print('The following directories are not valid targets: {}\n'
              'They do not start with {}'.format(', '.join(wrongtargets),
              ' or '.join(targettypes)));
        sys.exit(-1)

    if not targets:
        print("No tagets were found in " + confdir + "\n"
              "A targer is a subdirectory of " + confdir + " containing conf.py")
        sys.exit(-1)

    # Parse the command line options
    parser = argparse.ArgumentParser(description='The mat2doc notes generator.')
    parser.add_argument('filename', help='File or directory to process', default='')

    targets.extend(['make','clean']);
    parser.add_argument('target', choices=targets,
            help='Output target')

    parser.add_argument('-q', '--quiet',
            action="store_false", dest='verbose', default=True,
            help="don't print status messages to stdout")

    parser.add_argument('--upload',
            action="store_true", default=False,
            help="Run the upload script of the target")

    args = parser.parse_args()

    do_the_stuff(projectdir,args)

# ------------------ Run the program from the command line -------------
if __name__ == '__main__':
    main()







