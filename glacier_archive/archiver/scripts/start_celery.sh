#!/bin/bash
ARCHIVE_HOME=/home/bernz/workspace/glacier-archive/glacier_archive
export DJANGO_SETTINGS_MODULE="glacier_archive.settings"
NUM_PROCS=4

cd $ARCHIVE_HOME
nohup celery -A archiver.tasks worker -c $NUM_PROCS --loglevel=info &
