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
bindkey '^g' zaw
bindkey '^o' zaw-systemctl-user
bindkey '^r' zaw-history
bindkey '^t' zaw-process
bindkey '^u' dwim

# filter-select (only load if available from zaw plugin)
if (( $+functions[filter-select] )); then
    filter-select -i

    zstyle ':filter-select' case-insensitive yes
    zstyle ':filter-select' extended-search yes
    zstyle ':filter-select' hist-find-no-dups yes
    zstyle ':filter-select' max-lines 30
    zstyle ':filter-select' rotate-list yes

    bindkey -M filterselect '\e' send-break
    bindkey -M filterselect '^[[3;5~' backward-kill-word
    bindkey -M filterselect '^j' down-line-or-history
    bindkey -M filterselect '^k' up-line-or-history
fi
