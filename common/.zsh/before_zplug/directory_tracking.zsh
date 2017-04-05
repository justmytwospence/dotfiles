##!/usr/bin/env zsh

autoload -Uz add-zsh-hook

add-zsh-hook chpwd tmux-track-directory
function tmux-track-directory {
    if [[ -n $TMUX ]]; then
        tmux rename-window $(basename $PWD)
    fi
}

if [[ $TERM == eterm-color ]]; then
    add-zsh-hook chpwd eterm-track-directory
    function eterm-track-directory {
        print -P "\033AnSiTu %n"
        print -P '\033AnSiTc %d'
        if [[ -n "$SSH_TTY" ]]; then
            print "\033AnSiTh $(hostname)"
        else
            print "\033AnSiTh $(hostname -f)"
        fi
    }
    eterm-track-directory
fi
