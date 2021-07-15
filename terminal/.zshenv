#!/usr/bin/env zsh

export ALTERNATE_EDITOR=
export DO_NOT_TRACK=1
export GEM_HOME=$HOME/gems
export GOPATH=$HOME/gocode
export GPG_TTY=$(tty)
export HISTORY_IGNORE='(exit|reboot|rm *|shutdown now)'
export JUPYTER_DATA_DIR=$HOME/.local/share/jupyter
export LANG=en_US.UTF-8
export LANGUAGE=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export MANPAGER="vim -M +MANPAGER -"
export ZSH=$HOME/.zsh

path=(
    $BASE16_SHELL
    $GEM_HOME/bin
    $GOPATH/bin
    $HOME/.cabal/bin
    $HOME/.emacs.d/term-cmd
    $HOME/.local/bin
    $HOME/.rbenv/shims
    $HOME/bin
    /usr/local/bin
    /usr/local/sbin
    /usr/local/texlive
    /usr/share/zsh/share
    $path)

## emacs

if [[ $TERM == eterm-color ]]; then
    export EDITOR=emacsclient
else
    export EDITOR=vim
fi

## osx

if [[ $(uname) == Darwin ]]; then
    export MANPATH=/usr/local/opt/coreutils/libexec/gnuman:$MANPATH
    export HOMEBREW_INSTALL_CLEANUP=true
    export HOMEBREW_UPGRADE_CLEANUP=true
    export PGDATA=/usr/local/var/postgres
    fpath+=/usr/local/share/zsh/site-functions
    path=(
        $HOME/Library/Python/3.6/bin
        /Applications/calibre.app/Contents/MacOS
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
