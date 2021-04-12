#!/bin/bash

export TARGET="yd-tools/usr"
./prepare.sh

./cl_create.sh

cd yd-tools*/
debuild --no-tgz-check -k0x4EA45931DE1209A8C1017902EFD4B73225DAD03F -pgpg2
cd ..

echo "Don't forget to run ./clean.sh to clean buid directory"