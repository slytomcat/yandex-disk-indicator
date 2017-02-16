#!/bin/bash
sleep 2
cd yd-tools/
rm -r usr
rm -r debian/yd-tools*
rm -r debian/debhelper*
rm debian/files
cd ..
rm yd-tools_*

