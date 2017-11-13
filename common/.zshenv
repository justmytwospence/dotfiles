#!/usr/bin/env zsh

typeset -U path  # Disallow duplicates

export ALTERNATE_EDITOR=
export BASE16_SHELL=$HOME/.config/base16-shell/
export GOPATH=$HOME/gocode
export GPG_TTY=$(tty)
export HISTORY_IGNORE='(exit|reboot|rm *|shutdown now)'
export JUPYTER_DATA_DIR=~/.local/share/jupyter
export LANG=en_US.UTF-8
export LANGUAGE=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export ZSH=$HOME/.zsh

path=(
    $BASE16_SHELL
    $GOPATH/bin
    $HOME/.cabal/bin
    $HOME/.emacs.d/term-cmd
    $HOME/.local/bin
    $HOME/.rbenv/shims
    $HOME/bin
    /usr/local/bin
    /usr/local/sbin
    $path)

## osx

if [[ $(uname) == Darwin ]]; then
    export MANPATH=/usr/local/opt/coreutils/libexec/gnuman:$MANPATH
    export PGDATA=/usr/local/var/postgres
    fpath+=/usr/local/share/zsh/site-functions
    path=(/Applications/calibre.app/Contents/MacOS
          /Library/TeX/texbin
          /opt/X11/bin
          /usr/local/opt/coreutils/libexec/gnubin
          /usr/local/opt/gnu-sed/libexec/gnubin
          $path)
fi

## local

if [[ -f $HOME/.zshenv.local ]]; then
    source $HOME/.zshenv.local
fi
