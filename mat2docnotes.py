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

import sys,os,os.path,time,shutil
import argparse

# ------------------ read the configuration files ------------------------

# --- Exact sames function as in mat2doc.py, included verbatim to not
# --- depend on modules 
def findMat2docDir(searchdir):
    head=os.path.abspath(os.path.expanduser(searchdir))
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
                print "Not found"
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
            print 'Skipping note',note,'config file missing'
            continue

        notes_found.append(note)

        f=file(conffilename,'r')
        buf=f.readlines()
        f.close()
    
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
        notedict['bibentry']=os.path.exists(notesdir+note+'/bibentry')

        # Look for poster
        notedict['poster']=os.path.exists(notesdir+note+'/poster.pdf')

        # Look for slides
        notedict['slides']=os.path.exists(notesdir+note+'/slides.pdf')

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
    f=file(authorfile)
    buf = f.readlines()
    f.close

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

def createindexpage(noteprefix,notesdir,allnotes,keys,filename):

    obuf=[]

    # Open table, and append header and first horizontal line
    obuf.append('<table cellpadding=5><tr valign=top><td>')   
    obuf.append('<tr valign="top" align="left"><th><a href="index.php">No.</a></th><th><a href="index_author.php">Name</a></th><th><a href="index_year.php">Year</a></th><th><a href="index_type.php">Type</a></th></tr>')
    obuf.append('<tr><td colspan=4><hr /></td></tr>')

    for note in keys:
        notedict = allnotes[note]

        obuf.append('<tr valign="top"><td>')
        obuf.append(note+'</td><td>')
        obuf.append('<notes_title><a href="'+noteprefix+note+'.pdf">'+notedict['title']+'</a></notes_title><br>')
        
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

        #obuf.append('<a href="'+noteprefix+note+'.pdf">ltfatnote'+note+'.pdf</a>')
        #obuf.append('<a href="'+noteprefix+note+'.pdf">Download</a>')


        if notedict['poster']:
            obuf.append('<notes_third>Download <a href="'+noteprefix+note+'_poster.pdf">poster</a></notes_third><br>')

        if notedict['slides']:
            obuf.append('<notes_third>Download <a href="'+noteprefix+note+'_slides.pdf">slides</a></notes_third><br>')

        if notedict['bibentry']:
            obuf.append('<notes_third><a href="'+noteprefix+note+'.bib">Cite this paper</a></notes_third><br>')

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
        
    f=file(filename,'w')
    for line in obuf:
        f.write(line+'\n')

    f.close()
  

def printnoteshtml(noteprefix,notesdir,notehtml):

    # Parse the authors file in the mat2doc directory
    authdict = parseauthors(os.path.join(notesdir,'mat2doc/authors'))

    # Get information from all the 'config' files
    allnotesdict=parseconfigfiles(noteprefix,notesdir,authdict)
    notes=allnotesdict.keys()

    # Clear the target directory
    rmrf(notehtml)

    #keys=getcurrentnotes(allnotesdict)
    keys=allnotesdict.keys()
    keys.sort()

    createindexpage(noteprefix,notesdir,allnotesdict,keys,os.path.join(notehtml,'by_number.php'))
    
    keys.sort(key=lambda x: allnotesdict[x]['year'])

    createindexpage(noteprefix,notesdir,allnotesdict,keys,os.path.join(notehtml,'by_year.php'))

    keys.sort()
    keys.sort(key=lambda x: allnotesdict[x]['type'])

    createindexpage(noteprefix,notesdir,allnotesdict,keys,os.path.join(notehtml,'by_type.php'))

    keys.sort()
    keys.sort(key=lambda x: allnotesdict[x]['author'][0]['name'].split(' ')[:-1])

    createindexpage(noteprefix,notesdir,allnotesdict,keys,os.path.join(notehtml,'by_author.php'))

    for note in notes:                
        notename=noteprefix+note
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




def do_the_stuff(projectdir,confdir,todo,args):

    confdir=os.path.join(projectdir,'mat2doc')

    conf=ConfContainer()

    # Global
    conf.g=ConfType(confdir)
    
    # Sanitize the output directory for safety
    noteshtml=os.path.join(os.path.abspath(os.path.expanduser(conf.g.outputdir)),conf.g.prefix+'-html')

    if 'make' in todo:
        notes=getnotenumbers(projectdir)
        notes = filter(lambda x: (os.path.exists(os.path.join(projectdir,x,'Makefile'))), notes)

        for notenumber in notes:
            print 'Trying to make '+conf.g.prefix+notenumber
            os.system('cd '+os.path.join(projectdir,notenumber)+'; make')

    if 'clean' in todo:
        notes=getnotenumbers(projectdir)

        notes = filter(lambda x: (os.path.exists(os.path.join(projectdir,x,'Makefile'))), notes)

        for notenumber in notes:
            os.system('cd '+os.path.join(projectdir,notenumber)+'; make texclean')

    if 'html' in todo:
        printnoteshtml(conf.g.prefix,projectdir,noteshtml)

        # Add a final / to the path, otherwise rsync upload incorrectly
        if noteshtml[-1]!=os.sep:
            noteshtml=noteshtml+os.sep
        print noteshtml
        os.system('rsync -av '+noteshtml+' '+conf.g.hostname+':'+conf.g.hostdir);


# ------------------ Run the program from the command line -------------

# Parse the command line options
parser = argparse.ArgumentParser(description='The mat2doc notes generator.')
parser.add_argument('filename', help='File or directory to process', default='')

parser.add_argument('target', choices=['make','html','clean'],
                    help='Output target')

parser.add_argument('-q', '--quiet',
                  action="store_false", dest='verbose', default=True,
                  help="don't print status messages to stdout")

parser.add_argument('--upload',
                  action="store_true", default=False,
                  help="Run the upload script of the target")

args = parser.parse_args()

# Locate the mat2doc configuration directory
projectname,projectdir,confdir=findMat2docDir(args.filename)

do_the_stuff(projectdir,confdir,args.target,args)







