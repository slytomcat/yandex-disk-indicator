#!/bin/bash

export TARGET="yd-tools/usr"
./prepare.sh

./cl_create.sh

cd yd-tools*/
debuild -S -k0x4EA45931DE1209A8C1017902EFD4B73225DAD03F -pgpg2
cd ..

dput ppa:slytomcat/ppa yd-tools_*_source.changes

./clean.sh
