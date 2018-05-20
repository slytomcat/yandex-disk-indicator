#!/bin/bash

./prepare.sh

./cl_create.sh

cd yd-tools*/
debuild -S -k0x25DAD03F -pgpg2
cd ..

dput ppa:slytomcat/ppa yd-tools_*_source.changes

./clean.sh
