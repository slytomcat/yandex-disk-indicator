### **![yandex-disk-indicator](https://github.com/slytomcat/yandex-disk-indicator/blob/master/icons/yd-128.png)**
# yandex-disk-indicator
[![license](https://img.shields.io/badge/license-GPL%20v.3-green.svg)](https://github.com/slytomcat/yandex-disk-indicator/blob/master/LICENSE)
[![wiki](https://img.shields.io/badge/wiki-available-green.svg)](https://github.com/slytomcat/yandex-disk-indicator/wiki)
[![PPA](https://img.shields.io/badge/PPA-available-green.svg)](https://launchpad.net/~slytomcat/+archive/ubuntu/ppa)

Desktop panel indicator for YandexDisk CLI client for Linux (GTK+)

##### NOTE: 

If You are looking for YandexDisk indicator for KDE or other non-GTK based DE take a look on [yd-go](https://github.com/slytomcat/yd-go). _yd-go_ is a little simpler indicator written in golang. It uses D-BUS to communicate with the desktop notification plugin, that's why yd-go is fully independent off Desktop Environment.

### IMPORTANT:

Indicator responsible only for showing the synchronisation status in the desctop panel. All the synchronisation operations are perfomed by [yandex-disk utility from Yandex](https://yandex.ru/support/disk-desktop-linux/index.html).

### INSTALLATION:

See installation instruction in [Wiki](https://github.com/slytomcat/yandex-disk-indicator/wiki)

### INTERFACE LANGUAGES

English, Russian, Greek, Bulgarian, Belorussian.  


### NOTES:

Indicator code assumes that:
- `yandex-disk-indicator` is copied to `/usr/bin/yandex-disk-indicator` and marked as executable (chmod a+x ...)
- `fm-actions/` and `icons/` folders, `ya-setup` and `*.py` files are located in `/usr/share/yd-tools` folder
- `*.desktop` files were placed in `/usr/share/applications` folder
- compiled language files (`translations/*.mo`) are located in the system depended folders (i.e. `usr/share/locale/{LANG}/LC_MESSAGES/` in Linux)
- `ya-setup` utility translations files (`translations/ya-setup*.lang`) are located in `/usr/share/yd-tools/translation` folder
NOTE: All action above can be done via running of `build/install.sh` script
- indicator settings are stored in `~/.config/yd-tools/yandex-disk-indicator.conf` (file is automatically created on the first start).


`build` - everything that need to build the .deb package or `source.changes` file (only change key for signatures). Additional tools are required: `devscripts`, `debhelper` and `dput` (if you want to upload package, for example, to launchpad PPA).
- `install.sh` - script to install the indicator
- `prepare.sh` - creates the package build/instalation image in `build/yd-tools/`
- `clean.sh` - clean build directory
- `build_deb.sh` - creates DEB package
- `make_source.changes.sh` - prepares sources for publication
- `publish_to_PPA.sh` - prepares sources and publish it to [my PPA]https://launchpad.net/~slytomcat/+archive/ubuntu/ppa

See the wiki page for details: https://github.com/slytomcat/yandex-disk-indicator/wiki.
