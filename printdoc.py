#!/bin/env python

import sys, os, os.path, shutil, re, commands, time

# Append the current path so that we can load localconf
cwd=os.getcwd()+os.sep
sys.path.append(cwd)

import localconf

# Create a string containining day,month,year
def datesuffix():
    # Create a time suffix.
    t=time.localtime()
    
    date=`t[2]`
    if len(date)==1:
        date='0'+date
        
    month=`t[1]`
    if len(month)==1:
        month='0'+month

    year=`t[0]`[2:]

    s = date+month+year

    return s

# rm -Rf
# Does not remove the directory itself
def rmrf(s):
    for root, dirs, files in os.walk(s, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))

# Create directory, and do not produce an error if it already exists
def safe_mkdir(dir):
    try:
        os.makedirs(dir)
    except OSError:
        pass

# Make sure that a Git repo is on a specific branch
def assert_git_on_branch(repo,branchname):
    buf=commands.getoutput('git --git-dir='+repo+'.git branch | grep "*"')
    if not (buf.strip()[2:]==branchname):
        print 'Git repo',repo,'is not on branch "'+branchname+'". Stopping.'
        sys.exit(0)

def git_autostage(repo):
    # This command explicitly swicthes working directory to the
    # repository, otherwise git will think that the directory is
    # empty, and stage all files for removal.
    s = 'cd '+repo+'; git add -u'
    os.system(s)

def git_stageexport(repo,outdir):
    rmrf(outdir)
    git_autostage(repo)
    os.system('git --git-dir='+repo+'/.git/ checkout-index --prefix='+outdir+' -a')

def git_repoexport(repo,outdir,branchname='master'):
    assert_git_on_branch(repo,branchname)

    os.makedirs(outdir)
    rmrf(outdir)
    
    s='git --git-dir='+repo+'/.git/ archive '+branchname+' | tar -x -C '+outdir
    os.system(s)

def git_stageexport_mat(projectname):
    project=localconf.projects[projectname]
    repo=localconf.projects[projectname]
    outdir=localconf.outputdir+projectname+'-mat'+'/'

    rmrf(outdir)
    git_autostage(repo)
    os.system('git --git-dir='+repo+'/.git/ checkout-index --prefix='+outdir+' -a')

def git_repoexport_mat(projectname,branchname='master'):
    project=localconf.projects[projectname]
    repo=localconf.projects[projectname]
    outdir=localconf.outputdir+projectname+'-mat'+os.sep

    assert_git_on_branch(repo,branchname)

    rmrf(outdir)
    s='git --git-dir='+repo+'/.git/ archive '+branchname+' | tar -x -C '+outdir
    os.system(s)


def dos2unix(path):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            name=os.path.join(root, name)
            if 'ASCII' in commands.getoutput('file '+name):
                os.system('dos2unix '+name)

# Change the lineending to dos
def unix2dos(path):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            name=os.path.join(root, name)
            filecheck=commands.getoutput('file '+name)
            if 'ASCII' in filecheck:
                os.system('unix2dos '+name)

def convertencoding(path,targetencoding):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            name=os.path.join(root, name)
            filecheck=commands.getoutput('file '+name)
            if 'UTF-8' in filecheck:
                s='iconv --from-code=UTF-8 --to-code='+targetencoding+' '+name+' -o '+name
                print 'iconv: converting',name

                try:
                    output=check_output(s,shell=True,stderr=PIPE)
                except CalledProcessError as s:
                    print s.output
                    raise s

# ------------ inititializations and script calling ----------------

# Make sure that the temporary directory exists and empty it

if 'printdoc' in sys.argv[0]:
    if len(sys.argv)==1:
        print 'Usage: printdoc.py [project] [target] <rebuildmode>'
        sys.exit()
    
    if len(sys.argv)==2:
        printdoc(sys.argv[1],sys.argv[2])
    else:
        printdoc(sys.argv[1],sys.argv[2],sys.argv[3])
