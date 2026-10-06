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
export OPENCODE_ENABLE_EXA=1  # opencode's websearch tool; its planners and scouts research with it
export FZF_DEFAULT_COMMAND='fd --type f --hidden --follow --exclude .git'
export FZF_DEFAULT_OPTS='--color=16'
export ZSH=$HOME/.zsh

# Claude Code mods, checked out by `plugins sync` from shell.pins (README "Plugins").
# Only directories that exist, so a host that has not synced yet starts cleanly.
() {
  local dir dirs=()
  for dir in $HOME/.local/share/plugins/{claude-auto-effort,claude-code-playground/claude-code/mods/token-weather}; do
    [[ -d $dir ]] && dirs+=$dir
  done
  (( $#dirs )) && export CLAUDE_CODE_PLUGIN_DIRS=${(j.:.)dirs}
}

# pi-anthropic-auth reports a bundled Claude Code version (2.1.260 through 3.3.2)
# in its billing header, and Anthropic rejects newer models below a floor
# (2.1.280 as of 2026-09-28) with claude_code_version_too_old. This is the
# package's documented override; bump it if that error returns.
export PI_ANTHROPIC_AUTH_CLAUDE_CODE_VERSION=${PI_ANTHROPIC_AUTH_CLAUDE_CODE_VERSION:-2.1.284}
# pi-background-tasks also attributes Anthropic traffic, but only for models on
# its hard-coded list, and rejects the rest (claude-sonnet-5-5 as of 2.6.8).
# Leave attribution to pi-anthropic-auth by enabling every feature but that one.
# Its own delegate/fusion children still force it on, so those cannot run a
# model its list lacks. Add ",attribution" back once the package catches up.
export PI_BG_FEATURES=${PI_BG_FEATURES:-process,delegate,fusion,attested}
# Hide its footer update notice: it queries the registry directly, ignoring the
# npm min-release-age cooldown, so it flags versions pi install won't take yet.
export PI_BG_DISABLE_UPDATE_CHECK=${PI_BG_DISABLE_UPDATE_CHECK:-1}

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
    # Homebrew's bin is otherwise added only by `brew shellenv` in .zprofile, which
    # non-interactive SSH commands never read -- so `ssh mac mosh-server`, Moshi's
    # herdr session picker, and herdr's machine attach could not find brew tools.
    # Login shells still get brew's own ordering: path_helper and .zprofile run later.
    path=(
        /Applications/Obsidian.app/Contents/MacOS
        /Library/TeX/texbin
        /opt/X11/bin
        $HOMEBREW_PREFIX/opt/coreutils/libexec/gnubin
        $HOMEBREW_PREFIX/opt/gnu-sed/libexec/gnubin
        $HOMEBREW_PREFIX/bin
        $HOMEBREW_PREFIX/sbin
        $path)
fi

## local

# exe.dev's sshd runs with oom_score_adj -1000 and passes it to every session,
# which makes everything started over SSH -- the herdr server, its panes, agents
# and their jobs -- immune to the kernel OOM killer and invisible to earlyoom.
# A runaway job then livelocks the whole VM instead of being killed (2026-09-29).
# Raising the value needs no privilege; children inherit it. A no-op elsewhere.
if [[ $EUID != 0 && -w /proc/self/oom_score_adj && $(</proc/self/oom_score_adj) == -1000 ]]; then
    echo 0 >| /proc/self/oom_score_adj
fi

if [[ -f $HOME/.zshenv.local ]]; then
    source $HOME/.zshenv.local
fi

# Mac role (pro|air, set in ~/.zshenv.local) for osx/.Brewfile. brew scrubs every
# variable but HOMEBREW_* before evaluating a Brewfile, so mirror it under that
# prefix; brew forwards it to Ruby as-is (README "Mac roles").
[[ -n ${DOTFILES_ROLE-} ]] && export HOMEBREW_DOTFILES_ROLE=$DOTFILES_ROLE

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
