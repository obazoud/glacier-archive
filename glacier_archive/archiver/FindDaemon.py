import os,collections,sys, time, ConfigParser,tarfile,random,logging,string,getopt,json
base = os.path.dirname(os.path.dirname(__file__)) 
base_parent = os.path.dirname(base) 
sys.path.append(base) 
sys.path.append(base_parent)

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

TEMP_RESTORE_DIR="/mnt/tmp/restore"
ACCESS_KEY=""
SECRET_ACCESS_KEY=""
GLACIER_VAULT=None
GLACIER_REALM=""
RUNNING=False
CHECKSECONDS=600

logger=logging.getLogger(__name__)

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))

@transaction.commit_on_success
def scan_for_task():
    global TEMP_RESTORE_DIR,ACCESS_KEY,SECRET_ACCESS_KEY,GLACIER_VAULT,GLACIER_REALM,logger
    my_glacier=None
    try:
        ar = ArchiveRetrieve.objects.filter(ready=False)
        if ar:
            try:
                my_glacier = GlacierConnection(ACCESS_KEY,SECRET_ACCESS_KEY,region=GLACIER_REALM)
            except Exception,exc:
                print "Error scan conn: %s" % (exc)
                logger.error("Error scan conn: %s" % (exc))
                transaction.rollback()
                sys.exit(2)
        
        for a in ar:
            glacier_vault = my_glacier.get_vault(a.archive_obj.vault)
            gjson = glacier_vault.describe_job(a.job_id)
            if gjson["Completed"]=="true" and gjson["Action"]=="ArchiveRetrieval":
                try:
                    RUNNING=True
                    a.ready=True
                    a.save()
                    vault_file = glacier_vault.get_job_output(a.job_id)
                    with open(TEMP_RESTORE_DIR+"/"+id_generator(size=16), 'wb') as of:
                        while True:
                            x = vault_file.read(4096)
                            if len(x) == 0:
                                break
                            of.write(x)
                    a.downloaded=True
                    a.save()
                    transaction.commit()
                    RUNNING=False                    
                except Exception,exc:
                    logger.error("Error downloading %s" % exc)
                    transaction.rollback()
                    RUNNING=False
            elif gjson["Completed"]=="false":
                continue                
    except Exception,exc:
        if len(exc.args)>1:
            x,y=exc.args
            print ("Error in scan: %s" % (json.loads(y.read())))
        else:
            print "Error in scan: %s" % (str(exc))
        logger.error("Error in scan: %s" % (exc))
        transaction.rollback()
        sys.exit(2)

def run():
    global TEMP_RESTORE_DIR,ACCESS_KEY,SECRET_ACCESS_KEY,GLACIER_VAULT,GLACIER_REALM,CHECKSECONDS
    ACCESS_KEY=settings.ACCESS_KEY
    SECRET_ACCESS_KEY=settings.SECRET_ACCESS_KEY
    GLACIER_VAULT=settings.GLACIER_VAULT
    GLACIER_REALM=settings.GLACIER_REALM
    TEMP_RESTORE_DIR=settings.TEMP_RESTORE_DIR
    CHECKSECONDS=settings.CHECKSECONDS

    while True:
        scan_for_task()
        time.sleep(CHECKSECONDS)
        

if __name__ == "__main__":
    run()