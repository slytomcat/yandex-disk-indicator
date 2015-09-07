#!/bin/bash
cd yd-tools/
rm usr/bin/yandex-disk-indicator
rm usr/share/yd-tools/ya-setup
rm usr/share/yd-tools/IndicatorDebug_ON.sh
rm usr/share/yd-tools/IndicatorDebug_OFF.sh
rm usr/share/yd-tools/icons/readme
rm usr/share/yd-tools/icons/yd-128.png
rm usr/share/yd-tools/icons/yd-128_g.png
rm usr/share/yd-tools/icons/dark/yd-busy1.png
rm usr/share/yd-tools/icons/dark/yd-busy2.png
rm usr/share/yd-tools/icons/dark/yd-busy3.png
rm usr/share/yd-tools/icons/dark/yd-busy4.png
rm usr/share/yd-tools/icons/dark/yd-busy5.png
rm usr/share/yd-tools/icons/dark/yd-ind-error.png
rm usr/share/yd-tools/icons/dark/yd-ind-idle.png
rm usr/share/yd-tools/icons/dark/yd-ind-pause.png
rm usr/share/yd-tools/icons/light/yd-busy1.png
rm usr/share/yd-tools/icons/light/yd-busy2.png
rm usr/share/yd-tools/icons/light/yd-busy3.png
rm usr/share/yd-tools/icons/light/yd-busy4.png
rm usr/share/yd-tools/icons/light/yd-busy5.png
rm usr/share/yd-tools/icons/light/yd-ind-error.png
rm usr/share/yd-tools/icons/light/yd-ind-idle.png
rm usr/share/yd-tools/icons/light/yd-ind-pause.png
rm usr/share/yd-tools/fm-actions/Nautilus_Nemo/publish
rm usr/share/yd-tools/fm-actions/Nautilus_Nemo/unpublish
rm usr/share/yd-tools/fm-actions/Dolphin/publish.desktop
rm usr/share/yd-tools/fm-actions/Dolphin/unpublish.desktop
rm usr/share/locale/ru/LC_MESSAGES/yandex-disk-indicator.mo
rm usr/share/locale/el/LC_MESSAGES/yandex-disk-indicator.mo
rm usr/share/applications/Yandex.Disk.desktop
rm usr/share/applications/Yandex.Disk-indicator.desktop

rm -r debian/yd-tools*
cd ..
rm yd-tools_*
