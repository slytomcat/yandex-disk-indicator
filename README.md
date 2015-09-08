### **![yandex-disk-indicator](https://github.com/slytomcat/yandex-disk-indicator/blob/master/icons/yd-128.png)**
# yandex-disk-indicator
Desktop panel indicator for YandexDisk CLI client for Linux

Code assumes that:
- yandex-disk-indicator.py is placed in /usr/share/yandex-disk-indicator marked as executable (chmod a+x ...)
- fm-actions/ and icons/ folders, ya-setup and *.desktop files are located in the same directory where yandexDiskIndicator.py is located (from v.1.4.2 - /usr/share/yd-tools)
- compiled language files (translations/*.mo) are located in the system depended folders (i.e. usr/share/locale/{LANG}/LC_MESSAGES/ in Linux)
- indicator settings (from v.1.4.2) are stored in ~/.config/yd-tools/yandex-disk-indicator.conf (file is automatically created on the first start).

build - everything that need to build the .deb package or source.changes file. Additional tools are requered: devscripts, debhelper and dput (if you want to uplodd package, for example, to launcpad PPA).
