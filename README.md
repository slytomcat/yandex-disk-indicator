### **![yandex-disk-indicator](https://github.com/slytomcat/yandex-disk-indicator/blob/master/icons/yd-128.png)**
# yandex-disk-indicator
Desktop panel indicator for YandexDisk CLI client for Linux

Usage: yandex-disk-indicator [-l<n>]

Options:
 -l<n>   Set logging level to value <n>.
         Logging level value can be:
            10 - to show all messages (DEBUG)
            20 - to show all messages except debugging messages (INFO)
            30 - to show all messages except debugging and info messages (WARNING)
            40 - to show only error and critical messages (ERROR)
            50 - to show critical messages only (CRITICAL)

Ubuntu deb packages available from LaunchPad PPA: https://launchpad.net/~slytomcat/+archive/ubuntu/ppa

NOTES:

Code assumes that:
- yandex-disk-indicator.py is copied to /usr/bin/yandex-disk-indicator and marked as executable (chmod a+x ...)
- fm-actions/ and icons/ folders, ya-setup files are located in /usr/share/yd-tools
- *.desktop files should be placed in /usr/share/applications folder
- compiled language files (translations/*.mo) are located in the system depended folders (i.e. usr/share/locale/{LANG}/LC_MESSAGES/ in Linux)
- indicator settings are stored in ~/.config/yd-tools/yandex-disk-indicator.conf (file is automatically created on the first start).

build - everything that need to build the .deb package or source.changes file (only change key for signatures). Additional tools are required: devscripts, debhelper and dput (if you want to upload package, for example, to launcpad PPA).

