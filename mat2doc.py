#!/usr/bin/python

import sys,os,os.path,string,re,codecs,shutil
import argparse
from subprocess import *

from pygments import highlight
from pygments.lexers import MatlabLexer
from pygments.formatters import HtmlFormatter


import docutils.core

class Mat2docError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def myexec(s):
    print 'Executing: '+s

    p=Popen(s,shell=True,stdout=PIPE,stderr=PIPE,close_fds=True)
    sts = os.waitpid(p.pid, 0)
    buf=p.stdout.readlines()
    if len(buf)>0:
        print '   STDOUT:'
        for line in buf:
            print line

    buf=p.stderr.readlines()
    if len(buf)>0:
        print '   STDERR:'
        for line in buf:
            print line

# ----------------- extra path/dir manipulations ---------------------------

# Create directory, and do not produce an error if it already exists
def safe_mkdir(dir):
    try:
        os.makedirs(dir)
    except OSError:
        pass

# Remove directory without an error if it does not exist
def safe_rmdir(dir):
    try:
        os.rmdir(dir)
    except OSError:
        pass

# rm -Rf
# Does not remove the directory itself
def rmrf(s):
    for root, dirs, files in os.walk(s, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))

# Find all the Contents.m files
def find_indexfiles(projectdir):
    indexfiles=[]
    for root, dirs, files in os.walk(projectdir, topdown=False):
        for name in files:
            if name=='Contents.m':
                s=os.path.relpath(os.path.join(root, name),projectdir)
                # strip .m
                s=s[:-2]
                indexfiles.append(s)

    return indexfiles

def do_rebuild_file(source,dest,mode):
    if mode=='rebuild':
        return True

    if not os.path.exists(dest):
        if mode=='cached':
            print 'Error: Cached version of '+dest+ ' does not exist'
            sys.exit()
        
        print dest +' missing'

        return True
            
    is_newer = os.path.getmtime(source)>os.path.getmtime(dest)

    if mode=='auto':
        return is_newer

    if mode=='cached':
        return False

# ------------------ read the configuration files ------------------------

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

# ------------------ version control export routines ----------------------

def gitAutoStage(repo):
    # This command explicitly swicthes working directory to the
    # repository, otherwise git will think that the directory is
    # empty, and stage all files for removal.
    s = 'cd '+repo+'; git add -u'
    os.system(s)

def gitStageExport(repo,outputtargetdir):
    rmrf(outputtargetdir)
    s=os.path.join(repo,'.git')
    os.system('git --git-dir='+s+' checkout-index --prefix='+outputtargetdir+os.sep+' -a')

def svnExport(repo,outputtargetdir):
    rmrf(outputtargetdir)
    os.system('svn export --force '+repo+' '+outputtargetdir)

def detectVersionControl(projectdir):
    if os.path.exists(os.path.join(projectdir,'.svn')):
        return 'svn'
    if os.path.exists(os.path.join(projectdir,'.git')):
        return 'git'
    return 'none'

def matExport(projectdir,outputtargetdir):
    vctype=detectVersionControl(projectdir)
    if vctype=='git':
        gitAutoStage(projectdir)
        gitStageExport(projectdir,outputtargetdir)

    if vctype=='svn':
        svnExport(projectdir,outputtargetdir)

    # Remove the mat2doc directory that just got copied/exported
    s=os.path.join(outputtargetdir,'mat2doc')
    rmrf(s)
    os.rmdir(s)

# ------------------ safe reading and writing of text files ---------------
def saferead(filename):
    f=codecs.open(filename,'r',encoding="utf-8")
    try:
        buf=unicode(f.read())
    except UnicodeDecodeError as s:
        raise Mat2docError('File %s in not encoded an unicode, please convert it to Unicode.' % filename)
    
    f.close()

    return buf

def safewrite(filename,buf):

    #f.write(unicode(line+'\n','latin-1'))
            
    # Extra characters seems to be produced when writing the empty
    # string using the utf-8 encoding
    if buf=='':
        f=file(filename,'w')
    else:
        f=codecs.open(filename,'w',encoding="utf-8")

    f.write(buf)
    f.close()

def safereadlines(filename):
    buf=saferead(filename)
    linebuf=buf.split('\n')

    # String-splitting an empty string generates an array with a single element
    if linebuf==['']:
        linebuf=[]

    return linebuf
    
def safewritelines(filename,buf):
        
    s=u'\n'.join(buf)+u'\n'
    safewrite(filename,s)

# --------- Calling reStructuredText ---------------------------------

def call_rst(instring,outtype):
    # NOTE TO SELF: The name of the commandline option is
    # math-output, but the option set here math_output. All
    # options behave similarly.

    # Substitutions for making restructuredtext easier
    instring = re.sub(r"\\\\",r"\\\\\\\\",instring)

    if outtype=='php' or outtype=='html':
        args = {
            'math_output' : 'MathJax',
            'initial_header_level' : 2
            }
    else:
        args = {
            'initial_header_level' : 3,
            }
    
    # Look up the correct writer name
    writernames={}
    writernames['php']='html'
    writernames['html']='html'
    writernames['tex']='latex2e'

    #instring+='CLOSETHEDAMMTHINGIE.\n'

    # Call rst2html or similar
    buf=docutils.core.publish_string(instring,writer_name=writernames[outtype],
                                     settings=None, settings_overrides=args)
    return unicode(buf,'utf-8')

def call_bibtex2html(reflist,conf):
    outname=os.path.join(conf.g.tmpdir,'reflist')

    safewritelines(outname,reflist)

    s='bibtex2html --warn-error --no-abstract --no-keys --no-keywords --nodoc --nobibsource --no-header --citefile '+outname+' -s '+conf.t.bibstyle+' --output '+outname+' '+conf.g.bibfile+'.bib'

    try:
        output=check_output(s,shell=True,stderr=PIPE)
    except CalledProcessError as s:
        print s.output
        raise s
        

    if 'Warning' in output:
        print output
        print 'STOPPING MAT2DOC: bibtex key missing in bibfile'
        sys.exit()

    buf=saferead(outname+'.html')

    # Strip the annoying footer
    ii=buf.find('<hr>')
    buf=buf[:ii]+'\n'

    return buf.split('\n')


def rst_postprocess(instr,outtype):


    if outtype=='tex':
        instr = re.sub("\\\\section\*{","\\subsubsection*{",instr)
        instr = re.sub("\\\\phantomsection","",instr)
        instr = re.sub("\\\\addcontentsline.*\n","",instr)
        instr = re.sub("\\\\newcounter{listcnt0}","\\\setcounter{listcnt0}{0}",instr)
        instr = re.sub("\\\\label{.*?}%\n","",instr)


    buf = instr.split('\n')

    # php specific transformations
    if outtype=='php' or outtype=='html':
        # Transform <em> into <var>
        #buf=  re.sub('<em>','<var>',buf)
        #buf=  re.sub('</em>','</var>',buf)
        
        # Adjust the indexing to remove the <body> and <div document> tags.
        buf=buf[buf.index('<body>')+2:buf.index('</body>')-1]

    if outtype=='tex':
        
        # Adjust the indexing to only include the relevant parts
        buf=buf[buf.index('\\maketitle')+1:buf.index('\\end{document}')]

    return buf

# ----------  Protection routines ---------------------------

def protect_tex(line):
    # Protect characters so that they are not treated as special
    # commands for TeX
    
    line=line.replace('[','{[}')
    line=line.replace(']','{]}')
    #line=line.replace('_','\_')
    line=line.replace('_','\\textunderscore{}')
    line=line.replace('%','\%')
    line=line.replace('*','{*}')
    line=line.replace('^','\textasciicircum{}')
    
    return line


def protect_html(line):
    # Protect characters so that they are not treated as special
    # commands for HTML
    
    line=line.replace('<','&lt;')
    line=line.replace('>','&gt;')
    
    return line

# ------------ Configuration and output-producing object structure ---------------

# Empty type to hold a global and a local configuration object
class ConfContainer:
    pass

# This is the base class for deriving all configuration objects.
class ConfType:    
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

class GlobalConf(ConfType):
    def __init__(self,confdir,projectname,projectdir):
        ConfType.__init__(self,confdir)
        
        # Sanitize the output directory for safety
        self.outputdir=os.path.abspath(os.path.expanduser(self.outputdir))

        self.projectname=projectname
        self.projectdir=projectdir
        self.tmpdir=os.path.join(self.outputdir,self.projectname+'-tmp')
        safe_mkdir(self.tmpdir)
        # Empty the tmp directory for safety
        rmrf(self.tmpdir)

        s=os.path.join(self.confdir,'ignore')
        if os.path.exists(s):
            self.ignorelist=safereadlines(s)
        else:
            self.ignorelist=[]    

class TargetConf(ConfType):    
    bibstyle='abbrv'
    otherrefs=[]

    def __init__(self,g):        
        self.confdir=os.path.join(g.confdir,self.basetype)

        ConfType.__init__(self,self.confdir)

        self.codedir=os.path.join(g.outputdir,g.projectname+'-mat')
        self.dir=os.path.join(g.outputdir,g.projectname+'-'+self.basetype)

        self.urlbase=self.urlbase.format(TARGETDIR=self.dir)
        # urlbase must always end in a slash
        if not self.urlbase[-1]=='/':
            self.urlbase+='/'


 # This is the class from which TeX configuration should be derived.
class TexConf(TargetConf):
    basetype='tex'

    # Protect characters so that they are not treated as special
    # commands for TeX
    def protect(self,line):
        line=protect_tex(line)
        
        return line
    
    # Just append the latex-code.
    def displayformula_old(self,buf,obuf,fignum,caller):
        obuf.extend(buf)
        
    # Append a line of references
    def references(self,refbuf,obuf,caller):
        s=self.referenceheader+' '
        for item in refbuf:
            s=s+'\\cite{'+item+'}, '

        # append, and kill the last komma and space
        obuf.append(s[:-2])

    beginurl='\\href{'
    endurl='}'
    urlseparator='}{'

    referenceheader='\n\\textbf{References:}'

# This class serves as the ancestor for PhPConf and HtmlConf, and
# should only be used for that.
class WebConf(TargetConf):
    beginurl='<a href="'
    endurl='</a>'
    urlseparator='">'

    beginboxheader='<b>'
    endboxheader='</b><br>'
 
    referenceheader='<H2>References:</H2>'

    # Use bibtex2html to generate html references
    def references(self,reflist,obuf,caller):
        if len(reflist)==0:
            print '   WARNING: Empty list of references.'
        else:

            buf=call_bibtex2html(reflist,caller.c)

            obuf.append(self.referenceheader)
            obuf.extend(buf)
        

# This is the class from which PHP configurations should be
# derived.
class PhpConf(WebConf):
    basetype='php'

    def structure_as_webpage(self,caller,maincontents,doctype):

        backdir=''
        if len(caller.subdir)>0:
            backdir='../'

        includedir=os.path.join(backdir,caller.c.t.includedir)
        
        # Must end with a slash
        if not includedir[-1]=='/':
            includedir+='/'

        phpvars = caller.print_variables_php()

        maincontents=map(lambda x:x.replace("'","\\'"),maincontents)

        # Opening of the php-file
        obuf=['<?php']

        # php debugging code
        obuf.append("ini_set('display_errors', 'On');")
        obuf.append("error_reporting(E_ALL);")

        obuf.append('$path_include="'+includedir+'";')
        obuf.append('include($path_include."main.php");')
        obuf.append('$doctype='+`doctype`+';')

        obuf.extend(phpvars)
        
        obuf.append("$content = '")
        obuf.extend(maincontents)
        obuf.append("';")

        obuf.append('printpage($title,$keywords,$seealso,$demos,$content,$doctype);')

        # Close PHP
        obuf.append('?>')

        return obuf

    def print_menu(self,parsed):

        obuf=[]
        obuf.append('<?php')
        obuf.append('$menu = array(')

        # Add a unique number to each line to make them different
        # In the code below " is used to delimit python strings
        # and ' is used for the php strings, because we need to include a " into the innermost
        # string
        uniq_no=0
        for line in parsed:
            uniq_no+=1
            if line[0]=="li":
                obuf.append("   'li"+`uniq_no`+"' => '"+"<a href=\""+line[1]+self.fext+"\">"+line[1]+"</a>',")

            if line[0]=="caption":
                obuf.append("   'caption"+`uniq_no`+"' => '"+line[1]+"',")

        obuf.append(");")
        obuf.append("?>")
                    
        return obuf



# This is the class from which Html configurations should be
# derived.
class HtmlConf(WebConf):
    basetype='html'

    def __init__(self,g):
        WebConf.__init__(self,g)
        self.g=g

        # Read the template
        templatefile=os.path.join(self.confdir,'template.'+self.basetype)
        if os.path.exists(templatefile):
            self.template=saferead(templatefile)
        else:
            raise Mat2docError('Template file %s is missing.' % templatefile)

    def structure_as_webpage(self,caller,maincontents,doctype):

        # Generate the basedir link
        basedir=''
        if len(caller.subdir)>0:
            basedir='../'

        # Opening of the html-file
        obuf=[' ']

        # Load the menu from a file, it was previously written there by the ContentsPrinter
        menu=saferead(os.path.join(self.dir,caller.subdir,'contentsmenu'+self.fext))
        
        # Generate see-also
        seealso = caller.print_variables_html()

        # Generate view switcher
        switchview=''
        if doctype==1:
            switchview='<div id="menutitle"><a href="'+caller.fname+'_code'+self.fext+'">View the code</a></div>\n'
        if doctype==2:
            switchview='<div id="menutitle"><a href="'+caller.fname+self.fext+'">View the help</a></div>\n'


        content='\n'.join(maincontents)
        obuf.append(self.template.format(TITLE=caller.title,
                                         BASEDIR=basedir,
                                         CONTENT=content,
                                         SEEALSO=seealso,
                                         SWITCHVIEW=switchview,
                                         KEYWORDS='',
                                         MENU=menu,
                                         AUTHOR=self.g.author,
                                         VERSION=self.g.version,
                                         YEAR=self.g.year
))

        return obuf

    def print_menu(self,parsed):

        obuf=[]

        ul_on=0
        for line in parsed:
            if line[0]=="li":
                if not ul_on:
                    obuf.append('<ul>')
                    ul_on=1

                obuf.append("<li><a href=\""+line[1]+self.fext+"\">"+line[1]+"</a></li>")

            if line[0]=="caption":
                if ul_on:
                    obuf.append('</ul>')
                    ul_on=0
                    
                obuf.append('<div id="menutitle">'+line[1]+'</div>')

        if ul_on:
            obuf.append('</ul>')
            ul_on=0
                    
        return obuf




# This is the class from which Mat configurations should be
# derived.
class MatConf(TargetConf):
    basetype='mat'
    fext='.m'

    def __init__(self,g):
        TargetConf.__init__(self,g)

        # Read the targe-dependant header and footer
        headerfile=os.path.join(self.confdir,'header'+self.fext)

        if os.path.exists(headerfile):
            self.header=saferead(headerfile)
        else:
            self.header=''

        footerfile=os.path.join(self.confdir,'footer.'+self.fext)
        if os.path.exists(footerfile):    
            self.footer=saferead(footerfile)
        else:
            self.footer=''

        self.header=self.header.format(AUTHOR=g.author,
                             VERSION=g.version,
                             YEAR=g.year)

        self.footer=self.footer.format(AUTHOR=g.author,
                             VERSION=g.version,
                             YEAR=g.year)


# -----------------  Object structure for the parser -------------------------


class BasePrinter(object):
    def __init__(self,conf,fname):
        self.c=conf

        # self.fname contains the name of the file
        # self.subdir contains the relative subdir in which the file is placed
        # self.fullname contains both
        self.fullname=fname
        self.subdir,self.fname=os.path.split(fname)

        print 'Parsing ',self.fullname

        # backdir contains a link to the root relative to the path the
        # the file is living in
        backdir=''
        if len(self.subdir)>0:
            backdir='../'

        buf=safereadlines(os.path.join(self.c.g.projectdir,fname+'.m'))

        self.buf_help=[]

        buf.reverse()

        # Find the help section: discard any lines in the beginning
        # not starting with % and stop again as soon as a line not
        # starting with % is encountered
        foundhelp=0
        while len(buf)>0:
            line=buf.pop()
            if len(line)>0 and line[0]=="%":
                foundhelp=1
                self.buf_help.append(line[1:])
            else:
                if foundhelp:
                    break

        self.parse()

        
    def writelines(self,fname,buf):
	# Create directory to hold the file if it does not already
	# exist.
	fullname=os.path.join(self.c.t.dir,fname)
	base,name=os.path.split(fullname)
	if not os.path.exists(base):
	   os.mkdir(base)

        safewritelines(fullname,buf)





class ExecPrinter(BasePrinter):


    def parse(self):

        space=' '
        out={}

        buf=self.buf_help

        buf.reverse()

        line=buf.pop().split()

        out['name']=line[0]

        if out['name'].lower()<>self.fname:
            print '   ERROR: Mis-match between function name and help text name.'
            print '   <'+out['name'].lower()+'> <'+self.fname+'>'
            sys.exit()

        out['description']=space.join(line[1:]).strip()
        
        self.title=out['name']+' - '+out['description']

        if len(out['description'])==0:
            print '   ERROR: Discription on first line is empty.'
            sys.exit()

        if out['description'][-1]=='.':
            print '   ERROR: Description line ends in a full stop.'
            sys.exit()

        out['body']=[]

        header_added=0

        # Counter to keep track of the number of executable blocks in
        # this file, used for numbering the figures correctly
        exec_n=0

        # Add setup code
        out['body'].append('.. default-role:: literal')
        out['body'].append('')

        # Append the reference lookups for this project
        files=os.listdir(self.c.t.confdir)
        files=filter(lambda x: x[:4]=='ref-' and x[-4:]=='.txt',files)
        for filename in files:
            out['body'].append('.. include:: '+os.path.join(self.c.t.confdir,filename))

        out['body'].append('')

        # Add the title
        s=out['name']+' - '+out['description']
        out['body'].append(s)
        out['body'].append('='*len(s))
        
        for ii in range(len(buf)):
            
            if len(buf[ii].strip())>1:
                if not (buf[ii][0:3]=='   '):
                    print '   In function %s: Line does not start with three empty spaces.' % out['name']
                    sys.exit()
                else:
                    buf[ii]=buf[ii][3:]
            

        while len(buf)>0:

            line=buf.pop()

            # This check skips blank lines.
            if 'Usage' in line:
                out['body'].append('Usage')
                out['body'].append('-----')
                out['body'].append('')
                out['body'].append('::')
                out['body'].append('')
                out['body'].append('  '+line[6:].strip())
                line=buf.pop()
                # While the line does not start at zero.
                while not (len(line.strip())>0 and find_indent(line)==0):
                    s=line.strip()
                    if len(s)>0:
                        # When splitting the line, the function name
                        # always appears last, even if there is no "=" on
                        # the line.
                        #
                        # Similarly, then function name is always before "(" or ";"
                        usage_name=s.split('=')[-1].split('(')[0].split(';')[0].strip()
                        if usage_name<>self.fname:
                            print '   ERROR: Mis-match between function name and usage name.'
                            print '   <'+usage_name+'> <'+self.fname+'>'
                            print s
                            sys.exit()

                    
                    out['body'].append('  '+s)
                    line=buf.pop()

            if 'Input parameters' in line:                
                out['body'].append('Input parameters')
                out['body'].append('----------------')
                out['body'].append('')
                line=buf.pop().rstrip()
                while len(line.strip())==0:
                    line=buf.pop().rstrip()
                idl=find_indent(line)
                # While the line does not start at zero.
                while not (len(line.strip())>0 and find_indent(line)==0):       
                    s=find_indent(line)
                    if s>0:
                        line=line[idl:]
                    if s==idl:
                        colpos=line.find(':')
                        firstpart=line[0:colpos]
                        secondpart=' '*(colpos+1)+line[colpos+1:]
                        firstpart=re.sub(',',', --Q=',firstpart)
                        firstpart='--Q='+firstpart
                        #out['body'].append('')
                        out['body'].append(firstpart)
                        out['body'].append(secondpart)
                    else:
                        out['body'].append(line)                        

                    line=buf.pop().rstrip()
                # make sure the environment is closed
                out['body'].append('')

            if 'Output parameters' in line:
                out['body'].append('Output parameters')
                out['body'].append('-----------------')
                out['body'].append('')
                line=buf.pop().rstrip()
                while len(line.strip())==0:
                    line=buf.pop().rstrip()
                idl=find_indent(line)
                # While the line does not start at zero.
                while not (len(line.strip())>0 and find_indent(line)==0):       
                    s=find_indent(line)
                    if s>0:
                        line=line[idl:]
                    if s==idl:
                        colpos=line.find(':')
                        firstpart=line[0:colpos]
                        secondpart=' '*(colpos+1)+line[colpos+1:]
                        firstpart=re.sub(',',', --Q=',firstpart)
                        firstpart='--Q='+firstpart
                        #out['body'].append('')
                        out['body'].append(firstpart)
                        out['body'].append(secondpart)
                    else:
                        out['body'].append(line)                        

                    line=buf.pop().rstrip()
                # make sure the environment is closed
                out['body'].append('')
            
            if ':::' in line:
                exec_n +=1

                out['body'].append(line.replace(':::','::'))

                # kill the following empty lines, until we find the next indented one
                line=buf.pop().rstrip()
                while len(line.strip())==0:
                    line=buf.pop().rstrip()
                idl=find_indent(line)

                codebuf=[]
                # add an empty line after the ::, because it was killed
                out['body'].append('')
                # While the line does not start at zero.
                while not ((len(buf)==0) or (len(line.strip())>0 and find_indent(line)==0)):       
                    codebuf.append(line)

                    out['body'].append(line)
                    line=buf.pop().rstrip()
                    
                # push back the last line, it was one too many.
                if find_indent(line)==0:
                    buf.append(line)

                # make sure the environment is closed
                out['body'].append('')

                outputprefix=os.path.join(self.c.t.dir,self.fullname+'_'+`exec_n`)

                # Execute the code
                (outbuf,nfigs)=execplot(self.c.g.plotengine,codebuf,outputprefix,self.c.t.imagetype,self.c.g.tmpdir,self.c.g.execplot)

                # Append the result, if there is any
                if len(outbuf)>0:
                    out['body'].append('*This code produces the following output*::')
                    out['body'].append('')
                    for outline in outbuf:
                        out['body'].append('  '+outline)
                    out['body'].append('')                

                # Append the plots
                for i in range(nfigs):
                    out['body'].append('.. image:: '+self.fname+'_'+`exec_n`+'_'+`i+1`+'.'+self.c.t.imagetype)
                    if len(self.c.t.widthstr)>0:
                        out['body'].append('   :width: '+self.c.t.widthstr)
                    out['body'].append('')

                continue
      
            if 'See also' in line:
                (dummy,sep,s) = line.partition(':')
                if not(sep==':'):
                    raise Mat2docError('In function %s: See also line must contain a :' % out['name'])
                out['seealso']=map(lambda x:x.strip(',').lower(),s.split())
                while (len(buf)>0) and len(buf[-1][1:].strip())>0:
                    line = buf.pop();
                    out['seealso'].extend(map(lambda x:x.strip(',').lower(),line.split()))

                continue

            if 'Demos' in line:
                (dummy,sep,s) = line.partition(':')
                if not(sep==':'):
                    raise Mat2docError('In function %s: Demos line must contain a :' % out['name'])
                out['demos']=map(lambda x:x.strip(',').lower(),s.split())
                continue

            if 'References:' in line:
                (dummy,sep,s) = line.partition(':')
                out['references']=s.strip().split()
                continue

            if not header_added:
                if line.strip()=='':
                    # Skip any initial blank lines
                    continue

                if not line[0]==' ':
                    # First real line encountered
                    out['body'].append('XXXDescription')
                    out['body'].append('--------------')
                    header_added=1

            out['body'].append(line.rstrip())

        if 0:
            for line in out['body']:
                print line
            sys.exit()


        self.parsed=out

        # Find the variables from parameter and usage lists.
        # self.find_pars()

        # Set the name
        self.name=self.parsed['name'].lower()
        
        # Add a final empty line, to make sure all environments are properly closed.
        out['body'].append('')

        # Read the code from a generated file into a buffer
        s=os.path.join(self.c.t.codedir,self.fullname+'.m')
        if os.path.exists(s):
            self.codebuf=saferead(s)
        else:
            raise Mat2docError("The Matlab code file %s cannot be found. You probably need to run the 'mat' target first." % s)

    def print_code_html(self):
        
        highlightbuf=highlight(self.codebuf, MatlabLexer(), HtmlFormatter())
 
        maincontents=[]
    
        maincontents.append('<h1 class="title">'+self.parsed['name']+' - '+self.parsed['description']+'</h1>')

        maincontents.append('<h2>Program code:</h2>')

        maincontents.extend(highlightbuf.split('\n'))

        return self.c.t.structure_as_webpage(self,maincontents,2)


    def print_body(self,obuf):

        buf=self.parsed['body']

        # Initialize buffer
        buf_to_rst=u''

        for line in buf:
            s=line.strip()
            if s=='':
                buf_to_rst+=u'\n'
                continue

            # Transform list definitions and formulae
            if len(line)>2 and line[2]=="'":
                line=re.sub("  '","--Q",line)
                line=re.sub("',","Q ",line)
                line=re.sub("' ","Q ",line)

            # Substite the correct formula code
            if '$' in line:
                words=line.split('$')
                line=words[0]
                for ii in range((len(words)-1)/2):
                    line+=':math:`'+words[2*ii+1]+'`'+words[2*ii+2]                
            buf_to_rst+=line+u'\n'

        if 0: #self.c.t.basetype=='tex':
            if self.fname=='admm':
                print buf_to_rst
                sys.exit()


        buf=call_rst(buf_to_rst,self.c.t.basetype)

        # Uncomment this to print the raw reStructuredText output
        #print buf
        #sys.exit()

        # Clean up from table transformation

        splitidx=buf.find('XXXDescription')
        firstpart =buf[0:splitidx]
        secondpart=buf[splitidx:]

        if self.c.t.basetype=='php' or self.c.t.basetype=='html':
            firstpart =re.sub("--Q=","",firstpart)
            secondpart=re.sub("--Q","'",secondpart)
            secondpart=re.sub("Q ","',",secondpart)
            secondpart=re.sub("Q<","'<",secondpart)

        if self.c.t.basetype=='tex':
            firstpart =re.sub("-{}-Q=","",firstpart)
            secondpart=re.sub("-{}-Q","'",secondpart)
            secondpart=re.sub("Q ","',",secondpart)
            secondpart=re.sub("Q]","']",secondpart)


        buf = firstpart+secondpart
        buf=  re.sub('XXXDescription','Description',buf)

        if 0: #self.c.t.basetype=='tex':
            if self.fname=='dwilt':
                print buf


        buf = rst_postprocess(buf,self.c.t.basetype)
            
        obuf.extend(buf)        

        # Do references
        if  self.parsed.has_key('references'):
            refbuf=self.parsed['references']
            self.c.t.references(refbuf,obuf,self)

        return

        

    def print_html(self):

        maincontents=[]

        self.print_body(maincontents)

        return self.c.t.structure_as_webpage(self,maincontents,1)


    def print_tex(self,obuf):
        pname=self.c.t.protect(self.parsed['name'])
        pnamel=pname.lower()
        obuf.append('\subsection['+pnamel+']{'+pname+' - '+self.c.t.protect(self.parsed['description'])+'}\label{'+pnamel+'}')
    
        obuf.append('')

        self.print_body(obuf)

        return obuf

    def write_the_file(self):
        if self.c.t.basetype=='php' or self.c.t.basetype=='html':
            self.write_html()            

        if self.c.t.basetype=='tex':
            buf=self.print_tex([])
            self.writelines(self.fullname+self.c.t.fext,buf)
        

    def print_variables_php(self):
        # Convention used in this routine
        #   '  is the string delimiter in Python
        #   "  is the string delimiter in php

        obuf=[]

        # --- Title
        obuf.append('$title = "'+self.title+'";')

        # --- See also
        obuf.append('$seealso = array(')
        for see in self.parsed.get('seealso',[]):
            obuf.append('   "'+see+'" => "'+self.c.t.urlbase+
                        self.c.lookupsubdir[see]+'/'+see+self.c.t.fext+'",')
            
        obuf.append(');')

        
        obuf.append('$demos = array(')
        for see in self.parsed.get('demos',[]):
            obuf.append('   "'+see+'" => "'+self.c.t.urlbase+
                        self.c.lookupsubdir[see]+'/'+see+self.c.t.fext+'",')
            
        obuf.append(');')

        # --- Keywords
        obuf.append('$keywords = "'+self.title+'";')

        
        return obuf

    def print_variables_html(self):
        seealso=''
        seealsolist=self.parsed.get('seealso',[])
        if len(seealsolist)>0:
            seealso+='<div id="menutitle">See also:</div>\n'

            seealso+='<ul>\n'
            for see in seealsolist:
                seealso+='<li><a href="'+os.path.join(self.c.t.urlbase,self.c.lookupsubdir[see],see+self.c.t.fext)+'">'+see+'</a></li>\n'
            seealso+='</ul>\n'

        return seealso

        

class FunPrinter(ExecPrinter):

    def write_html(self):

        html_help_buf=self.print_html()
        self.writelines(self.fullname+self.c.t.fext,html_help_buf)

        html_code_buf=self.print_code_html()
        self.writelines(self.fullname+'_code'+self.c.t.fext,html_code_buf)


class ExamplePrinter(ExecPrinter):

    # Specialized version to fill in figures.    
    def write_html(self):

        # This functions does the following things different than the funnav
        #
        # - Executes the script and saves the images
        #
        # - Appends the output to the end.
        #
        # - does a search and replace to put in the correct filenames
        #   for the .. figure:: tags

        outputprefix=os.path.join(self.c.t.dir,self.fullname)

        # Execute the code in the script
        (outbuf,nfigs)=execplot(self.c.g.plotengine,self.codebuf.split('\n'),
                                outputprefix,self.c.t.imagetype,self.c.g.tmpdir,self.c.g.execplot)
        
        # Go through the code and fill in the correct filenames
        counter = 1
        for idx in range(len(self.parsed['body'])):
            line = self.parsed['body'][idx]
            if line.find('figure::')>0:
                self.parsed['body'][idx] = line+' '+self.name+'_'+`counter`+'.'+self.c.t.imagetype
                if len(self.c.t.widthstr)>0:
                    out['body'].append('   :width: '+self.c.t.widthstr)

                counter += 1
        

        # Append the result, if there is any
        if len(outbuf)>0:
            self.parsed['body'].append('*This code produces the following output*::')
            self.parsed['body'].append('')
            for outline in outbuf:
                self.parsed['body'].append('  '+outline)
            self.parsed['body'].append('')                

        #self.write_output_html(outbuf)

        # Do the main plotting.
        html_help_buf=self.print_html()

        self.writelines(self.fullname+self.c.t.fext,html_help_buf)

        html_code_buf=self.print_code_html()
        self.writelines(self.fullname+'_code'+self.c.t.fext,html_code_buf)            
        

    def print_tex(self,obuf):

        # Go through the code and fill in the correct filenames in the figure directives
        counter = 1
        rstbuf=[]
        for line in self.parsed['body']:
            if line.find('figure::')>0:
                rstbuf.append(line+' '+self.name+'_'+`counter`+'.'+self.c.t.imagetype)
                if len(self.c.t.widthstr)>0:
                    rstbuf.append('   :width: '+self.c.t.widthstr)

                counter += 1
            else:
                rstbuf.append(line)

        self.parsed['body']=rstbuf

        # Execute the inherited print_tex, to do the main work
        ExecPrinter.print_tex(self,obuf)

        outputprefix=os.path.join(self.c.t.dir,self.fullname)

        # Execute the code in the script
        (outbuf,nfigs)=execplot(self.c.g.plotengine,self.codebuf.split('\n'),
                                outputprefix,self.c.t.imagetype,self.c.g.tmpdir,self.c.g.execplot)
        
        obuf.append('\\subsubsection*{Output}')
            
        obuf.append('\\begin{verbatim}')

        for line in outbuf:
            obuf.append(line)

        obuf.append('\\end{verbatim}')

        return obuf

class ContentsPrinter(BasePrinter):

    def parse(self):

        html=[]
        files=[]
        sep='-'

        buf=self.buf_help

        buf.reverse()

        line=buf.pop()

        # First line defines the title.
        self.title=line.strip()

        obuf=[]

        while len(buf)>0:

            line=buf.pop()
                        
            if (sep in line) and not (isnewblock(line)):
                # Fix the preceeding line, if it is a text line
                if obuf[-1][0]=='text':
                    obuf[-1][0]='caption'
                
                # Put the line back in buf for parsing.
                buf.append(line)
                pairs=parse_pairs(sep,buf,find_indent(line))
                for (key,sep,val) in pairs:
                    obuf.append(['li',key.lower(),val])
                    files.append(key.lower())

                # Append an empty line, it is eaten by parse_pairs
                obuf.append(['text',''])
            else:
                obuf.append(['text',line.strip()])

        self.files=files

        self.parsed=obuf


    def old_print_html(self):

        maincontents=[]

        maincontents.append(self.c.t.hb+self.title+self.c.t.he)

        ul_on=0
        for line in self.parsed:

            if line[0]=='li':
                if ul_on==0:
                    maincontents.append('<ul>')
                    ul_on=1

                maincontents.append('<li><a href="'+line[1]+self.c.t.fext+'">'+line[1]+'</a> - '+line[2]+'</li>')
                continue

            # Turn of list mode, we have encountered a non-list line
            if ul_on==1:
                maincontents.append('</ul>')
                ul_on=0

            if line[0]=='text':
                maincontents.append(line[1])
                continue

            if line[0]=='caption':
                maincontents.append(self.c.t.hb+line[1]+self.c.t.he)
                continue

        self.html = self.c.t.structure_as_webpage(self,maincontents,0)


    def print_rst(self):

        maincontents=[]

        # Append the reference lookups for this project
        files=os.listdir(self.c.t.confdir)
        files=filter(lambda x: x[:4]=='ref-' and x[-4:]=='.txt',files)
        for filename in files:
            maincontents.append('.. include:: '+os.path.join(self.c.t.confdir,filename))

        maincontents.append(self.title)
        maincontents.append('='*len(self.title))


        ul_on=0
        for line in self.parsed:

            if line[0]=='li':
                if ul_on==0:
                    maincontents.append('')
                    ul_on=1

                maincontents.append('  * |'+line[1]+'| - '+line[2])
                continue

            # Turn of list mode, we have encountered a non-list line
            if ul_on==1:
                maincontents.append('')
                ul_on=0

            if line[0]=='text':
                # Substite the correct formula code
                if '$' in line[1]:
                    words=line[1].split('$')
                    line[1]=words[0]
                    for ii in range((len(words)-1)/2):
                        line[1]+=':math:`'+words[2*ii+1]+'`'+words[2*ii+2]

                maincontents.append(line[1])
                continue

            if line[0]=='caption':
                maincontents.append(line[1])
                maincontents.append('-'*len(line[1]))
                continue

        
        outstr=''
        for line in maincontents:
            outstr+=line+'\n'

        return outstr


    def print_tex(self):

        obuf=[]

        obuf.append('\graphicspath{{'+self.subdir+'/}}') 

        obuf.append('\\chapter{'+self.title+'}')

        for line in self.parsed:

            # Skip text lines
            if line[0]=='text':
                continue

            # Turn captions into sections
            if line[0]=='caption':
                obuf.append('\section{'+self.c.t.protect(line[1])+'}')
                continue

            if line[0]=='li':
                # Parse the file.
                fname=os.path.join(self.subdir,line[1])
                obuf.append('\input{'+fname+'}')
                continue
            
        return obuf



    def write_the_file(self):

        if self.c.t.basetype=='php' or self.c.t.basetype=='html':
            # Print the menu first, as the html target will need to
            # include it immidiatly
            menu=self.c.t.print_menu(self.parsed)
            self.writelines(os.path.join(self.subdir,'contentsmenu'+self.c.t.fext),menu)

            rststr=self.print_rst()
            webstr=call_rst(rststr,self.c.t.basetype)
            buf = rst_postprocess(webstr,self.c.t.basetype)
            buf = self.c.t.structure_as_webpage(self,buf,0)
            
            self.writelines(os.path.join(self.subdir,'index'+self.c.t.fext),buf)
            

        if self.c.t.basetype=='tex':
            obuf=self.print_tex()
            self.writelines(self.fullname+'.tex',obuf)
    

    def print_variables_php(self):
        # Convention used in this routine
        #   '  is the string delimiter in Python
        #   "  is the string delimiter in php

        obuf=[]

        # --- Title
        obuf.append('$title = "'+self.title+'";')

        obuf.append('$seealso = array();')
        obuf.append('$demos = array();')
        
        # --- Keywords
        obuf.append('$keywords = "'+self.title+'";')

        return obuf

    def print_variables_html(self):
        seealso=''
        return seealso


def isblank(line):
    if len(line.split())==0:
        return 1
    return 0
    
def isnewblock(line):
    if line[3]!=' ':
        return 1
    return 0

def parse_pairs(sep,buf,parent_indent):
    out=[]
    while len(buf)>0:
        line=buf.pop()
        ind=line.find(sep)

        if ind==-1:
            # No separator found.
            
            if find_indent(line)>parent_indent:
                # If this line is more indented than its parent,
                # add it to the list but with no separator
                out.append(('','',line[ind+1:].strip()))
            else:
                # End of block reached.
                # Put the line back into the buffer and stop
                buf.append(line)
                break
        else:            
            if ind+1==len(line.rstrip()):
                # The separator appears at the very end, this is a
                # new block.
                # Put the line back into the buffer and stop
                buf.append(line)
                break
            else:
                # Append the line, with separator
                out.append((line[0:ind].strip(),sep,line[ind+1:].strip()))
    return out


# Remove TeX-only charachters
def clean_tex(line):
    
    line=line.replace('$','')
    
    return line


def execplot(plotengine,buf,outprefix,ptype,tmpdir,do_it):

    tmpfile='plotexec'
    tmpname=os.path.join(tmpdir,tmpfile+'.m')
    fullpath=os.path.dirname(outprefix)
    funname =os.path.basename(outprefix).split('.')[0]

    # printtype determines the correct printing flag in Matlab / Octave
    printtype={'png':'-dpng',
               'eps':'-depsc'}[ptype]

    if not do_it:
        # We are not supposed to generate anything, but if there is no
        # _output file, we must rebuild anyway
        if not os.path.exists(outprefix+'_output'):
            do_it=1        

    if do_it:
        # Clear old figures. We *must* do this, as we cannot tell if
        # the number of figures has changed, and we would run the risk
        # of including old figures
        if os.path.exists(fullpath):
            p=os.listdir(fullpath)
            # Match only the beginning of the name, to avoid sgram maching resgram etc.
            oldfiles=filter(lambda x: x[0:len(funname)]==funname,p)
            for fname in oldfiles:
                os.remove(os.path.join(fullpath, fname))
        else:
            safe_mkdir(fullpath)

        obuf=u''

        obuf+='startup;\n'

        obuf+="disp('MARKER');\n"

        obuf+="""
    set(0, 'DefaultFigureVisible', 'off');
    %set(0, 'DefaultAxesVisible', 'off');
    """

        # Matlab does not terminate if there is an error in the code, so
        # we use a try-catch statment to capture the error an exit cleanly.
        obuf+="try\n"

        for line in buf:
            obuf+=line+'\n'

        obuf+="""

    for ii=1:numel(findall(0,'type','figure'))
      figure(ii);
      %X=get(gcf,'PaperPosition');
      %set(gcf,'PaperPosition',[X(1) X(2) .7*X(3) .7*X(4)]);
    """
        # Matlab does not support changing the resolution (-r300) when
        # printing to png in nodisplay mode.
        obuf+="print(['"+outprefix+"_',num2str(ii),'."+ptype+"'],'"+printtype+"')\n"
        obuf+="end;\n"

        obuf+="catch err\ndbstack\nerr.message\ndisp('ERROR IN THE CODE');end;"

        # Matlab needs an explicit 'exit' statement, otherwise the interpreter
        # hangs around.
        if plotengine=='matlab':
            obuf+='pause(1);\n'
            obuf+='exit\n'

        safewrite(tmpname,obuf)

        if plotengine=='octave':
           # -q suppresses the Octave startup message.
           s='octave -q '+tmpname
        else:
           s='matlab -nodesktop -nodisplay -r "addpath \''+tmpdir+'\'; '+tmpfile+';"'    

        print '   Producing '+outprefix+' using '+plotengine

        try:
            output=check_output(s,shell=True,stderr=PIPE)
        except CalledProcessError as s: 
            print '   WARNING: Exit code from Matlab',s.returncode
            output=s.output

        pos=output.find('MARKER')
        if pos<0:
            raise Mat2docError('For the output %s: The plot engine did not print the MARKER output.' % outprefix)

        # Remove everything until and including the marker
        output=output[pos+7:].strip()

        if 'ERROR IN THE CODE' in output:
            print '--------- Matlab code error ----------------'
            print output        
            raise Mat2docError('For the output %s: There was an error in the Matlab code.' % outprefix)

        output=output.strip()

        # Write the output to a file
        #safewrite(outprefix+'_output',output)
        f=open(outprefix+'_output','w')
        f.write(output)
        f.close()        

        # If string was empty, return empty list, otherwise split into lines.
        if len(output)==0:
            outbuf=[]
        else:
            outbuf=output.split('\n')

    # Read the output previously written
    outbuf=safereadlines(outprefix+'_output')


    # Sometimes Matlab prints the prompt on the last line, it ends
    # with a ">" sign, which should otherwise never terminate the output.
    if (len(outbuf)>0) and (outbuf[-1][-1]=='>'):
        outbuf.pop()


    # Find the number of figures
    p=os.listdir(fullpath)
    # Match only the beginning of the name, to avoid sgram maching
    # resgram etc.  Heuristic: The number of figures is the number of
    # files mathcing the name minus 1, because one of them is the
    # _output file
    nfigs=len(filter(lambda x: x[0:len(funname)]==funname,p))-1

    if do_it:
        print '   Created %i plot(s)' % nfigs
    else:
        print '   Found %i plot(s)' % nfigs


    return (outbuf,nfigs)


def print_matlab(conf,ifilename,ofilename):
    ibuf=safereadlines(ifilename)
    outbuf=u''

    # Determine the name of the function
    name = os.path.basename(ifilename).split('.')[0]

    ibuf.reverse()

    line=ibuf.pop()

    # Copy all lines before the first comment
    while not (len(line)>0 and line[0]=="%"):
        outbuf+=line+'\n'
        if len(ibuf)>0:
            line=ibuf.pop()
        else:
            break

    # figure counter for the demos
    nfig=1

    # Do the help section
    while len(line)>0 and line[0]=='%' and len(ibuf)>0:
        if  'References:' in line:
            (dummy,sep,s) = line.partition(':')
            reflist = s.strip().split()

            if len(reflist)==0:
                print '   WARNING: Empty list of references.'
            else:

                buf=call_bibtex2html(reflist,conf)

                obuf=''

                # Skip lines containing hyperlinks
                for rline in buf:
                    if rline[:1]=='[':
                        continue

                    if rline[:6]=='</tr>':
                        obuf+=rline+'\n'
                        obuf+='</table><br><table><tr>\n'
                        continue

                    obuf+=rline+u'\n'

                # Write the clean HTML to a temporary file and process it using
                # lynx.
                outname=os.path.join(conf.g.tmpdir,'reflist')
                safewrite(outname+'.html',obuf)

                s='lynx -dump '+outname+'.html > '+outname+'.txt'
                os.system(s)

                buf=safereadlines(outname+'.txt')

                buf=map(lambda x:x.strip(),buf)

                outbuf+=u'%   References:\n'
                for rline in buf[0:]:
                    outbuf+=u'%     '+rline+'\n'

            line=ibuf.pop()

            continue

        # Figures in demos
        if '.. figure::' in line:
            # Pop the empty line
            line_empty=ibuf.pop()
            if len(line_empty[1:].strip())>0:
                print '   Error: Figure definition must be followed by a single empty line.'
                sys.exit()
                
            heading=ibuf.pop()

            if len(heading[1:].strip())==0:
                print 'Error: Figure definition must be followed by a single empty line.'
                sys.exit()

            outbuf+=u'%   Figure '+`nfig`+': '+heading[1:].strip()+u'\n'
            line=ibuf.pop()

            if len(line[1:].strip())>0:
                print '   Error: Figure definition must be followed by a single line header and an empty line.'
                sys.exit()

            nfig+=1

            continue

        # remove the display math sections. FIXME: This will not
        # correctly handle display math in nested environments.
        if '.. math::' in line:
            line=ibuf.pop()
            
            # Keep removing lines until we hit an empty line.
            while len(line[1:].strip())>0:
                line=ibuf.pop()

            continue

        # Handle comments: No substitutions must be made in
        # comments, so they are handled differently than the rest
        # of the text
        if line[1:].strip()[0:2]=='..':
            idl=find_indent(line[1:])
            # Remove the start of the comments
            line=line.replace(' .. ','    ')
            outbuf+=line+'\n'
            line=ibuf.pop()
            # While the line does not start at zero.
            while not (len(line[1:].strip())>0 and find_indent(line[1:])==idl):
                outbuf+=line+'\n'
                line=ibuf.pop()

            continue


        # Keep all other lines.
        if len(line)>2:

            # Remove inline formula markup
            line=line.replace('$','')

            # Math substitutions
            line=line.replace('\ldots','...')
            line=line.replace('\\times ','x')
            line=line.replace('\leq','<=')
            line=line.replace('\geq','>=')
            line=line.replace('\cdot ','*')
            line=line.replace('\pm ','+-')
            line=line.replace('\mathbb','')
            # Kill all remaining backslashes
            line=line.replace('\\','')

            # Remove hyperlink markup
            line=line.replace('`<','')
            line=line.replace('>`_','')

            # Convert internal links to uppercase
            p=re.search(' \|.*?\|',line)
            if p:
                line=line[0:p.start(0)+1]+line[p.start(0)+2:p.end(0)-1].upper()+line[p.end(0):]

            # Uppercase the function name appearing inside backticks, and remove them
            p=re.search('`.*?`',line)
            if p:
                line=line[0:p.start(0)]+line[p.start(0)+1:p.end(0)-1].replace(name,name.upper())+line[p.end(0):]

            #line=line.replace('`','')

            # Remove stars
            line=line.replace(' *',' ')
            line=line.replace('* ',' ')
            line=line.replace('*,',',')
            line=line.replace('*.','.')
            line=line.replace('*\n','\n')


            if line.find(':::')>0:
                line=line.replace(':::',':')
                

            # Convert remaining :: into :
            line=line.replace('::',':')

            outbuf+=line+'\n'
        else:        
            outbuf+=line+'\n'

        line=ibuf.pop()

    # Append url for quick online help
    # Find the name of the file + the subdir in the package 
    shortpath=ifilename[len(conf.t.dir):-2]
    outbuf+=u'%\n'
    outbuf+=u'%   Url: '+conf.t.urlbase+shortpath+conf.t.urlext+'\n'
    
    # --- Append header
    # Append empty line to seperate header from help section
    outbuf+=u'\n'
    outbuf+=conf.t.header

    # Append the rest (non-help section)
    while len(ibuf)>0:
        outbuf+=line+'\n'
        line=ibuf.pop()

    # Write the last line and write the buffer to file
    outbuf+=line+'\n'

    outbuf+=conf.t.footer

    safewrite(ofilename,outbuf)


# This factory function creates function or script file objects
# depending on whether the first word of the first line is 'function'
def matfile_factory(conf,fname):
    
    buf=safereadlines(os.path.join(conf.g.projectdir,fname+'.m'))

    if buf[0].split()[0]=='function':
        return FunPrinter(conf,fname)
    else:
        return ExamplePrinter(conf,fname)

def find_indent(line):
    ii=0
    while (ii<len(line)) and (line[ii]==' '):
        ii=ii+1
    return ii

def printdoc(projectname,projectdir,targetname,rebuildmode='auto',do_execplot=True):

    target=targetname
    confdir=os.path.join(projectdir,'mat2doc')

    conf=ConfContainer()

    # Global
    conf.g=GlobalConf(confdir,projectname,projectdir)

    conf.g.bibfile=os.path.join(projectdir,'mat2doc','project')

    conf.g.execplot=do_execplot

    # Target
    if target=='php':
        conf.t=PhpConf(conf.g)

    if target=='html':
        conf.t=HtmlConf(conf.g)

    if target=='tex':
        conf.t=TexConf(conf.g)

    if target=='mat':
        conf.t=MatConf(conf.g)
        

    conf.t.basetype=targetname
    conf.t.indexfiles=find_indexfiles(projectdir)

    safe_mkdir(conf.t.dir)

    # Copy the startup.m file to the temporary directory
    shutil.copy(os.path.join(confdir,'startup.m'),conf.g.tmpdir)
    
    if conf.t.basetype=='php' or conf.t.basetype=='tex' or conf.t.basetype=='html':

        fileext='.'+conf.t.basetype

        # These should not be neccesary to set, as they depend on
        # reStructuredTex, so they are impossible to change
        # Still needed for printing the code
        conf.t.hb='<H2>'
        conf.t.he='</H2>'

        print "Creating list of files"
        # Search the Contents files for all files to process
        allfiles=[]
        lookupsubdir={}
        for fname in conf.t.indexfiles:
            P=ContentsPrinter(conf,fname)

            # Create list of files with subdir appended	
            subdir,fname=os.path.split(fname)
            for name in P.files:
                if not name in conf.g.ignorelist:
                    allfiles.append(os.path.join(subdir,name))
                    lookupsubdir[name]=subdir
                else:
                    print '   IGNORING ',name

        conf.lookupsubdir=lookupsubdir

        print "Writing internal refs"
        f=open(os.path.join(conf.t.confdir,'ref-'+conf.g.projectname+'.txt'),'w')

        if conf.t.basetype=='tex':
            f.write('.. role:: linkrole(raw)\n')
            f.write('   :format: latex\n')

            for funname in lookupsubdir.keys():
                f.write('.. |'+funname+'| replace:: :linkrole:`\\nameref{'+funname+'}`\n')

        else:
            f.write('.. role:: linkrole(raw)\n')
            f.write('   :format: html\n')

            for funname in lookupsubdir.keys():
                tn=os.path.join(conf.t.urlbase,lookupsubdir[funname],funname)+conf.t.fext
                f.write('.. |'+funname+'| replace:: :linkrole:`<a href="'+tn+'">'+funname+'</a>`\n')

        # flush the file, because we need it again very quickly
        f.flush()
        f.close()

        # Print Contents files
        lookupsubdir={}
        for fname in conf.t.indexfiles:
            P=ContentsPrinter(conf,fname)
            if do_rebuild_file(os.path.join(conf.g.projectdir,fname+'.m'),
                               os.path.join(conf.t.dir,os.path.dirname(fname),'index'+fileext),
                               rebuildmode):
                P.write_the_file()


        for fname in allfiles:
            if do_rebuild_file(os.path.join(conf.g.projectdir,fname+'.m'),
                               os.path.join(conf.t.dir,fname+fileext),
                               rebuildmode):
                print 'Rebuilding '+conf.t.basetype+' '+fname

                P=matfile_factory(conf,fname)
                P.write_the_file()

        # Post-stuff, copy the include directory
        if conf.t.basetype=='html':
            targetinc=os.path.join(conf.t.dir,'include')
            rmrf(targetinc)
            safe_rmdir(targetinc)
            shutil.copytree(os.path.join(confdir,conf.t.basetype,'include'),targetinc)
        
        

    if conf.t.basetype=='mat':
          
        matExport(projectdir,conf.t.dir)

        for root, dirs, files in os.walk(conf.t.dir, topdown=False):
            # Walk through the .m files
            for mfile in filter(lambda x: x[-2:]=='.m',files):
                print 'MAT '+os.path.join(root,mfile)
                print_matlab(conf,os.path.join(root,mfile),os.path.join(root,mfile))
        

    if conf.t.basetype=='verify':

        print conf.t.sourcedir

        for root, dirs, files in os.walk(conf.t.sourcedir, topdown=False):
            # Walk through the .m files
            for name in filter(lambda x: x[-2:]=='.m',files):
                fullname=os.path.join(root,name)
                print 'VERIFY '+name

                ignored=0
                for s in conf.t.ignore:
                    if re.compile(s).search(name, 1):
                        ignored=1

                if ignored==1:
                    print 'IGNORED',name
                else:
                    f=open(fullname);
                    buf=f.read()
                    f.close()

                    for target in conf.t.targets:
                        if buf.find(target)==-1:
                            print '   ',target,'is missing'

                    for notappear in conf.t.notappears:
                        pos=buf.find(notappear)
                        if pos>1:
                            endpos=buf.find('\n',pos)
                            print '   ',buf[pos:endpos]


# ------------------ Run the program from the command line -------------

# Parse the command line options
parser = argparse.ArgumentParser(description='The mat2doc documentation generator.')
parser.add_argument('target', choices=['mat','html','php','tex'],
                    help='Output target')
parser.add_argument('filename', help='File or directory to process', default='')

parser.add_argument('-q', '--quiet',
                  action="store_false", dest='verbose', default=True,
                  help="don't print status messages to stdout")

# Mutually exclusive : --execplot and --no-execplot
group1 = parser.add_mutually_exclusive_group()
group1.add_argument("--execplot", action="store_true", help='Process examples and demos')
group1.add_argument("--no-execplot", action="store_true",help='Do not process examples or demos, but used cached files instead, if available')

# Mutually excluse : --auto, --cached, --rebuild
group2 = parser.add_mutually_exclusive_group()
group2.add_argument("--auto", dest='rebuildmode',action="store_const",const='auto',
                    help='Process changed files automatically')
group2.add_argument("--rebuild", dest='rebuildmode', action="store_const",const='rebuild',
                    help='Rebuild all files')
group2.add_argument("--cached", dest='rebuildmode', action="store_const",const='cached',
                    help='Only use cached files, never build')

args = parser.parse_args()

rebuildmode=args.rebuildmode
if rebuildmode==None:
    rebuildmode='auto'

# Locate the mat2doc configuration directory
projectname,projectdir,confdir=findMat2docDir(args.filename)

printdoc(projectname,projectdir,args.target,rebuildmode,not args.no_execplot)






