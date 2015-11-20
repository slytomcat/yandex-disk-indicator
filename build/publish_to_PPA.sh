./prepare.sh
./make_source.changes.sh

dput ppa:slytomcat/ppa yd-tools_*_source.changes

./clean.sh
