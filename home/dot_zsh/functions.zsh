#!/usr/bin/env zsh

autoload -U parseopts
autoload -U zargs
autoload -U zcalc
autoload -U zed
autoload -U zmv

alias cc='claude --enable-auto-mode'
alias compose='docker compose --compatibility'
alias e=$EDITOR
alias homelab='herdr --remote nuc'  # herdr into the nuc's ~/homelab agent workspace

# Explicitly upgrade one cask without permanently changing its pin state.
brew-upgrade-explicit() {
    if (( $# != 1 )) || [[ -z $1 || $1 == -* ]]; then
        print -u2 'Usage: brew-upgrade-explicit <cask>'
        return 2
    fi

    local cask=$1 pins result=0 repin_result=0
    local -a pinned_casks
    pins=$(command brew list --cask --pinned) || return $?
    pinned_casks=("${(@f)pins}")
    if (( ${pinned_casks[(Ie)$cask]} )); then
        {
            command brew unpin --cask "$cask" &&
                command brew upgrade --cask "$cask"
            result=$?
        } always {
            command brew pin --cask "$cask"
            repin_result=$?
            (( repin_result == 0 )) || result=$repin_result
        }
        return $result
    fi
    command brew upgrade --cask "$cask"
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
