#!/usr/bin/env zsh

autoload -U parseopts
autoload -U zargs
autoload -U zcalc
autoload -U zed
autoload -U zmv

alias cc='claude --enable-auto-mode'
alias compose='docker-compose --compatibility'
alias e=$EDITOR
alias homelab='herdr --remote nuc --session homelab'  # herdr into the nuc's ~/homelab agent workspace

# The plugin companion wraps only interactive attachments; CLI commands exec
# the actual binary unchanged. Never replace/shadow the native executable.
herdr() {
    local native=$(whence -p herdr)
    local repeat=$HOME/.local/share/plugins/herdr-repeat-navigation/bin/herdr-repeat
    if [[ -n $native && -x $repeat ]]; then
        "$repeat" --binary "$native" -- "$@"
    else
        command herdr "$@"
    fi
}
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
