#!/usr/bin/env zsh

setopt auto_cd
setopt auto_pushd
setopt correct
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

typeset -U path  # Disallow duplicates

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

if [[ -a /usr/share/zsh/share/antigen.zsh ]]; then
  source /usr/share/zsh/share/antigen.zsh # Arch
elif [[ -a /usr/share/zsh-antigen/antigen.zsh ]]; then
  source /usr/share/zsh-antigen/antigen.zsh # Debian
else
  echo "Cannot find Antigen"
fi

antigen bundle chriskempson/base16-shell
antigen bundle zsh-users/zsh-syntax-highlighting
antigen bundle zsh-users/zsh-completions
antigen bundle zsh-users/zaw
antigen bundle termoshtt/zaw-systemd
antigen bundle oknowton/zsh-dwim

antigen apply

source $ZSH/keybindings.zsh
