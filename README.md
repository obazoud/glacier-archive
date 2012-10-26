glacier-archive
===========================

Right now, a commandline tool for dumping files (smartly and multi-threadedly) from a filesystem to Glacier. Then another commandline tool for finding your files and getting your stuff back out of Glacier.

The database (anything Django compatible) becomes the crux of your archival solution. It really needs to be backed-up/secure. That's the only way you'll find your files.

This is meant to be a full, scalable archival solution. If you just have a few big files, there are better solutions. But if you have millions or billions, you'll need a way to deal with finding them again.

Requirements
===========================
Python 2.7+

Django 1.4+ (and some knowledge about basic Django setup. Yes, I know this is command-line, but it was the fastest path to a good DB/search)

Haystack w/Search of Choice (I picked elasticsearch). Use latest Haystack beta  

Glacier libraries for Python (https://github.com/paulengstler/glacier). You might want to use my fork.  

Boto w/Glacier libraries (2.6.0).  

Celery and Redis if you're doing multi-threading. (celery-with-redis)  

Django Settings File
===========================
NUM_PROCS -- Default 2, The number of processors (and thus threads) to spawn.  
TEMP_DIR -- Default "/mnt/tmp". The place to put tar files while they're being bundled before sent to Glacier. Needs enough space for the ARCHIVEMB x NUM_PROCS  
TEMP_RESTORE_DIR -- Default "/mnt/tmp/restore". The place where tar files will go and be unpacked after coming in from Glacier.
ACCESS_KEY="XXXX" - AWS Access Key  
SECRET_ACCESS_KEY="XXXX" - AWS Secret Access Key  
GLACIER_VAULT="glaciervault" - Default "glaciervault"  
ELASTICSEARCH - Default True, using ElasticSearch  
NUMFILES - Default 1000 - Number of files per tarball. This tells the system how many files should be in each tarball. If you point it at a tree of a million files, it'll make 1000 tarballs and upload them to Glacier.  
ARCHIVEMB - Default 500 - Number of MB per tarball. When 500MB in a tarball are exceeded, it closes that tarball and moves to a new one. If you have 10 1GB files, it'll make 10 Tarballs. It won't split files.  
HAYSTACK_CONNECTIONS - By default, it's set up for elasticsearch. Configure it for your needs.  
CHECKSECONDS - (600) - The number of seconds to wait between checking for finished archive retrieval tasks.  
USECELERY=True  - Use Celery for multithreaded queues. Currently multithreading with Haystack is broken so if you're going to use multithreads, use this. Requires you to set-up Celery.  

AD_LDAP = "ldap://xxxx" - If doing extended attributes, used for lookups.  
AD_DN = "name@xxx.xxx" - If doing extended attributes, used for lookups.  
AD_PW = "password" - If doing extended attributes, used for lookups.  
AD_BASE = "dc=xxx,dc=xxx" - If doing extended attributes, used for lookups.  


celeryconfig.py settings file  
=================================
BROKER_URL = 'redis://localhost:6379/0'  - Broker URL. Redis by default.  
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0' - Broker Backend. Redis by default.  

Setup
=========================
Make sure your DB is on. After setting your settings.py file to the stuff you want (glacier_archive/glacier_archive/settings.py), execute:  
```
python manage.py syncdb --noinput
```
Which sets up all of the DB tables. This assumes that you'll just use the provided command-line tools.

If you think that you'll use the (future) Web or API Interfaces, run:
```
python manage.py syncdb
```
A follow the on-screen instructions for creating a root user.  

If you're familiar with Django, you can set up the (not-very-exciting) web interface. 

Usage
===========================
Crawl a tree and put stuff in AWS Glacier and keep a searchable record of files and archives in a Database:

```
python archiver/archiveFiles.py [options] filepath

options:
-r recursive
-d debug to logger (configured in django settings)
-s <text> a short description of your archival set
-t <comma list> tags used to find your data later
-x <integer> # of days a file's atime is older than now() to include it in the archive. If selected, archive will only include detected files.
-z <integer> # of days a file's atime is newer to include it in the archive. If selected, archive will only include detected files.  
-n dry run
-e capture extended cifs attributes  
-f capture extended nfs4 attributes  
filepath 

example:
python archiver/archiveFiles.py -r -d -s "TEST" -t "TEST1,test2" /home/bernz/Downloads
```

Indexing
=======================
Go into archiver/scripts and alter the rebuild_index_cron.sh script. Alter the line:  
ARCHIVE_HOME=/home/bernz/workspace/glacier-archive/glacier_archive  
with wherever your package lives.

Then activate the archiver/scripts/rebuild_index_cron.sh via your cron or scheduler. It will rebuild the indexes that often.

Indexing is key to finding your files after you've archived them (via filepath, tags or description). Otherwise you'll have to rely on the DB.

Finding your stuff
=======================
```
$ python archiver/findAndRetrieveFiles.py --help
findAndRetrieveFiles.py -- find files and put them somewhere.

findAndRetrieveFiles.py [options]

options:
 -h|--help
 -d|--debug
 -s|--search= search string. Put " " around exact searches, - before NOT words. eg | quick brown "fox jumped" -dogs | would find instances of quick, brown and "fox jumped" without instances of "dogs". 
 -a|--archiveid= archive id to be gotten. All other specification options are ignored.
 -r -- dry run. Just return vaults and archive_ids (csv)

```
Be careful! If you don't specify -r, the jobs are initiated in Amazon which might be costly!  
Also if you don't have search terms or a specific ArchiveId (-a), it will try to grab everything!

Once you start the Daemon (see below), it will check and see if your downloaded stuff is done.

Getting your stuff
=======================
Start the Daemon.

```
sudo nohup python archiver/FindDaemon.py &
```
This runs every 600 seconds (10 minutes. Change in settings.py). It checks the jobs in your database and sees if they're done. If they're done, it grabs the tar archive and throws it into TEMP_RESTORE_DIR.

ToDo
==========================
API for archive.

Scripts to do retention. (when files are archived, delete archived files)

Integrate with NoSQL backend.