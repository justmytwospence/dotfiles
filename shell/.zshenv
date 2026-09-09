#!/usr/bin/env zsh

export ALTERNATE_EDITOR=
# export DO_NOT_TRACK=1
export GEM_HOME=$HOME/gems
export GOPATH=$HOME/gocode
export HISTORY_IGNORE='(exit|reboot|rm *|shutdown now)'
export JUPYTER_DATA_DIR=$HOME/.local/share/jupyter
export LANG=en_US.UTF-8
export LANGUAGE=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export MANPAGER="vim -M +MANPAGER -"
export FZF_DEFAULT_COMMAND='fd --type f --hidden --follow --exclude .git'
export FZF_DEFAULT_OPTS='--color=16'
export ZSH=$HOME/.zsh

path=(
    # local
    $HOME/.local/bin
    $HOME/bin

    # languages & package managers
    $GEM_HOME/bin
    $GOPATH/bin
    $HOME/.cabal/bin
    $HOME/.rbenv/shims

    # tools
    $HOME/.antigravity/antigravity/bin/
    $HOME/.emacs.d/term-cmd
    $HOME/.lmstudio/bin

    # system
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
    export PGDATA=$HOMEBREW_PREFIX/var/postgresql@17
    fpath+=$HOMEBREW_PREFIX/share/zsh/site-functions
    path=(
        /Applications/calibre.app/Contents/MacOS
        /Applications/Obsidian.app/Contents/MacOS
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

# NVM - put the default version's bin on PATH directly. Shimming only node/npm/
# npx/corepack/yarn left every other globally installed binary (defuddle,
# prettier, vercel, the npm-installed MCP servers) unresolvable in shells that
# never call one of the shims - notably non-interactive ones. `nvm` itself stays
# lazy; sourcing nvm.sh is the slow part, adding a directory to PATH is not.
export NVM_DIR="$HOME/.nvm"

if [[ -r $NVM_DIR/alias/default ]]; then
    nvm_bin=($NVM_DIR/versions/node/v${${(f)"$(<$NVM_DIR/alias/default)"}#v}*/bin(N))
    (( $#nvm_bin )) && path=($nvm_bin[-1] $path)
    unset nvm_bin
fi

nvm() { unset -f nvm; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; [ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"; nvm "$@" }

[[ "$TERM_PROGRAM" == "kiro" ]] && . "$(kiro --locate-shell-integration-path zsh)"

[[ "$TERM_PROGRAM" == "vscode" ]] && . "$(code --locate-shell-integration-path zsh)"
