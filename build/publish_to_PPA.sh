#!/bin/bash

./prepare.sh
  
cd yd-tools*/
debuild -S -k0x25DAD03F
cd ..

dput ppa:slytomcat/ppa yd-tools_*_source.changes

./clean.sh
