import os, math,logging,random,string,gc,subprocess
from datetime import timedelta
from datetime import datetime
logger=logging.getLogger(__name__)
from archiver.models import Archives,ArchiveFiles,UserCache,Crawl
from archiver.tasks import archiveFilesTask as af
from django.db import models
from django.conf import settings
from pytz import timezone
from time import sleep
if settings.CIFSPERMS:
	from cifsacl import getfacl

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
	description=""
	debug=False
	tags=[]
	dry=False
	temp_dir=""
	totaljobsize=0
	crawlid=None
	crawlobj=None
	filelist = []

	def __init__(self, filepath=None,recurse=False,numfiles=1000,archivemb=500,queue=queue,usecelery=False,extendedcifs=False,description="",debug=False,tags=None,dry=False,temp_dir=""):
		self.filepath=filepath
		self.recurse=recurse
		self.numfiles=numfiles
		self.archivemb=archivemb
		self.queue=queue
		self.usecelery=usecelery
		self.extendedcifs=extendedcifs
		self.description=description
		self.debug=debug
		self.tags=tags
		self.dry=dry
		self.temp_dir=temp_dir
		crawl = Crawl(crawlpath=filepath)
		crawl.save()
		self.crawlobj=crawl
		self.crawlid=crawl.id

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
		perms=[]
		gc.collect()
		from archiver.archiveFiles import id_generator 
		kilo_byte_size = self.arraysize/1024
		mega_byte_size = kilo_byte_size/1024
		if self.extendedcifs:
			perms = self.buildPerms(perms,rfile)
			
		if len(self.jobarray)<self.numfiles and mega_byte_size<self.archivemb:
			self.jobarray.append({"rfile":rfile,"perms":perms})
			self.arraysize = self.arraysize+statinfo.st_size
		else:
			jobcopy = self.jobarray
			if self.usecelery:
				#self.alljobs.append(jobcopy)
				id_gen = self.temp_dir+"/"+id_generator(size=16)
				af.apply_async(args=[id_gen, jobcopy,self.debug,self.description,self.tags,self.dry,self.extendedcifs,self.crawlid])
				del jobcopy[:]
				gc.collect()
			else:
				self.queue.put(jobcopy)
			self.totaljobsize=self.arraysize+self.totaljobsize
			del self.jobarray[:]
			gc.collect()
			self.jobarray=[]
			self.arraysize=0
			self.jobarray.append({"rfile":rfile,"perms":perms})
			self.arraysize = self.arraysize+statinfo.st_size
		self.filelist.remove(rfile)
	
	def recurseCrawl(self,filepath=filepath):
		global logger
		from archiver.archiveFiles import id_generator
		for (path, dirs, files) in os.walk(filepath):
			for fi in files:
				kilo_byte_size = self.arraysize/1024
				mega_byte_size = kilo_byte_size/1024
				rfile = os.path.join(path,fi)
				if os.path.islink(rfile):
					continue
				statinfo = os.stat(rfile)
				if self.oldertime>0 or self.newertime>0:
					dateatime = datetime.fromtimestamp(statinfo.st_mtime)
					#datemtime = datetime.fromtimestamp(statinfo.st_mtime)
					if self.oldertime>0 and self.newertime>0:
						#between
						if (dateatime < (datetime.now() - timedelta(days=self.oldertime))) and (dateatime > (datetime.now() - timedelta(days=self.newertime))):
							self.filelist.append(rfile)
							self.addFile(rfile,statinfo)
							continue
					elif self.oldertime>0 and self.newertime==0:
						#print "%s %s" % (dateatime, (datetime.now() - timedelta(days=self.oldertime)))
						if (dateatime < (datetime.now() - timedelta(days=self.oldertime))):
							self.filelist.append(rfile)
							self.addFile(rfile,statinfo)
							continue
					elif self.oldertime==0 and self.newertime>0:
						if (dateatime > (datetime.now() - timedelta(days=self.newertime))):
							self.filelist.append(rfile)
							self.addFile(rfile,statinfo)
							continue
					else:
						continue
				else:
					self.filelist.append(rfile)
					self.addFile(rfile,statinfo)
		jobcopy = self.jobarray
		if self.usecelery:
			if len(jobcopy)>0:
				#self.alljobs.append(jobcopy)
				id_gen=self.temp_dir+"/"+id_generator(size=16)
				af.apply_async(args=[id_gen, jobcopy,self.debug,self.description,self.tags,self.dry,self.extendedcifs,self.crawlid])
		else:	
			if len(jobcopy)>0:
				self.queue.put(jobcopy)
		self.totaljobsize=self.totaljobsize+self.arraysize
		logger.info("Done crawl %s %s %s bytes" % (filepath,self.crawlid,self.totaljobsize))			
		return	
