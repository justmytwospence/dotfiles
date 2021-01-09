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
setopt rc_expand_param
setopt rm_star_wait

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
ZPLUG_CHMOD='chmod --recursive g-w "$ZPLUG_HOME"'
ZPLUG_HOME=$ZSH/zplug
ZPLUG_LOADFILE=$ZSH/packages.zsh
ZSH_HIGHLIGHT_HIGHLIGHTERS=(brackets main)

source ${HOME}/.zsh/zplug/init.zsh
zplug load
