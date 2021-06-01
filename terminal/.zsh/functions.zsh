#!/usr/bin/env zsh

autoload -U parseopts
autoload -U zargs
autoload -U zcalc
autoload -U zed
autoload -U zmv

alias ag='ag --hidden'
alias compose='docker-compose --compatibility'
alias dc=pushd
alias e=$EDITOR
alias ff=firefox
alias g='surfraw google'
alias hs=homeshick
alias p=parallel
alias pbcopy='xclip -selection clipboard'
alias pbpaste='xclip -selection clipboard -o'
alias r=ranger
alias s='surfraw duckduckgo -j'
alias sc=starcluster
alias sl=ls
alias stack='docker stack'
alias sudo='sudo '
alias ytd=youtube-dl
alias zcp='zmv -C'
alias compose= 'docker compose'
alias zln='zmv -L'

if [[ $(uname) == Darwin ]]; then
    alias cat=vimcat
    alias l='gls -ahl --color=auto --group-directories-first'
    alias ls='gls --color=auto --group-directories-first'
    alias rm='trash'
else
    alias l='ls -ahl --color=auto --group-directories-first'
    alias ls='ls --color=auto --group-directories-first'
fi
