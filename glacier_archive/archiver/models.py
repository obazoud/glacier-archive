from django.db import models
from django.contrib.auth.models import User,Group
from datetime import datetime
from django.conf import settings
from pytz import timezone
from haystack.query import SearchQuerySet
from taggit.managers import TaggableManager
from cifsacl import getfacl
from guardian.shortcuts import assign,remove_perm

import logging,string,random,ldap
logger = logging.getLogger(__name__)

class ArchiveManager(models.Manager):
    def archive_search(self,searchquery):
        sqs = SearchQuerySet().auto_query(searchquery).models(Archives)
        return sqs

class Archives(models.Model):
    archive_id = models.CharField(max_length=1000)
    startdate = models.DateTimeField(blank=True,null=True,auto_now=True)
    filecount = models.IntegerField(blank=True,null=True)
    bytesize = models.BigIntegerField(blank=True,null=True)
    short_description = models.CharField(max_length=250,blank=True,null=True)
    vault = models.CharField(max_length=100,blank=True,null=True)
    
    tags = TaggableManager(blank=True)
    objects = ArchiveManager()

    class Meta:
        app_label = 'archiver'

    def __unicode__(self):
        return self.archive_id
    
    def archive_create(self,short_description=None,tags=None,vault=None):
        self.short_description=short_description
        self.startdate=datetime.now(timezone(settings.TIME_ZONE))
        self.vault=vault
        self.save()
        for tag in tags:
            self.tags.add(tag)
        self.save()
        return self

    def update_archive_id(self,archive_id):
        self.archive_id=archive_id
        self.save()

class ArchiveFiles(models.Model):
    archive = models.ForeignKey(Archives)
    startdate = models.DateTimeField(blank=True,null=True,auto_now=True)
    bytesize = models.BigIntegerField(blank=True,null=True)
    filepath = models.CharField(max_length=2000)
    fileadate = models.DateTimeField(blank=True,null=True)
    filemdate = models.DateTimeField(blank=True,null=True)
    filecdate = models.DateTimeField(blank=True,null=True)

    class Meta:
        app_label = 'archiver',
        permissions = (
                ('read', 'read file'),
                ('write', 'write file'),
                ('own', 'own file'),
        )    

    def __unicode__(self):
        return self.filepath
    
    def archivefile_create(self,filepath=None,bytesize=0,fileadate=None,filemdate=None,filecdate=None,archive=None):
        self.archives = archive
        self.filepath=filepath
        self.startdate=datetime.now(timezone(settings.TIME_ZONE))
        self.fileadate = fileadate
        self.filemdate = filemdate
        self.filecdate = filecdate
        self.bytesize = bytesize
        self.save()
        
    
class ArchiveRetrieve(models.Model):
    archive_id = models.CharField(max_length=1000)
    startdate = models.DateTimeField(blank=True,null=True,auto_now=True)
    job_id = models.CharField(max_length=1000)
    ready = models.BooleanField(default=False,blank=True)
    downloaded = models.BooleanField(default=False,blank=True)
    archive_obj = models.ForeignKey('Archives')

    class Meta:
        app_label = 'archiver'

    def __unicode__(self):
        return self.jobid
    
    def archive_retrieve(self,job_id=None,archive_id=None):
        self.job_id=job_id
        self.archive_id=archive_id
        self.startdate=datetime.now(timezone(settings.TIME_ZONE))
        self.ready=False
        self.downloaded=False
        self.archive_obj=Archives.objects.get(archive_id=archive_id)
        self.save()

def resolveUsernameOrGroup(sid):
    con = ldap.initialize(settings.AD_LDAP)
    dn = settings.AD_DN
    pw = settings.AD_PW
    base = settings.AD_BASE
    retrieve_attributes=["sAMAccountName","objectClass"]
    #retrieve_attributes = None
    scope = ldap.SCOPE_SUBTREE
    con.set_option(ldap.OPT_REFERRALS, 0)
    con.simple_bind_s(dn,pw)
    filter = "objectSid=" + sid
    result_id = con.search_s( base, ldap.SCOPE_SUBTREE, filter, retrieve_attributes )
    try:
        name =  result_id[0][1]["sAMAccountName"][0]
        utype = result_id[0][1]["objectClass"][1]
        return (name,utype)
    except:
        return None
    
    
class UserCache(models.Model):
    user_obj = models.CharField(max_length=100,unique=True)
    user_sid = models.CharField(max_length=100,unique=True)
    user_class = models.CharField(max_length=10,blank=True,null=True)

    class Meta:
        app_label = 'archiver'

    def __unicode__(self):
        return self.user_obj.username
    
    def lookupSID(self,user_sid=None):
        try:
            uc = UserCache.objects.get(user_sid=user_sid)
            return (uc.user_obj,uc.user_class)
        except UserCache.DoesNotExist:
            try:
                us = resolveUsernameOrGroup(user_sid)
                if us[1]=="user":
                    try:
                        u = User.objects.get(username=us[0])
                    except:
                        u = User.objects.create_user(username=us[0])

                if us[1]=="group":
                    try:
                        g = Group.objects.get(username=us[0])
                    except:
                        try:
                            g = Group(groupname=us[0])
                            g.save()
                        except:
                            pass

                uc = UserCache(user_obj=us[0],
                               user_sid=user_sid,
                               user_class=us[1])
                uc.save()
                return (uc.user_obj,uc.user_class)
            except:
                try:
                    uc = UserCache.objects.get(user_sid=user_sid)
                    return (uc.user_obj,uc.user_class)
                except Exception,exc:
                    logger.error("cannot create UserCache")
                    return None