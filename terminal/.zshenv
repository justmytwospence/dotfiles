#!/usr/bin/env zsh

export ALTERNATE_EDITOR=
export DO_NOT_TRACK=1
export GEM_HOME=$HOME/gems
export GOPATH=$HOME/gocode
export HISTORY_IGNORE='(exit|reboot|rm *|shutdown now)'
export JUPYTER_DATA_DIR=$HOME/.local/share/jupyter
export LANG=en_US.UTF-8
export LANGUAGE=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export MANPAGER="vim -M +MANPAGER -"
export ZSH=$HOME/.zsh

path=(
    $GEM_HOME/bin
    $GOPATH/bin
    $HOME/.antigravity/antigravity/bin/
    $HOME/.cabal/bin
    $HOME/.emacs.d/term-cmd
    $HOME/.lmstudio/bin
    $HOME/.local/bin
    $HOME/.rbenv/shims
    $HOME/bin
    /opt/homebrew/bin
    /opt/homebrew/sbin
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
    # Detect Homebrew prefix (Apple Silicon vs Intel)
    if [[ -d /opt/homebrew ]]; then
        export HOMEBREW_PREFIX=/opt/homebrew
    else
        export HOMEBREW_PREFIX=/usr/local
    fi
    
    export MANPATH=$HOMEBREW_PREFIX/opt/coreutils/libexec/gnuman:$MANPATH
    export HOMEBREW_INSTALL_CLEANUP=true
    export HOMEBREW_UPGRADE_CLEANUP=true
    export PGDATA=$HOMEBREW_PREFIX/var/postgresql@17
    fpath+=$HOMEBREW_PREFIX/share/zsh/site-functions
    path=(
        /Applications/calibre.app/Contents/MacOS
        /Library/TeX/texbin
        /opt/X11/bin
        $HOMEBREW_PREFIX/opt/coreutils/libexec/gnubin
        $HOMEBREW_PREFIX/opt/gnu-sed/libexec/gnubin
        $path)
fi

## local

if [[ -f $HOME/.zshenv.local ]]; then
    source $HOME/.zshenv.local
fi

# Lazy load cargo - only add to path, don't source full env
[[ -d $HOME/.cargo/bin ]] && path=($HOME/.cargo/bin $path)

# Lazy load NVM - only set dir, load on first use of nvm/node/npm
export NVM_DIR="$HOME/.nvm"

nvm() {
    unset -f nvm node npm
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
    nvm "$@"
}

node() {
    unset -f nvm node npm
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
    node "$@"
}

npm() {
    unset -f nvm node npm
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
    npm "$@"
}

[[ "$TERM_PROGRAM" == "kiro" ]] && . "$(kiro --locate-shell-integration-path zsh)"

[[ "$TERM_PROGRAM" == "vscode" ]] && . "$(code --locate-shell-integration-path zsh)"
