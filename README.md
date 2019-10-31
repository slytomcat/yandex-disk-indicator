### **![yandex-disk-indicator](https://github.com/slytomcat/yandex-disk-indicator/blob/master/icons/yd-128.png)**
# yandex-disk-indicator
[![license](https://img.shields.io/badge/license-GPL%20v.3-green.svg)](https://github.com/slytomcat/yandex-disk-indicator/blob/master/LICENSE)
[![wiki](https://img.shields.io/badge/wiki-available-green.svg)](https://github.com/slytomcat/yandex-disk-indicator/wiki)
[![PPA](https://img.shields.io/badge/PPA-available-green.svg)](https://launchpad.net/~slytomcat/+archive/ubuntu/ppa)

[![DeepSource](https://static.deepsource.io/deepsource-badge-light.svg)](https://deepsource.io/gh/slytomcat/yandex-disk-indicator/?ref=repository-badge)

Desktop panel indicator for YandexDisk CLI client for Linux

INSTALLATION:

See installation instruction in [Wiki](https://github.com/slytomcat/yandex-disk-indicator/wiki)

INTERFACE LANGUAGES

English, Russian, Greek, Bulgarian, Belorussian.

Everybody welcome to translate it to other languages!  


NOTES:

Indicator code assumes that:
- yandex-disk-indicator.py is copied to /usr/bin/yandex-disk-indicator and marked as executable (chmod a+x ...)
- fm-actions/ and icons/ folders, ya-setup files are located in /usr/share/yd-tools folder
- *.desktop files were placed in /usr/share/applications folder
- compiled language files (translations/*.mo) are located in the system depended folders (i.e. usr/share/locale/{LANG}/LC_MESSAGES/ in Linux)
- ya-setup utility translations files (translations/ya-setup*.lang) are located in /usr/share/yd-tools/translation folder
NOTE: All action above can be done via running of build/install.sh script
- indicator settings are stored in ~/.config/yd-tools/yandex-disk-indicator.conf (file is automatically created on the first start).


build - everything that need to build the .deb package or source.changes file (only change key for signatures). Additional tools are required: devscripts, debhelper and dput (if you want to upload package, for example, to launchpad PPA).
- install.sh - script to install the indicator
- prepare.sh - creates the package build/instalation image in build/yd-tools/
- clean.sh - clean build directory
- bild_deb.sh - creates DEB package
- make_source.changes.sh - prepares sources for publication
- publish_to_PPA.sh - prepares sources and publish it to my ppa

See the wiki page for details: https://github.com/slytomcat/yandex-disk-indicator/wiki.
