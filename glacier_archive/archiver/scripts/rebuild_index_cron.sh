#!/bin/bash
ARCHIVE_HOME=/home/bernz/workspace/glacier-archive/glacier_archive
export DJANGO_SETTINGS_MODULE="glacier_archive.settings"

cd $ARCHIVE_HOME
python manage.py rebuild_index --noinput