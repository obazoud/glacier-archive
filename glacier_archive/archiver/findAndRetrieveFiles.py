import os, sys 
base = os.path.dirname(os.path.dirname(__file__)) 
base_parent = os.path.dirname(base) 
sys.path.append(base) 
sys.path.append(base_parent)

import os,collections,sys, time, ConfigParser,tarfile,random,logging,string,getopt,json
from threading import Thread
from Queue import *
from django.db import models
from django.conf import settings
from django.db.models import Q
from django.contrib import messages
from django.db import transaction
from datetime import datetime
from pytz import timezone
from archiver.models import Archives,ArchiveRetrieve

from glacier.glacier import Connection as GlacierConnection
from glacier.vault import Vault as GlacierVault
from glacier.archive import Archive as GlacierArchive

NUM_PROCS=1
TEMP_DIR="/tmp"
TEMP_RESTORE_DIR="/mnt/tmp/restore"
ACCESS_KEY=""
SECRET_ACCESS_KEY=""
GLACIER_VAULT=None
GLACIER_REALM=""
DEBUG_MODE=False
DRYRUN=False
SEARCHSTRING=None
ARCHIVEID=None

logger=logging.getLogger(__name__)
queue = Queue()

def startJob(vault=None,archive_id=None):
    try:
        my_glacier = GlacierConnection(ACCESS_KEY,SECRET_ACCESS_KEY,region=GLACIER_REALM)
    except Exception,exc:
        print ("Error startJob: %s" % exc)
        logger.error("Error startJob: %s" % exc)
        sys.exit(2)

    try:
        example_vault = my_glacier.get_vault(vault)
    except Exception,exc:
        print ("Error startJob get vault: %s" % exc)
        logger.error("Error startJob get vault: %s" % exc)
        sys.exit(2)

    try:
        job_id = example_vault.initiate_job("archive-retrieval",archive=GlacierArchive(archive_id))
    except Exception,exc:
        if len(exc.args)>1:
                x,y=exc.args
        	print ("Error startJob initiate: %s (%s)" % (json.loads(y.read()),archive_id))
        else:
                print "Error startjob initiate: %s" % (str(exc))
        sys.exit(1)

    try:
        a=ArchiveRetrieve()
        a.archive_retrieve(job_id=job_id,archive_id=archive_id)
    except Exception,exc:
        print ("Error startJob db: %s" % exc)
        logger.error("Error startJob db: %s" % exc)
        sys.exit(2)

    #hand stuff over to daemon to keep checking
        #when done, download and untar and delete
        #make ArchiveRetrieve to done 
        

def main(argv):
    #set up all of the variables
    global NUM_PROCS,TEMP_RESTORE_DIR,ACCESS_KEY,SECRET_ACCESS_KEY,GLACIER_VAULT,NUMFILES,ARCHIVEMB,GLACIER_REALM,ARCHIVEID
    NUM_PROCS=settings.NUM_PROCS
    TEMP_DIR=settings.TEMP_DIR
    ACCESS_KEY=settings.ACCESS_KEY
    SECRET_ACCESS_KEY=settings.SECRET_ACCESS_KEY
    GLACIER_VAULT=settings.GLACIER_VAULT
    GLACIER_REALM=settings.GLACIER_REALM
    NUMFILES=settings.NUMFILES
    ARCHIVEMB=settings.ARCHIVEMB
    TEMP_RESTORE_DIR=settings.TEMP_RESTORE_DIR

    try:
        opts, args = getopt.getopt(argv, "hs:rda:", [
                                "help", 
                                "searchstring=",
                                "dryrun",
                                "debug",
                                "archiveid="
                            ])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    
    #make sure file exists

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-d","--debug"):
            global DEBUG_MODE
            DEBUG_MODE=True
        elif opt in ("-s", "--search"):
            global SEARCHSTRING
            SEARCHSTRING = arg
        elif opt in ("-a","--archiveid"):
            global ARCHIVEID
            ARCHIVEID=arg
        elif opt in ("-r","--dryrun"):
            global DRYRUN
            DRYRUN=True
    
    #set up logging
    global logger
    if DEBUG_MODE:
        print "DEBUG MODE"
    
    if ARCHIVEID:
        try:
            arc = Archives.objects.get(archive_id=ARCHIVEID)
            startJob(arc.vault,arc.archive_id)
            print "%s,%s" % (arc.vault,arc.archive_id)
        except Exception,exc:
            print "Invalid ArchiveID!"
            sys.exit(2)
    
    
    searchrecord=[]
    if SEARCHSTRING:
        searchresults = Archives.objects.archive_search(SEARCHSTRING)
        for r in searchresults:
            searchrecord.append(r.object)
    elif ARCHIVEID:
        pass    
    else:
        searchresults = Archives.objects.all()
        for r in searchresults:
            if r.archive_id:
                searchrecord.append(r)
            
    if DRYRUN:
        for r in searchrecord:
            print "%s,%s" % (r.vault,r.archive_id)
        sys.exit(2)
    elif ARCHIVEID:
        pass
    else:
        for r in searchrecord:
	    print "ArchiveId: %s" % (r.archive_id)
            startJob(r.vault,r.archive_id)    

def usage():
    print 'findAndRetrieveFiles.py -- find files and put them somewhere.'
    print 
    print 'findAndRetrieveFiles.py [options]'
    print 
    print 'options:'
    print ' -h|--help'
    print ' -d|--debug'
    print ' -s|--search= search string. Put \" \" around exact searches, - before NOT words. eg | quick brown \"fox jumped\" -dogs | would find instances of quick, brown and \"fox jumped\" without instances of \"dogs\". '
    print ' -r -- dry run. Just return vaults and archive_ids (csv)'
    print ' -a| --archiveid= archiveID to get. All other options are ignored.'
    print

if __name__ == "__main__":
    main(sys.argv[1:])
