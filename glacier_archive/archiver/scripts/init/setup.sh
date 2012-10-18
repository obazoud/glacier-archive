#!/bin/bash

rm -rf /etc/init.d/celerybeat
rm -rf /etc/init.d/celeryevcam
rm -rf /etc/init.d/celeryd
rm -rf /etc/default/celeryd
cp -rfp celerybeat /etc/init.d/celerybeat
chmod +x /etc/init.d/celerybeat
cp -rfp celeryd /etc/init.d/celeryd
chmod +x /etc/init.d/celeryd
cp -rfp celeryevcam /etc/init.d/celeryevcam
chmod +x /etc/init.d/celeryevcam
cp -rfp celeryd.conf /etc/default/celeryd
cp -rfp celerybeat.conf /etc/default/celerybeat
cp -rfp celeryev.conf /etc/default/celeryev
