from celery import Celery
import os, sys,json,logging 
base = os.path.dirname(os.path.dirname(__file__)) 
base_parent = os.path.dirname(base) 
sys.path.append(base) 
sys.path.append(base_parent)
logger=logging.getLogger(__name__)

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

celery = Celery('tasks', broker='redis://localhost')

@celery.task
@transaction.commit_manually
def archiveFilesTask (tempTarFile=None,job=None,DEBUG_MODE=False,DESCRIPTION="",TAGS=[]):
    from archiver.archiveFiles import makeTar,uploadToGlacier
    global logger
    global NUM_PROCS,TEMP_DIR,ACCESS_KEY,SECRET_ACCESS_KEY,GLACIER_VAULT,NUMFILES,ARCHIVEMB,GLACIER_REALM,USECELERY
    NUM_PROCS=settings.NUM_PROCS
    TEMP_DIR=settings.TEMP_DIR
    ACCESS_KEY=settings.ACCESS_KEY
    SECRET_ACCESS_KEY=settings.SECRET_ACCESS_KEY
    GLACIER_VAULT=settings.GLACIER_VAULT
    NUMFILES=settings.NUMFILES
    ARCHIVEMB=settings.ARCHIVEMB
    GLACIER_REALM=settings.GLACIER_REALM
    USECELERY=settings.USECELERY
        
    print "Got job %s-files" % len(job)
    try:
        c = Archives().archive_create(short_description=DESCRIPTION,tags=TAGS,vault=GLACIER_VAULT)
        sid = transaction.savepoint()
        if DEBUG_MODE:
            logger.debug("Created archive in DB")
        #add files to temp archive on disk
        try:
            #add each to tarchive
            makeTar(job,tempTarFile)
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
            transaction.commit()
            if DEBUG_MODE:
                logger.debug("done task: %s " % tempTarFile)
        except Exception,exc:
            logger.error('Error creating archive %s' % exc)
            transaction.rollback()
    except Exception,exc:
        logger.error('Error creating archive %s' % exc)
        transaction.rollback()
    return