#!/usr/bin/python

import sys,os,os.path
cwd=os.getcwd()+'/'

# ------- Configuration parameters -------------


# ------- do not edit below this line ----------

# Import the localconf file, it should be place in the same directory
# as this function is called from.

sys.path.append(cwd)
import localconf

sys.path.append(localconf.mat2docdir)

import printdoc, notes

package=sys.argv[1]

if package=='amt':
    # Configure HTML placement at remote server
    host='soender,amtoolbox@web.sourceforge.net'
    noteswww='/home/project-web/amtoolbox/htdocs//'

    notesdir='~/nw/amtnotes'
    noteshtml='~/publish/amtnoteshtml'
    noteswww='/home/project-web/amtoolbox/htdocs/notes/'

if package=='ltfat':
    host='soender,amtoolbox@web.sourceforge.net'
    noteswww='/home/project-web/ltfat/htdocs//'

    notesdir='~/nw/notes'
    noteshtml='~/publish/noteshtml'
    noteswww='/home/project-web/ltfat/htdocs/notes/'

prefix=package+'note'
notesdir=os.path.expanduser(notesdir)+os.sep
noteshtml=os.path.expanduser(noteshtml)+os.sep



todo=sys.argv[2]

if 'make' in todo:
    notes=notes.getnotenumbers(notesdir)

    notes = filter(lambda x: (os.path.exists(notesdir+x+'/Makefile')), notes)

    for notenumber in notes:
        print 'Trying to make '+package+' note '+notenumber
        os.system('cd '+notesdir+notenumber+'; make')

if 'clean' in todo:
    notes=notes.getnotenumbers(notesdir)

    notes = filter(lambda x: (os.path.exists(notesdir+x+'/Makefile')), notes)

    for notenumber in notes:
        os.system('cd '+notesdir+notenumber+'; make texclean')

if 'html' in todo:
    notes.printnoteshtml(prefix,notesdir,noteshtml)
        
    os.system('rsync -av '+noteshtml+' '+host+':'+noteswww);
