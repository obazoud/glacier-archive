import os, math,logging
from datetime import timedelta
from datetime import datetime
logger=logging.getLogger(__name__)

class Crawler(object):
    """ Crawler API """
    jobarray=[]
    filepath=""
    arraysize=0
    recurse=False
    queue=None    
    newertime=0
    oldertime=0

    def __init__(self, filepath=None,recurse=False,numfiles=1000,archivemb=500,queue=queue):
        self.filepath=filepath
        self.recurse=recurse
        self.numfiles=numfiles
        self.archivemb=archivemb
        self.queue=queue
    
    def set_newer(self,newertime=0):
        self.newertime=newertime

    def set_older(self,oldertime=0):
        self.oldertime=oldertime

    def addFile(self,rfile,statinfo):
        kilo_byte_size = self.arraysize/1024
        mega_byte_size = kilo_byte_size/1024
        
        if len(self.jobarray)<self.numfiles and mega_byte_size<self.archivemb:
            self.jobarray.append(rfile)
            self.arraysize = self.arraysize+statinfo.st_size
            #continue
        else:
            jobcopy = self.jobarray
            self.queue.put(jobcopy)
            self.jobarray=[]
            self.arraysize=0
            self.jobarray.append(rfile)
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
        if len(jobcopy)>0:
            self.queue.put(jobcopy)
            
        logger.debug("Done crawl "+filepath)
            
        return    