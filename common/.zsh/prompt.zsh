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
                echo '\033TeRmCmD CursorShape 0'
                echo '\033TeRmCmD LeaderToggle on'
                ;;
            viins|main)
                echo '\033TeRmCmD CursorShape 1'
                echo '\033TeRmCmD LeaderToggle off'
                ;;
        esac
    else
        if [[ $(uname) == Darwin ]]; then
            case $KEYMAP in
                opp|vicmd) print -n '\033]50;CursorShape=0\007';;
                viins|main) print -n  '\033]50;CursorShape=1\007';;
            esac
        elif [[ $(uname) == Linux ]]; then
            case $KEYMAP in
                opp|vicmd) print -n  '\e[2 q';;
                viins|main) print -n  '\e[6 q';;
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

# This mucks up the spacebar in interactive CLI tools
# TODO: figure out how to execute leader-toggle only for non-interactive
# commands
# if [[ $TERM == eterm-color ]]; then
#     add-zsh-hook preexec leader-toggle-on
#     function leader-toggle-on {
#         print '\033TeRmCmD LeaderToggle on'
#     }
# fi

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
    git_root=$PWD
    while [[ $git_root != / && ! -e $git_root/.git ]]; do
        git_root=$git_root:h
    done
    if [[ $git_root = / ]]; then
        unset git_root
        prompt_short_dir=%~
    else
        parent=${git_root%\/*}
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
