#!/bin/bash
#### Author: Fahreev Eldar ####
f=$(yandex-disk publish "$1")
out=$?
if [ $out == 0 ]; then
    echo "$f" | xclip -filter -selection clipboard
    notify-send Яндекс.Диск "Ссылка на файл: $1 скопирована в буфер обмена."
else
    notify-send Яндекс.Диск "$f"
fi

