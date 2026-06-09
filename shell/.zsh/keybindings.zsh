#!/usr/bin/env zsh

bindkey '^h' backward-kill-word

# vim
bindkey -v

# emacs
bindkey '^?' backward-delete-char
bindkey '^a' beginning-of-line
bindkey '^b' backward-char
bindkey '^e' end-of-line
bindkey '^f' forward-char
bindkey '^k' kill-line
bindkey '^n' history-beginning-search-forward
bindkey '^p' history-beginning-search-backward
bindkey '^w' backward-delete-word
bindkey -M vicmd '^k' kill-line

# menuselect
zmodload zsh/complist
bindkey -M menuselect '\e' undo
bindkey -M menuselect '^[[Z' reverse-menu-complete

# suspend
function fancy-ctrl-z {
    if [[ $#BUFFER -eq 0 ]]; then
        BUFFER=fg
        zle accept-line
    else
        zle push-input
        zle clear-screen
    fi
}
bindkey '^z' fancy-ctrl-z
zle -N fancy-ctrl-z

# plugins
# fzf handles ^r (history) and ^t (file finder) via `fzf --zsh`
bindkey '^u' dwim

# claude: translate the current line (natural language) into a shell command (Ctrl+G).
# Runs gencmd in the background and polls its live phase, so the status line shows a
# spinner and flips to "consulting opus…" when the Opus advisor is consulted. Then it
# replaces the buffer with the command and waits — review and press Enter to run.
function gencmd-widget {
    emulate -L zsh
    unsetopt monitor notify   # background job below must not print [1] pid / [1] done
    if [[ -z ${BUFFER//[[:space:]]/} ]]; then
        zle -M "gencmd: type what you want to do first"
        return 1
    fi
    local request=$BUFFER
    local saved_postdisplay=$POSTDISPLAY
    local statusfile resultfile
    statusfile=$(mktemp -t gencmd-status) || return 1
    resultfile=$(mktemp -t gencmd-result) || { command rm -f $statusfile; return 1; }
    print -r -- "asking claude" > $statusfile
    GENCMD_STATUS=$statusfile gencmd "$request" > $resultfile 2>/dev/null &
    local pid=$!
    local -a spin=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local i=1 phase
    while kill -0 $pid 2>/dev/null; do
        phase="$(<$statusfile)"
        POSTDISPLAY=$'\n'"${spin[i]} ${phase}…"
        (( i = i % $#spin + 1 ))
        zle -R
        sleep 0.1
    done
    wait $pid
    local cmd="$(<$resultfile)"
    command rm -f $statusfile $resultfile
    POSTDISPLAY=$saved_postdisplay
    if [[ -z $cmd ]]; then
        zle -M "gencmd: no command returned (claude error or not logged in)"
        zle reset-prompt
        return 1
    fi
    BUFFER=$cmd
    CURSOR=$#BUFFER
    zle reset-prompt
}
zle -N gencmd-widget
bindkey       '^g' gencmd-widget   # main keymap (viins, since bindkey -v)
bindkey -M vicmd '^g' gencmd-widget

