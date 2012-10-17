import os, math,logging
from datetime import timedelta
from datetime import datetime
logger=logging.getLogger(__name__)
from cifsacl import getfacl
from archiver.models import Archives,ArchiveFiles,UserCache

class Crawler(object):
    """ Crawler API """
    jobarray=[]
    filepath=""
    arraysize=0
    recurse=False
    queue=None    
    newertime=0
    oldertime=0
    alljobs=[]
    usecelery=False
    extendedcifs=False

    def __init__(self, filepath=None,recurse=False,numfiles=1000,archivemb=500,queue=queue,usecelery=False,extendedcifs=False):
        self.filepath=filepath
        self.recurse=recurse
        self.numfiles=numfiles
        self.archivemb=archivemb
        self.queue=queue
        self.usecelery=usecelery
        self.extendedcifs=extendedcifs
        
    def buildPerms(self,perms,rfile):
        gf = getfacl(rfile)
        counter = 0
        for perm in gf:
            permhash={}
            if counter==0:
                uc = UserCache().lookupSID(str(perm))
                try:
                    name =  uc[0]
                    type = uc[1]
                    permhash={"role":"owner","name":name,"type":type}
                except:
                    name = "root"
                    type = "person"
                    permhash={"role":"owner","name":name,"type":type}
                perms.append(permhash)                
            elif counter==1:
                uc = UserCache().lookupSID(user_sid=str(perm))
                try:
                    name =  uc[0]
                    type = uc[1]
                except:
                    name = "root"
                    type = "group"
                permhash={"role":"group","name":name,"type":type}
                perms.append(permhash)                
            else:
                permstring = str(perm)
                sid = permstring[0:permstring.find('::')]
                uc = UserCache().lookupSID(user_sid=sid)
                try:
                    name = uc[0]
                    type = uc[1]
                    role = permstring[permstring.rfind('::')+2:len(permstring)]
                    permhash={"role":role,"name":name,"type":type}
                    perms.append(permhash)
                except:
                    pass                
            counter=counter+1
        return perms    
    
    def set_newer(self,newertime=0):
        self.newertime=newertime

    def set_older(self,oldertime=0):
        self.oldertime=oldertime

    def addFile(self,rfile,statinfo):
        kilo_byte_size = self.arraysize/1024
        mega_byte_size = kilo_byte_size/1024
        perms=[]
        if self.extendedcifs:
            perms = self.buildPerms(perms,rfile)
            
        if len(self.jobarray)<self.numfiles and mega_byte_size<self.archivemb:
            self.jobarray.append({"rfile":rfile,"perms":perms})
            self.arraysize = self.arraysize+statinfo.st_size
            #continue
        else:
            jobcopy = self.jobarray
            if self.usecelery:
                self.alljobs.append(jobcopy)
            else:
                self.queue.put(jobcopy)
            self.jobarray=[]
            self.arraysize=0
            self.jobarray.append({"rfile":rfile,"perms":perms})
            self.arraysize = self.arraysize+statinfo.st_size

    
    def recurseCrawl(self,filepath=filepath):
        global logger
        for (path, dirs, files) in os.walk(filepath):
            for fi in files:
                kilo_byte_size = self.arraysize/1024
                mega_byte_size = kilo_byte_size/1024
                rfile = os.path.join(path,fi)
                statinfo = os.stat(rfile)
                if self.oldertime>0 or self.newertime>0:
                    dateatime = datetime.fromtimestamp(statinfo.st_mtime)
                    #datemtime = datetime.fromtimestamp(statinfo.st_mtime)
                    if self.oldertime>0 and self.newertime>0:
                        #between
                        if (dateatime < (datetime.now() - timedelta(days=self.oldertime))) and (dateatime > (datetime.now() - timedelta(days=self.newertime))):
                            self.addFile(rfile,statinfo)
                            continue
                    elif self.oldertime>0 and self.newertime==0:
                        #print "%s %s" % (dateatime, (datetime.now() - timedelta(days=self.oldertime)))
                        if (dateatime < (datetime.now() - timedelta(days=self.oldertime))):
                            self.addFile(rfile,statinfo)
                            continue
                    elif self.oldertime==0 and self.newertime>0:
                        if (dateatime > (datetime.now() - timedelta(days=self.newertime))):
                            self.addFile(rfile,statinfo)
                            continue
                    else:
                        continue
                else:
                    self.addFile(rfile,statinfo)

        jobcopy=[]
        jobcopy = self.jobarray
        if self.usecelery:
            if len(jobcopy)>0:
                self.alljobs.append(jobcopy)
        else:    
            if len(jobcopy)>0:
                self.queue.put(jobcopy)
            
        logger.debug("Done crawl "+filepath)
            
        return    
