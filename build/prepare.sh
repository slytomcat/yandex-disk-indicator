#!/bin/bash

# prepare changelog
version=$(sed -n "/appVer = '.*'/p" ../yandex-disk-indicator.py | grep -o '[0-9]\.[0-9]\.[0-9]')
serie='xenial'
clear

sed "s/@serie/$serie/" changelog > yd-tools/debian/changelog
sed -i "s/@version/$version/" yd-tools/debian/changelog
sed -i "s/@date/$(date -R)/" yd-tools/debian/changelog
cat yd-tools/debian/changelog 

# prepare buld directory
mv yd-tools yd-tools-$version
cd yd-tools-*/
mkdir -p usr/bin
mkdir -p usr/share/applications
mkdir -p usr/share/locale/ru/LC_MESSAGES
mkdir -p usr/share/locale/el/LC_MESSAGES
mkdir -p usr/share/locale/bg/LC_MESSAGES
mkdir -p usr/share/locale/be/LC_MESSAGES
mkdir -p usr/share/yd-tools/fm-actions/Dolphin
mkdir -p usr/share/yd-tools/fm-actions/Nautilus_Nemo
mkdir -p usr/share/yd-tools/fm-actions/pantheon-files
mkdir -p usr/share/yd-tools/icons/dark
mkdir -p usr/share/yd-tools/icons/light
mkdir -p usr/share/yd-tools/translations
cp ../../yandex-disk-indicator.py usr/bin/yandex-disk-indicator
cp ../../ya-setup usr/share/yd-tools/
cp ../../translations/yandex-disk-indicator_ru.mo usr/share/locale/ru/LC_MESSAGES/yandex-disk-indicator.mo
cp ../../translations/yandex-disk-indicator_el.mo usr/share/locale/el/LC_MESSAGES/yandex-disk-indicator.mo
cp ../../translations/yandex-disk-indicator_bg.mo usr/share/locale/bg/LC_MESSAGES/yandex-disk-indicator.mo
cp ../../translations/yandex-disk-indicator_be.mo usr/share/locale/be/LC_MESSAGES/yandex-disk-indicator.mo
cp ../../translations/*.lang usr/share/yd-tools/translations/
cp ../../Yandex.Disk-indicator.desktop usr/share/applications/
cp ../../icons/readme usr/share/yd-tools/icons/
cp ../../icons/yd-128.png usr/share/yd-tools/icons/
cp ../../icons/yd-128_g.png usr/share/yd-tools/icons/
cp ../../icons/dark/yd-busy1.png usr/share/yd-tools/icons/dark/
cp ../../icons/dark/yd-busy2.png usr/share/yd-tools/icons/dark/
cp ../../icons/dark/yd-busy3.png usr/share/yd-tools/icons/dark/
cp ../../icons/dark/yd-busy4.png usr/share/yd-tools/icons/dark/
cp ../../icons/dark/yd-busy5.png usr/share/yd-tools/icons/dark/
cp ../../icons/dark/yd-ind-error.png usr/share/yd-tools/icons/dark/
cp ../../icons/dark/yd-ind-idle.png usr/share/yd-tools/icons/dark/
cp ../../icons/dark/yd-ind-pause.png usr/share/yd-tools/icons/dark/
cp ../../icons/light/yd-busy1.png usr/share/yd-tools/icons/light/
cp ../../icons/light/yd-busy2.png usr/share/yd-tools/icons/light/
cp ../../icons/light/yd-busy3.png usr/share/yd-tools/icons/light/
cp ../../icons/light/yd-busy4.png usr/share/yd-tools/icons/light/
cp ../../icons/light/yd-busy5.png usr/share/yd-tools/icons/light/
cp ../../icons/light/yd-ind-error.png usr/share/yd-tools/icons/light/
cp ../../icons/light/yd-ind-idle.png usr/share/yd-tools/icons/light/
cp ../../icons/light/yd-ind-pause.png usr/share/yd-tools/icons/light/
cp ../../fm-actions/Nautilus_Nemo/publish usr/share/yd-tools/fm-actions/Nautilus_Nemo/
cp ../../fm-actions/Nautilus_Nemo/unpublish usr/share/yd-tools/fm-actions/Nautilus_Nemo/
cp ../../fm-actions/Dolphin/ydpublish.desktop usr/share/yd-tools/fm-actions/Dolphin/
cp ../../fm-actions/pantheon-files/publish.sh usr/share/yd-tools/fm-actions/pantheon-files/
cp ../../fm-actions/pantheon-files/unpublish.sh usr/share/yd-tools/fm-actions/pantheon-files/
cp ../../fm-actions/pantheon-files/yandex-disk-indicator-publish.contract usr/share/yd-tools/fm-actions/pantheon-files/
cp ../../fm-actions/pantheon-files/yandex-disk-indicator-unpublish.contract usr/share/yd-tools/fm-actions/pantheon-files/

chmod -R u+rw *
chmod -R go-w *
chmod a+x debian/rules
chmod a+x debian/pre*
chmod a+x debian/post*
chmod a+x usr/share/yd-tools/*
chmod a+x usr/share/yd-tools/fm-actions/Nautilus_Nemo/*
chmod a+x usr/share/yd-tools/fm-actions/pantheon-files/*.sh
chmod a+x usr/bin/*
chmod a+x usr/share/applications/*
cd ..
chmod a+x *.sh
