#!/usr/bin/env zsh

autoload -U parseopts
autoload -U zargs
autoload -U zcalc
autoload -U zed
autoload -U zmv

# Strip telemetry-opt-out vars before invoking claude — DO_NOT_TRACK and friends
# silently break Remote Control by gating the GrowthBook feature-flag fetch
# (anthropics/claude-code#29580). Remove this wrapper once that bug is fixed.
claude() {
    (unset DO_NOT_TRACK DISABLE_TELEMETRY CLAUDE_CODE_ENABLE_TELEMETRY DISABLE_GROWTHBOOK
     command claude "$@")
}

alias cc='claude --enable-auto-mode'
alias compose='docker-compose --compatibility'
alias e=$EDITOR
alias sl=ls
alias zcp='zmv -C'
alias zln='zmv -L'

if [[ $(uname) == Darwin ]]; then
    alias dircolors=gdircolors
    alias l='gls -ahl --color=auto --group-directories-first'
    alias ls='gls --color=auto --group-directories-first'
else
    alias l='ls -ahl --color=auto --group-directories-first'
    alias ls='ls --color=auto --group-directories-first'
fi
