#!/usr/bin/env zsh

bindkey '^f' deer
zle -N deer

function deer-mark-file-list {
    local MARKED=$1
    shift
    print -l -- "$@" \
        | grep -Fx -B5 -A$DEER_HEIGHT -- "$MARKED" \
        | perl -pe 'BEGIN{$name = shift}
                    if ($name."\n" eq $_) {
                        $_="➜ $_"
                    } else {
                        $_="  $_"
                    }' -- "$MARKED"
}
