import os, sys,json 
base = os.path.dirname(os.path.dirname(__file__)) 
base_parent = os.path.dirname(base) 
sys.path.append(base) 
sys.path.append(base_parent)

import os,collections,sys, time, ConfigParser,tarfile,random,logging,string,getopt
from threading import Thread
from Queue import *
from django.db import models
from django.conf import settings
from django.db.models import Q
from django.contrib import messages
from django.db import transaction
from datetime import datetime
from pytz import timezone
from archiver.models import Archives,ArchiveFiles
from archiver.crawler import Crawler
from archiver.tasks import archiveFilesTask as af

from glacier.glacier import Connection as GlacierConnection
from glacier.vault import Vault as GlacierVault
from glacier.archive import Archive as GlacierArchive

NUM_PROCS=1
TEMP_DIR="/tmp"
ACCESS_KEY=""
SECRET_ACCESS_KEY=""
GLACIER_VAULT=None
DEBUG_MODE=False
FILE=False
DIR=True
RECURSE=False
OLDERTHAN=0
NEWERTHAN=0
FILENAME="."
TAGS=None
DESCRIPTION=None
NUMFILES=1000
ARCHIVEMB=500
GLACIER_REALM="us-east-1"
USECELERY=False
DRY=False

logger=logging.getLogger(__name__)
queue = Queue()

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))

def uploadToGlacier(tempTarFile=None,
                    DEBUG_MODE=False,
                    GLACIER_VAULT=None,
                    SECRET_ACCESS_KEY=None,
                    ACCESS_KEY=None,
                    GLACIER_REALM=None):
    global logger

    if not tempTarFile:
        return 0
    # Establish a connection to the Glacier
    glacier_vault_in=None
    my_archive=None
    try:
        my_glacier = GlacierConnection(ACCESS_KEY,SECRET_ACCESS_KEY,region=GLACIER_REALM)
        if DEBUG_MODE:
            logger.debug("Glacier Connection: %s" % my_glacier)
        # Create a new vault (not neccessary if you already have one!)
        if GLACIER_VAULT:
            glacier_vault_in = my_glacier.get_vault(GLACIER_VAULT)
            vaults = my_glacier.get_all_vaults()
            if GLACIER_VAULT not in vaults:
                glacier_vault_in = my_glacier.create_vault(GLACIER_VAULT)
        else:
            glacier_vault_in = my_glacier.create_vault(id_generator(size=16))

        if DEBUG_MODE:
            logger.debug("Glacier Vault: %s" % glacier_vault_in)
        
        my_archive = GlacierArchive(tempTarFile)
        if DEBUG_MODE:
            logger.debug("Archive created in mem: %s " % my_archive)
    
        glacier_vault_in.upload(my_archive)
        if DEBUG_MODE:
            logger.debug("upload created: %s" % glacier_vault_in)
    except Exception,exc:
        if exc.args>0:
            x, y = exc.args
            logger.error("Error in glacier upload %s" % json.loads(y.read()))
        else:
            logger.error("Error in glacier upload %s" % (exc))

    if my_archive:
        try:
            os.unlink(tempTarFile)
        except Exception,exc:
            logger.error("couldn't unlink file: %s" % tempTarFile)
        if DEBUG_MODE:
            logger.debug("Archive created: %s" % my_archive.id)
        return my_archive.id    
    return 0

def makeTar(fileList=None,tempfilename=None,dry=False):
    #tempfilename = TEMP_DIR+"/"+id_generator(size=16)
    global NEWERTHAN,OLDERTHAN
    if dry:
        return
    tar = tarfile.open(tempfilename, "w")
    for name in fileList:
        statinfo = os.stat(name)
        atime = statinfo.st_atime
        mtime = statinfo.st_mtime
        tar.add(name)
        try:    
            os.utime(name, (atime,mtime))
        except Exception,exc:
            logger.error("Cannot change utime: %s" % name)
    tar.close()
    logger.debug("Created archive in tar: %s" % tempfilename)
    return     

@transaction.commit_manually
def archiveFiles (tempTarFile=None,dry=False):
    global queue
    global logger
    global GLACIER_VAULT
        
    if queue.empty() == True:
        print "the Queue is empty!"
    while queue.qsize()>0:
        print "the Queue has stuff: %s" % queue.qsize()    
        try:
            job = queue.get()
            print "Got job %s-files" % len(job)
            try:
                #create database archive
                #c = Archives()
                c = Archives().archive_create(short_description=DESCRIPTION,tags=TAGS,vault=GLACIER_VAULT)
                if not dry:
                    sid = transaction.savepoint()
                if DEBUG_MODE:
                    logger.debug("Created archive in DB")
                #add files to temp archive on disk
                try:
                    #add each to tarchive
                    makeTar(job,tempTarFile,DRY)
                    if not DRY:
                        transaction.savepoint_commit(sid)
                    if DEBUG_MODE:
                        logger.debug("Number of files in job: %s -- File %s" % (len(job),tempTarFile))
                    #add each to DB
                    bulk=[]
                    filelength=len(job)
                    total_bytesize=0
                    if tempTarFile:
                        for jobfile in job:
                            statinfo = os.stat(jobfile)
                            bytesize = statinfo.st_size
                            atime = statinfo.st_atime
                            mtime = statinfo.st_mtime
                            ctime = statinfo.st_ctime
                            f = ArchiveFiles(archive=c,
                                             startdate=datetime.now(),
                                             bytesize=bytesize,
                                             filepath=jobfile,
                                             fileadate=datetime.fromtimestamp(atime),
                                             filecdate=datetime.fromtimestamp(ctime),
                                             filemdate=datetime.fromtimestamp(mtime),
                                             )
                            total_bytesize=total_bytesize+bytesize
                            bulk.append(f)
                    if dry:
                        if DEBUG_MODE:
                            logger.debug("done task -- dry run -- %s " % tempTarFile)
                        transaction.rollback()
                        queue.task_done()                        
                    else:
                        ArchiveFiles.objects.bulk_create(bulk)
                    #upload to glacier
                        archive_id = uploadToGlacier(tempTarFile=tempTarFile,
                                                     DEBUG_MODE=DEBUG_MODE,
                                                     GLACIER_VAULT=GLACIER_VAULT,
                                                     SECRET_ACCESS_KEY=SECRET_ACCESS_KEY,
                                                     ACCESS_KEY=ACCESS_KEY,
                                                     GLACIER_REALM=GLACIER_REALM)
                        c.update_archive_id(archive_id)
                        c.bytesize=total_bytesize
                        c.filecount=filelength
                        c.save()
                        queue.task_done()
                        transaction.commit()
                    if DEBUG_MODE:
                        logger.debug("done task: %s " % tempTarFile)
                except Exception,exc:
                    logger.error('Error creating archive %s' % exc)
                    transaction.rollback()
                    queue.task_done()
                #get archive_id
            except Exception,exc:
                logger.error('Error creating archive2 %s' % exc)
                transaction.rollback()
                queue.task_done()
        except Exception,exc:
            logger.error("error on queue: %s" % exc)
            try:
                transaction.rollback()
                queue.task_done()
            except:
                pass

def main(argv):
    #set up all of the variables
    global NUM_PROCS,TEMP_DIR,ACCESS_KEY,SECRET_ACCESS_KEY,GLACIER_VAULT,NUMFILES,ARCHIVEMB,GLACIER_REALM,USECELERY,DRY
    NUM_PROCS=settings.NUM_PROCS
    TEMP_DIR=settings.TEMP_DIR
    ACCESS_KEY=settings.ACCESS_KEY
    SECRET_ACCESS_KEY=settings.SECRET_ACCESS_KEY
    GLACIER_VAULT=settings.GLACIER_VAULT
    NUMFILES=settings.NUMFILES
    ARCHIVEMB=settings.ARCHIVEMB
    GLACIER_REALM=settings.GLACIER_REALM
    USECELERY=settings.USECELERY

    try:
        opts, args = getopt.getopt(argv, "hx:z:t:s:rdn", [
                                "help", 
                                "olderthan=",
                                "newerthan=",
                                "description=",
                                "tags=",
                                "recursive",
                                "debug",
                                "dry"
                            ])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    
    #make sure file exists
    global FILENAME
    global DIR
    try:    
        FILENAME = argv[len(argv) - 1]
        if os.path.exists(FILENAME):
            if os.path.isdir(FILENAME):
                DIR=True
            elif os.path.isfile(FILENAME):
                DIR=False
        else:
            print "ERROR file does not exist: %s" % FILENAME
            usage()
            sys.exit(2)                            
    except Exception,exc:
        print "ERROR %s" % exc
        usage()
        sys.exit(2)                

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-d","--debug"):
            global DEBUG_MODE
            DEBUG_MODE=True
        elif opt in ("-x", "--olderthan"):
            global OLDERTHAN
            OLDERTHAN = arg
        elif opt in ("-z", "--newerthan"):
            global NEWERTHAN
            NEWERTHAN = arg
        elif opt in ("-t", "--tags"):
            global TAGS
            try:
                TAGS=arg.split(',')
            except Exception,exc:
                print "this is not a valid comma separated list."
                usage()
                sys.exit()
        elif opt in ("-s", "--description"):
            global DESCRIPTION
            DESCRIPTION = arg
        elif opt in ("-r","--recursive"):
            global RECURSE
            RECURSE=True
        elif opt in ("-n","--dry"):
            global DRY
            DRY=True
    
    #set up logging
    global logger
    if DEBUG_MODE:
        print "DEBUG MODE"
        
    #start crawl - single crawl, launches multiple tasks
    global queue
    if USECELERY:
        if DIR:
            c = Crawler(filepath = FILENAME,recurse=RECURSE,numfiles=NUMFILES,archivemb=ARCHIVEMB,queue=queue,usecelery=USECELERY)
            c.set_newer(int(NEWERTHAN))
            c.set_older(int(OLDERTHAN))
            c.recurseCrawl(FILENAME)
            for job in c.alljobs:
                af.apply_async(args=[(TEMP_DIR+"/"+id_generator(size=16)), job,DEBUG_MODE,DESCRIPTION,TAGS,DRY])
                #archiveFiles.delay(4, 4)            
        else:
            pass
            #one file
    else:
        if DIR:
            c = Crawler(filepath = FILENAME,recurse=RECURSE,numfiles=NUMFILES,archivemb=ARCHIVEMB,queue=queue,usecelery=USECELERY)
            c.set_newer(int(NEWERTHAN))
            c.set_older(int(OLDERTHAN))
            c.recurseCrawl(FILENAME)
            for i in range(NUM_PROCS):
                t = Thread(target=archiveFiles,args=[TEMP_DIR+"/"+id_generator(size=16),DRY])
                t.setDaemon(True)
                t.start()
        else:
            fileList=[]
            fileList.append(FILENAME)
            queue.put(fileList)    
            for i in range(NUM_PROCS):
                t = Thread(target=archiveFiles,args=[TEMP_DIR+"/"+id_generator(size=16),DRY])
                t.setDaemon(True)
                t.start()
        
        queue.join()
        if queue.empty():
            print "Done processing queue."
            sys.exit(1)        

def usage():
    print 'archiveFilesCommandline.py - find and archive to glacier'
    print 
    print 'archiveFilesCommandline.py [options] filepath'
    print 
    print 'options:'
    print ' -h|--help'
    print ' -d|--debug'
    print ' -x|--olderthan= older than in days, include. If left blank, all inclusive.'
    print ' -z|--newerthan= newer than in days, include. If left blank, all inclusive.'
    print ' -t|--tags= comma delimited list of keywords for later retrieval'
    print ' -s|--description= short description of archive'
    print ' -r --recursive'
    print ' -n --dry'
    print

if __name__ == "__main__":
    main(sys.argv[1:])
