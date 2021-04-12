#!/bin/bash
#TARGET="yd-tools/usr" or "/usr"

# prepare target directory
mkdir -p $TARGET/bin
mkdir -p $TARGET/share/applications
mkdir -p $TARGET/share/locale/ru/LC_MESSAGES
mkdir -p $TARGET/share/locale/el/LC_MESSAGES
mkdir -p $TARGET/share/locale/bg/LC_MESSAGES
mkdir -p $TARGET/share/locale/be/LC_MESSAGES
mkdir -p $TARGET/share/yd-tools/fm-actions/Dolphin
mkdir -p $TARGET/share/yd-tools/fm-actions/Nautilus_Nemo
mkdir -p $TARGET/share/yd-tools/fm-actions/pantheon-files
mkdir -p $TARGET/share/yd-tools/icons/dark
mkdir -p $TARGET/share/yd-tools/icons/light
mkdir -p $TARGET/share/yd-tools/translations
cp ../yandex-disk-indicator $TARGET/bin/yandex-disk-indicator
cp ../indicator.py $TARGET/share/yd-tools/
cp ../daemon.py $TARGET/share/yd-tools/
cp ../tools.py $TARGET/share/yd-tools/
cp ../ya-setup $TARGET/share/yd-tools/
cp ../translations/yandex-disk-indicator_ru.mo $TARGET/share/locale/ru/LC_MESSAGES/yandex-disk-indicator.mo
cp ../translations/yandex-disk-indicator_el.mo $TARGET/share/locale/el/LC_MESSAGES/yandex-disk-indicator.mo
cp ../translations/yandex-disk-indicator_bg.mo $TARGET/share/locale/bg/LC_MESSAGES/yandex-disk-indicator.mo
cp ../translations/yandex-disk-indicator_be.mo $TARGET/share/locale/be/LC_MESSAGES/yandex-disk-indicator.mo
cp ../translations/*.lang $TARGET/share/yd-tools/translations/
cp ../Yandex.Disk-indicator.desktop $TARGET/share/applications/
cp ../icons/readme $TARGET/share/yd-tools/icons/
cp ../icons/yd-128.png $TARGET/share/yd-tools/icons/
cp ../icons/yd-128_g.png $TARGET/share/yd-tools/icons/
cp ../icons/dark/yd-busy1.png $TARGET/share/yd-tools/icons/dark/
cp ../icons/dark/yd-busy2.png $TARGET/share/yd-tools/icons/dark/
cp ../icons/dark/yd-busy3.png $TARGET/share/yd-tools/icons/dark/
cp ../icons/dark/yd-busy4.png $TARGET/share/yd-tools/icons/dark/
cp ../icons/dark/yd-busy5.png $TARGET/share/yd-tools/icons/dark/
cp ../icons/dark/yd-ind-error.png $TARGET/share/yd-tools/icons/dark/
cp ../icons/dark/yd-ind-idle.png $TARGET/share/yd-tools/icons/dark/
cp ../icons/dark/yd-ind-pause.png $TARGET/share/yd-tools/icons/dark/
cp ../icons/light/yd-busy1.png $TARGET/share/yd-tools/icons/light/
cp ../icons/light/yd-busy2.png $TARGET/share/yd-tools/icons/light/
cp ../icons/light/yd-busy3.png $TARGET/share/yd-tools/icons/light/
cp ../icons/light/yd-busy4.png $TARGET/share/yd-tools/icons/light/
cp ../icons/light/yd-busy5.png $TARGET/share/yd-tools/icons/light/
cp ../icons/light/yd-ind-error.png $TARGET/share/yd-tools/icons/light/
cp ../icons/light/yd-ind-idle.png $TARGET/share/yd-tools/icons/light/
cp ../icons/light/yd-ind-pause.png $TARGET/share/yd-tools/icons/light/
cp ../fm-actions/Nautilus_Nemo/publish $TARGET/share/yd-tools/fm-actions/Nautilus_Nemo/
cp ../fm-actions/Nautilus_Nemo/unpublish $TARGET/share/yd-tools/fm-actions/Nautilus_Nemo/
cp ../fm-actions/Dolphin/ydpublish.desktop $TARGET/share/yd-tools/fm-actions/Dolphin/
cp ../fm-actions/pantheon-files/publish.sh $TARGET/share/yd-tools/fm-actions/pantheon-files/
cp ../fm-actions/pantheon-files/unpublish.sh $TARGET/share/yd-tools/fm-actions/pantheon-files/
cp ../fm-actions/pantheon-files/yandex-disk-indicator-publish.contract $TARGET/share/yd-tools/fm-actions/pantheon-files/
cp ../fm-actions/pantheon-files/yandex-disk-indicator-unpublish.contract $TARGET/share/yd-tools/fm-actions/pantheon-files/

chmod a+x $TARGET/share/yd-tools/*
chmod a+x $TARGET/share/yd-tools/fm-actions/Nautilus_Nemo/*
chmod a+x $TARGET/share/yd-tools/fm-actions/pantheon-files/*.sh
chmod a+x $TARGET/bin/yandex-disk-indicator
chmod a+x $TARGET/share/applications/Yandex.Disk-indicator.desktop
