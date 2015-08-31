# yandex-disk-indicator
Desktop panel indicator for YandexDisk CLI client for Linux

Code assumes that
- fm-actions/ and icons/ folders, ya-setup and *.desktop files are located in the same directory where yandexDiskIndicator.py is located
- language files (.mo) are located in the system depended folders (i.e. usr/share/locale/<LANG>/LC_MESSAGES/ in Linux)
- settings (apps.yandex-disk-indicator.gschema.xml) are applied via gconf (/usr/share/glib-2.0/schemas/). See schemas_update script

build - everything that need to build the .deb package source.changes file (some additional tools are requered)
