#!/bin/bash
#### Author: Fahreev Eldar ####

### Language
lang_home="/usr/share/yd-tools/translations"

lang_file="$lang_home/actions-$(echo $LANG | cut -c 1-2).lang"

if [ ! -f $lang_file ]; then
    lang_file="$lang_home/actions-en.lang"
fi

source $lang_file


f=$(yandex-disk publish "$1")
out=$?
if [ $out == 0 ]; then
    echo "$f" | xclip -filter -selection clipboard
    notify-send Yandex.Disk "$_Symlink $*

$f

$_Copy."

else
    notify-send Yandex.Disk "$f"
fi

