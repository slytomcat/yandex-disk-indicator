#!/bin/bash
cd yd-tools/
cp ../../yandex-disk-indicator.py usr/bin/yandex-disk-indicator
cp ../../ya-setup usr/share/yd-tools/
cp ../../translations/yandex-disk-indicator_ru.mo usr/share/locale/ru/LC_MESSAGES/yandex-disk-indicator.mo
cp ../../translations/yandex-disk-indicator_el.mo usr/share/locale/el/LC_MESSAGES/yandex-disk-indicator.mo
cp ../../Yandex.Disk-indicator.desktop usr/share/applications/
cp ../../Yandex.Disk.desktop usr/share/applications/
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
cp ../../fm-actions/Dolphin/publish.desktop usr/share/yd-tools/fm-actions/Dolphin/
cp ../../fm-actions/Dolphin/unpublish.desktop usr/share/yd-tools/fm-actions/Dolphin/

chmod -R u+rw *
chmod -R go-w *
chmod a+x debian/rules
chmod a+x debian/prerm
chmod a+x debian/preinst
chmod a+x usr/share/yd-tools/*
chmod a+x usr/share/yd-tools/fm-actions/Nautilus_Nemo/*
chmod a+x usr/share/yd-tools/fm-actions/Dolphin/*
chmod a+x usr/bin/*
chmod a+x usr/share/applications/*
cd ..
chmod a+x *.sh