#!/usr/bin/env zsh

autoload -U parseopts
autoload -U zargs
autoload -U zcalc
autoload -U zed
autoload -U zmv

alias compose='docker-compose --compatibility'
alias e=$EDITOR
alias pipe2slack="tee /dev/tty | grep --line-buffered -v '^\s*$' | perl -pe 'select(STDOUT); $| =1; s/\e\[[0-9;]*m//g' | slackcat"
alias slackping="slackcat success || slackcat failure"
alias sl=ls
alias xcopy='xclip -selection clipboard'
alias xpaste='xclip -selection clipboard -o'
alias zcp='zmv -C'
alias zln='zmv -L'

if [[ $(uname) == Darwin ]]; then
    alias cat=vimcat
    alias dircolors=gdircolors
    alias l='gls -ahl --color=auto --group-directories-first'
    alias ls='gls --color=auto --group-directories-first'
    alias rm='trash'
else
    alias l='ls -ahl --color=auto --group-directories-first'
    alias ls='ls --color=auto --group-directories-first'
fi
