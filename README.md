# yandex-disk-indicator
Desktop panel indicator for YandexDisk CLI client for Linux

Code assumes that
- fm-actions/ and icons/ folders, ya-setup and *.desktop files are located in the same directory where yandexDiskIndicator.py is located
- compiled language files (.mo) are located in the system depended folders (i.e. usr/share/locale/<LANG>/LC_MESSAGES/ in Linux)
- settings (apps.yandex-disk-indicator.gschema.xml) are applied via gconf. schemas_update script can be used to update settings after coping .xml file to /usr/share/glib-2.0/schemas/ folder 

build - everything that need to build the .deb package or source.changes file. Additional tools are requered: devscripts, debhelper and dput (if you want to uplodd package, for example, to launcpad PPA).
