#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from output import Output
from lxml import html
import imp
import datetime
import shutil

parsers = []

def select_parser(url):
    global parsers
    for parser in parsers:
        for parseurl in parser[0]:
            if url.startswith(parseurl):
                return parser[1](url)
    

def get():
    if len(sys.argv) < 3:
        print >> sys.stderr, "Insufficient args."
        sys.exit(1)
    if os.path.isfile('lock.pid'):
        pidfile = open('lock.pid', 'r')
        pid = pidfile.read()
        pidfile.close()
        try:
            os.kill(int(pid), 0)
        except OSError:
            pass
        else:
            print >> sys.stderr, "Already running instance"
            sys.exit(2)

    pidfile = open('lock.pid', 'w')
    pidfile.write(str(os.getpid()))
    pidfile.close()
    
    for modfile in os.listdir('parsers'):
        if modfile.endswith('.py'):
            try:
                name = "parsers/" + modfile[:-3]
                parsefile, pathname, description = imp.find_module(name)
            except:
                print >> sys.stderr, 'MODULE: %s not found' % modfile[:-3]
                sys.exit(1)

            try:
                method = imp.load_module(name, parsefile, pathname, description).info
            except:
                print >> sys.stderr, 'MODULE: can\'t load %s' % modfile[:-3]

            else:
                parsers.append(method())

    try:
        # load threads list from threads.txt
        _threadsfile = open(sys.argv[2], 'r')
        _threads = _threadsfile.read().split()
        _threadsfile.close()
        _threads = filter(lambda x: x != '', _threads)
    except IOError:
        print >> sys.stderr, "Error opening threads file " + sys.argv[1]
        sys.exit(1)

    # for every thread

    deadthreads = set()
    for url in _threads:

    #{{{
    # download thread page
    # make lxml from the data 
        _activeparser = select_parser(url)
        if _activeparser:
            print >> sys.stderr, "Checking " + url
            _threadfile = os.path.join("threads", _activeparser.outname)
            if not _activeparser.died:
                _toDownload = _activeparser.get_posts_number()
            # if this thread was already downloaded:
                output_writer = None
                if os.path.isfile(_threadfile):
            #{{{
                    #    make lxml from it
                    #    get posts number in it
                    output_writer = Output(_activeparser.outname[:-5], infile = _threadfile)
                    out_nums = set(output_writer.get_posts_number())
                    in_nums = set(_activeparser.get_posts_number())
                    deleted = list(out_nums - in_nums)
                    #    leave only new posts in _toDownload
                    _toDownload = list(in_nums - out_nums)
                    #    mark deleted posts in _deleted
                    for post in deleted:
                        # set deleted marks
                        output_writer.mark_deleted(post)

            #}}}
                else:
                    title = _activeparser.get_title()
                    output_writer = Output(_activeparser.outname[:-5], title = title[0], board = title[1])

                _toDownload.sort(cmp = lambda x,y: int(x) - int(y))
                postcnt = len(_toDownload) - 1
                for post in _toDownload:
            #{{{
                    print >> sys.stderr, "Adding post #" + post + " (" + str(postcnt) + " left)"
                    #    get the post from thread
                    newpost = _activeparser.get_post(post)
                    #    add this post to the end
                    output_writer.add_post(newpost)
                    #    get images and thumbnails links
                    post_image = _activeparser.get_images(post)
                    if post_image:
                        #    download images and thumbs
                        print >> sys.stderr, "Downloading image for post..."
                        output_writer.download_images(*post_image)
                    postcnt -= 1
                    
                # save the thread
                output_writer.save(_activeparser.outname)

            #}}}

            else:
                deadthreads.add(url)
                if os.path.isfile(_threadfile): # leave mark that thread died
                    output_writer = Output(_activeparser.outname[:-5], infile = _threadfile)
                    output_writer.add_post({'topic': '', 'date': datetime.datetime.now().strftime("%a %d %b %Y %H:%M:%S"), 'postername': 'locmechan', 'postnumber': '******', 'text': html.fromstring(u'<p style="color: #ff0000; font-style: italic;">Тред умер.</p>')})
                    output_writer.save(_activeparser.outname)
                print >> sys.stderr, "Thread died: " + url
        else:
            print >> sys.stderr, "Unsupported url: " + url

    threadfile = open(sys.argv[2], 'r')
    filethreads = set(threadfile.read().split())
    threadfile.close()

    threadfile = open(sys.argv[2], 'w')
    filethreads = list(filethreads - deadthreads)
    filethreads.sort()
    threadfile.write('\n'.join(filethreads))
    threadfile.close()
    os.unlink('lock.pid')

    #}}}

def get_aliases():
    if not os.path.isdir("aliases") or not os.listdir("aliases"):
        return []

    result = []
    aliases = filter(lambda x: x.endswith(".html"), os.listdir("aliases"))
    for alias in aliases:
        result.append([alias.decode('utf-8'), os.path.basename(os.readlink(os.path.join("aliases", alias)))])
        
    return result

def list_aliases():
    aliases = get_aliases()
    if not aliases:
        print "No aliases defined."
        return
    
    print "Aliased threads:"
    for alias in aliases:
        print "%s -> %s" % (alias[0], alias[1])

def list_not_aliased():
    aliases = get_aliases()
    aliased = [x[1] for x in aliases]
    threads = filter(lambda x: x.endswith(".html"), os.listdir("threads"))
    notaliased = filter(lambda x: not x in aliased, threads)
    notaliased.sort()
    print "Not aliased threads:"
    for thread in notaliased:
        print thread

def add_alias():
    if len(sys.argv) < 4:
        print >> sys.stderr, "Insufficient args, need command, thread file and alias name."
        sys.exit(1)

    if not os.path.isfile(sys.argv[2]):
        print >> sys.stderr, "First argument isn't thread filename."
        sys.exit(1)

    try:
        if not os.path.isdir("aliases"):
            os.mkdir("aliases")

        if not os.path.isdir("aliases/images"):
            os.symlink("../threads/images", "aliases/images")
        if not os.path.isdir("aliases/thumbs"):
            os.symlink("../threads/thumbs", "aliases/thumbs")
            
        os.symlink(os.path.join("..", sys.argv[2]), os.path.join("aliases", sys.argv[3] + ".html"))
    except OSError, c:
        print "Error creating alias:", c
    else:
        print "Alias created."

def delete_thread():
    if len(sys.argv) < 3:
        print "Insufficient args, need path to the thread to delete"
        return
    
    if not os.path.isfile(sys.argv[2]):
        print "Thread doesn't exist!"
        return

    aliases = get_aliases()
    alias = filter(lambda x: x[1] == os.path.basename(sys.argv[2]), aliases)
    if alias:
        for a in alias:
            os.unlink(os.path.join("aliases", a[0]))
    threadnumber = os.path.basename(sys.argv[2])[:-5]
    images_dir = os.path.join("threads/images", threadnumber)
    thumbs_dir = os.path.join("threads/thumbs", threadnumber)
    os.unlink(sys.argv[2])
    try:
        shutil.rmtree(images_dir)
        shutil.rmtree(thumbs_dir)
    except OSError:
        pass
    
    print "Thread deleted."
        
def help():
    print """LocmeChan - imageboard threads keeping engine.

Commands:
help - this help message.
get <path/to/links.txt> - check, download and sync threads which are listed in links.txt. Run this with cron to periodically update watched threads.
lsa - list threads aliases.
lsna - list not aliased threads. Alias them now!
a <threads/some_thread.html> <"new alias"> - add thread alias.
del <threads/some_thread.html> - delete thread, its aliases, pics'n'thumbs
"""
        
commands = {'get': get, 'lsa': list_aliases, 'lsna': list_not_aliased, 'a': add_alias, 'help': help, 'del': delete_thread}

if len(sys.argv) < 2:
    commands['help']()
elif sys.argv[1] in commands:
    commands[sys.argv[1]]()
else:
    print "No such command. Try running without parameters to show help."
