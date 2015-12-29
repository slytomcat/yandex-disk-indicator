#!/bin/bash
#### Author: Fahreev Eldar ####
f=$(yandex-disk unpublish "$1")
out=$?
if [ $out == 0 ]; then
    notify-send Яндекс.Диск "Публичная ссылка на файл $f удалена"
else
    notify-send Яндекс.Диск "$f"
fi


