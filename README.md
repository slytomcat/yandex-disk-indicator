### **![yandex-disk-indicator](https://github.com/slytomcat/yandex-disk-indicator/blob/master/icons/yd-128.png)**
# yandex-disk-indicator
Desktop panel indicator for YandexDisk CLI client for Linux

INSTALLATION:

Note that yandex-disk CLI utility have to be installed before the indicator. Visit https://yandex.com/support/disk/cli-clients.xml#cli-install for instructions.

Installation from Github: 

 1. Download ZIP with project sources (either master branch or last releaze)

 2. Run build/install.sh script.

Installation from Launchpad PPA: 
 - Visit PPA: https://launchpad.net/~slytomcat/+archive/ubuntu/ppa and follow the instructions.


NOTES:

Code assumes that:
- yandex-disk-indicator.py is copied to /usr/bin/yandex-disk-indicator and marked as executable (chmod a+x ...)
- fm-actions/ and icons/ folders, ya-setup files are located in /usr/share/yd-tools
- *.desktop files should be placed in /usr/share/applications folder
- compiled language files (translations/*.mo) are located in the system depended folders (i.e. usr/share/locale/{LANG}/LC_MESSAGES/ in Linux)
- indicator settings are stored in ~/.config/yd-tools/yandex-disk-indicator.conf (file is automatically created on the first start).

build - everything that need to build the .deb package or source.changes file (only change key for signatures). Additional tools are required: devscripts, debhelper and dput (if you want to upload package, for example, to launcpad PPA).

See the wiki page for details: https://github.com/slytomcat/yandex-disk-indicator/wiki.
