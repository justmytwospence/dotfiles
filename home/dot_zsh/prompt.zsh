#!/usr/bin/env zsh

autoload -Uz add-zsh-hook

## timestamp

DEFAULT_TIMESTAMP="%F{white}%D{%H:%M}:--%f"
TIMESTAMP=$DEFAULT_TIMESTAMP

# show seconds in timestamp when command is about to execute...
function accept-line {
    TIMESTAMP="%F{white}%D{%H:%M:%S}%f"
    zle reset-prompt
    zle .accept-line
}
zle -N accept-line

# ...then reset timestamp back to hiding seconds
function reset-timestamp { TIMESTAMP=$DEFAULT_TIMESTAMP }
add-zsh-hook precmd reset-timestamp

## virtualenv

VIRTUAL_ENV_DISABLE_PROMPT=true
function virtualenv-prompt-info {
    if [[ -n $VIRTUAL_ENV ]]; then
        echo "%F{white}(%F{cyan}${VIRTUAL_ENV:t}%F{white})%f"
    fi
}

## mode

function state-toggle {
    if [[ $TERM == eterm-color ]]; then
        case $KEYMAP in
            opp|vicmd)
                print -n "\033TeRmCmD CursorShape 0"
                print -n "\033TeRmCmD LeaderToggle on"
                ;;
            viins|main)
                print -n "\033TeRmCmD CursorShape 1"
                print -n "\033TeRmCmD LeaderToggle off"
                ;;
        esac
    else
        # DECSCUSR sequences — works in all modern terminals and tmux 3.1+
        case $KEYMAP in
            opp|vicmd) print -n '\e[2 q';;  # block cursor
            viins|main) print -n '\e[6 q';; # line cursor
        esac
    fi
}

VIMODE='❯'
function zle-keymap-select zle-line-init {
    VIMODE=${${KEYMAP/(opp|vicmd)/:}/(main|viins)/❯}
    state-toggle
    zle reset-prompt
    zle -R
}
zle -N zle-keymap-select
zle -N zle-line-init

## vcs

# The same branch/dirty/ahead/behind line as every agent footer (~/.local/bin/git-status-line).
function update-vcs-prompt {
    local vcs
    vcs=$(git-status-line -f zsh 2>/dev/null)
    _prompt_vcs=${vcs:+"%F{white} ${vcs}%f "}
}
add-zsh-hook precmd update-vcs-prompt

## working directory

function update-pwd-prompt {
    local git_root=$(git rev-parse --show-toplevel 2>/dev/null)
    if [[ -z $git_root ]]; then
        _prompt_pwd=%~
    else
        local parent=${git_root%/*}
        _prompt_pwd=${PWD#$parent/}
    fi
}
add-zsh-hook precmd update-pwd-prompt

## host (computed once per session)

if [[ -z $SSH_TTY ]]; then
    _prompt_host="%F{cyan}@%m%f"
else
    _prompt_host="%F{red}@%m%f"
fi

## prompt

setopt prompt_subst

BG_JOBS="%F{blue}%(1j. •.)%(2j.%j.)%F{white}%f"

PROMPT='%B
%n${_prompt_host}%F{blue}:${_prompt_pwd}%f${_prompt_vcs}$(virtualenv-prompt-info)
${TIMESTAMP}${BG_JOBS} %(!.#.$VIMODE) %b'

## TRAMP

if [[ $TERM == "dumb" ]]; then
    export PS1="$ "
fi
