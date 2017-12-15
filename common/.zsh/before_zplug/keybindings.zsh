#!/usr/bin/env zsh

autoload -U is-at-least

# vim
bindkey -v

# emacs
bindkey '^?' backward-delete-char
bindkey '^a' beginning-of-line
bindkey '^b' backward-char
bindkey '^e' end-of-line
bindkey '^f' forward-char
bindkey '^k' kill-line
bindkey '^n' history-beginning-search-forward
bindkey '^p' history-beginning-search-backward
bindkey '^w' backward-delete-word
bindkey -M vicmd '^k' kill-line

# edit-command-line
autoload -Uz edit-command-line
if [[ $TERM == eterm-color ]]; then
    bindkey -M vicmd 'V' edit-command-line-emacs
    bindkey -M vicmd 'v' edit-command-line-emacs
    zle -N edit-command-line-emacs
    function edit-command-line-emacs {
        print '\033TeRmCmD LeaderToggle off'
        edit-command-line
    }
else
    bindkey -M vicmd 'V' edit-command-line
    bindkey -M vicmd 'v' edit-command-line
    zle -N edit-command-line
fi

# menuselect
zmodload zsh/complist
bindkey -M menuselect '\e' undo
bindkey -M menuselect '^[[Z' reverse-menu-complete

# suspend
function fancy-ctrl-z {
    if [[ $#BUFFER -eq 0 ]]; then
        BUFFER=fg
        zle accept-line
    else
        zle push-input
        zle clear-screen
    fi
}
bindkey '^z' fancy-ctrl-z
zle -N fancy-ctrl-z

# vi-mode
if is-at-least 5.0.8; then

    bindkey -a j history-beginning-search-forward
    bindkey -a k history-beginning-search-backward

    # select-bracketed
    autoload -U select-bracketed
    for m in visual viopp; do
        for c in {a,i}${(s..)^:-'()[]{}<>bB'}; do
            bindkey -M $m $c select-bracketed
        done
    done
    zle -N select-bracketed

    # select-quoted
    autoload -U select-quoted
    for m in visual viopp; do
        for c in {a,i}{\',\",\`}; do
            bindkey -M $m $c select-quoted
        done
    done
    zle -N select-quoted

    # surround
    autoload -Uz surround
    bindkey -a cs change-surround
    bindkey -a ds delete-surround
    bindkey -a ys add-surround
    bindkey -M visual S add-surround
    zle -N delete-surround surround
    zle -N add-surround surround
    zle -N change-surround surround

fi
