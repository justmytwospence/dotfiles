#!/usr/bin/env zsh

# Uncomment to profile startup time
# zmodload zsh/zprof

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

export GPG_TTY=$TTY  # Set GPG TTY for interactive shells

HISTFILE=$ZSH/history
HISTSIZE=10000
KEYTIMEOUT=23
PAGER=$EDITOR
REPORTTIME=5
SAVEHIST=10000
ZLE_RPROMPT_INDENT=0

source $ZSH/functions.zsh
source $ZSH/completion.zsh
source $ZSH/directory_tracking.zsh
source $ZSH/prompt.zsh

### Added by Zinit's installer
ZINIT_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}/zinit/zinit.git"
[ ! -d $ZINIT_HOME ] && mkdir -p "$(dirname $ZINIT_HOME)"
[ ! -d $ZINIT_HOME/.git ] && git clone https://github.com/zdharma-continuum/zinit.git "$ZINIT_HOME"
source "${ZINIT_HOME}/zinit.zsh"

# Load base16-shell synchronously (needs to set colors before prompt)
if [[ $TERM_PROGRAM != vscode ]]; then
  zinit ice lucid
  zinit light chriskempson/base16-shell
  
  # Set your preferred base16 theme if not already set
  if [ -z "$BASE16_THEME" ]; then
    base16_tomorrow-night 2>/dev/null
  fi
fi

# Load syntax highlighting and completions with turbo mode (async after prompt)
zinit wait lucid for \
  atinit"zicompinit; zicdreplay" \
    zdharma-continuum/fast-syntax-highlighting \
  blockf atpull'zinit creinstall -q .' \
    zsh-users/zsh-completions

# Load other plugins async
zinit wait lucid for \
    zsh-users/zaw \
    termoshtt/zaw-systemd \
    oknowton/zsh-dwim

# Load keybindings after plugins are available
zinit wait lucid atload'source $ZSH/keybindings.zsh' for \
    zdharma-continuum/null

## pyenv initialization (only for interactive shells)

if command -v pyenv >/dev/null 2>&1; then
    eval "$(pyenv init - --no-rehash 2>/dev/null)" 2>/dev/null
    eval "$(pyenv virtualenv-init - 2>/dev/null)" 2>/dev/null
fi

## local

if [[ -f $HOME/.zshrc.local ]]; then
    source $HOME/.zshrc.local
fi

# Uncomment to see profiling output
# zprof
