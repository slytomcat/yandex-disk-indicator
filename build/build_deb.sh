#!/bin/bash

export TARGET="yd-tools/usr"
./prepare.sh

./cl_create.sh

cd yd-tools*/
debuild --no-tgz-check -k0x25DAD03F -pgpg2
cd ..

echo "Don't forget to run ./clean.sh to clean buid directory"