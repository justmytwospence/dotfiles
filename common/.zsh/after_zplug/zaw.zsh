#!/usr/bin/env zsh

bindkey '^g' zaw
bindkey '^r' zaw-history
bindkey '^t' zaw-process
bindkey '^u' dwim

bindkey -M filterselect '\e' send-break
bindkey -M filterselect '^[[3;5~' backward-kill-word
bindkey -M filterselect '^j' down-line-or-history
bindkey -M filterselect '^k' up-line-or-history

zstyle ':filter-select' case-insensitive yes
zstyle ':filter-select' extended-search yes
zstyle ':filter-select' hist-find-no-dups yes
zstyle ':filter-select' max-lines 30
zstyle ':filter-select' rotate-list yes
