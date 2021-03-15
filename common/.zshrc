#!/usr/bin/env zsh

setopt auto_cd
setopt auto_pushd
setopt extended_glob
setopt extended_history
setopt glob_dots
setopt hist_find_no_dups
setopt hist_ignore_all_dups
setopt hist_ignore_space
setopt hist_reduce_blanks
setopt hist_verify
setopt inc_append_history
setopt interactive_comments
setopt no_case_glob
setopt numeric_glob_sort
setopt pushd_ignore_dups
setopt pushd_silent
setopt rm_star_wait

autoload -U select-word-style
select-word-style bash

if [[ $TERM == eterm-color ]]; then
    export EDITOR=emacsclient
else
    [ -n "$PS1" ] && [ -s $BASE16_SHELL/profile_helper.sh ] && eval "$($BASE16_SHELL/profile_helper.sh)"
    export EDITOR=vim
fi

HISTFILE=$ZSH/history
HISTSIZE=10000
KEYTIMEOUT=23
PAGER=$EDITOR
REPORTTIME=5
SAVEHIST=10000
ZLE_RPROMPT_INDENT=0

source $ZSH/completion.zsh
source $ZSH/directory_tracking.zsh
source $ZSH/functions.zsh
source $ZSH/prompt.zsh

source $ZSH/antigen/antigen.zsh

antigen bundle zsh-users/zsh-syntax-highlighting
antigen bundle zsh-users/zsh-completions
antigen bundle zsh-users/zaw
antigen bundle termoshtt/zaw-systemd
antigen bundle oknowton/zsh-dwim

antigen apply

source $ZSH/keybindings.zsh
