#!/bin/bash

version=$(sed -n "/appVer = '.*'/p" ../yandex-disk-indicator.py | grep -o '[0-9]\.[0-9]\.[0-9]')

serie='xenial'

clear

./prepare.sh
  
sed "s/@serie/$serie/" changelog > yd-tools/debian/changelog
sed -i "s/@version/$version/" yd-tools/debian/changelog
sed -i "s/@date/$(date -R)/" yd-tools/debian/changelog
cat yd-tools/debian/changelog 

cd yd-tools/
debuild --no-lintian -S -k0x25DAD03F
cd ..

dput ppa:slytomcat/ppa yd-tools_*_source.changes

./clean.sh
