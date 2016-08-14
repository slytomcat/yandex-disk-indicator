#!/bin/bash
#### Author: Fahreev Eldar ####

notify-send Yandex.Disk $(yandex-disk unpublish "$1")

#f=$(yandex-disk unpublish "$1")
#out=$?
#if [ $out == 0 ]; then
#    notify-send Yandex.Disk "$f"
#else
#    notify-send Yandex.Disk "$f"
#fi


