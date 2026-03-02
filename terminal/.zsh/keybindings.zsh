#!/usr/bin/env zsh

# stty erase '^h'
bindkey '^h' backward-kill-word

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

# plugins
# fzf handles ^r (history) and ^t (file finder) via `fzf --zsh`
bindkey '^u' dwim

