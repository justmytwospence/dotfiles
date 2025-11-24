#!/usr/bin/env zsh

autoload -Uz add-zsh-hook
autoload -Uz colors && colors

## timestamp

DEFAULT_TIMESTAMP="%{$fg[white]%}%D{%H:%M}:--"
TIMESTAMP=$DEFAULT_TIMESTAMP

# show seconds in timestamp when command is about to execute...
function accept-line {
    TIMESTAMP="%{$fg[white]%}%D{%H:%M:%S}"
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
        echo "%{$fg[white]%}(%{$fg[cyan]%}`basename "$VIRTUAL_ENV"`%{$fg[white]%})"
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
        # VS Code terminal uses standard ANSI sequences
        if [[ $TERM_PROGRAM == "vscode" ]]; then
            case $KEYMAP in
                opp|vicmd) print -n '\e[2 q';;  # block cursor
                viins|main) print -n '\e[6 q';; # line cursor
            esac
        elif [[ $(uname) == Darwin ]]; then
            # iTerm2-specific sequences
            case $KEYMAP in
                opp|vicmd) print -n '\033]50;CursorShape=0\007';;
                viins|main) print -n '\033]50;CursorShape=1\007';;
            esac
        elif [[ $(uname) == Linux ]]; then
            case $KEYMAP in
                opp|vicmd) print -n '\e[2 q';;
                viins|main) print -n '\e[6 q';;
            esac
        fi
    fi
}

function tmux-wrap-escape { print -n "\033Ptmux;\033$($1)\033\\" }

VIMODE='❯'
function zle-keymap-select zle-line-init {
    VIMODE=${${KEYMAP/(opp|vicmd)/:}/(main|viins)/❯}
    if [[ -n $TMUX ]]; then
        tmux-wrap-escape state-toggle
    else
        state-toggle
    fi
    zle reset-prompt
    zle -R
}
zle -N zle-keymap-select
zle -N zle-line-init

## vcs

autoload -Uz vcs_info
add-zsh-hook precmd vcs_info
zstyle ':vcs_info:*' enable git
zstyle ':vcs_info:*' formats "%b "

function vcs-prompt-info {
    if [[ -n $vcs_info_msg_0_ ]]; then
        echo "%{$fg[white]%} $vcs_info_msg_0_"
    fi
}

## working directory

function pwd-prompt-info {
    local git_root=$(git rev-parse --show-toplevel 2>/dev/null)
    if [[ -z $git_root ]]; then
        prompt_short_dir=%~
    else
        parent=${git_root%/*}
        prompt_short_dir=${PWD#$parent/}
    fi
    echo "%{$fg[blue]%}:$prompt_short_dir"
}

## host

function host-prompt-info {
    if [[ -z $SSH_TTY ]]; then
        echo "%{$fg[cyan]%}@%m"
    else
        echo "%{$fg[red]%}@%m"
    fi
}

## prompt

setopt prompt_subst

BG_JOBS="%{$fg[blue]%}%(1j. •.)%(2j.%j.)%{$fg[white]%}"

PROMPT='%B
%n$(host-prompt-info)$(pwd-prompt-info)$(vcs-prompt-info)$(virtualenv-prompt-info)
${TIMESTAMP}${BG_JOBS} %(!.#.$VIMODE) %b'

## TRAMP

if [[ $TERM == "dumb" ]]; then
    export PS1="$ "
fi
