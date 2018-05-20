#!/bin/bash

# prepare changelog
version=$(sed -n "/appVer = '.*'/p" ../yandex-disk-indicator.py | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+')
#series='artful'
#series='bionic'
#series='trusty'
series='xenial'
#series='zesty'

clear

sed "s/@series/$series/" changelog > yd-tools/debian/changelog
sed -i "s/@version/$version/" yd-tools/debian/changelog
sed -i "s/@date/$(date -R)/" yd-tools/debian/changelog
cat yd-tools/debian/changelog 
