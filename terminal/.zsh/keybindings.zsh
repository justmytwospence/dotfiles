#!/usr/bin/env zsh

autoload -U is-at-least

# stty erase '^h'
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

function clear-scrollback-buffer {
  # Behavior of clear:
  # 1. clear scrollback if E3 cap is supported (terminal, platform specific)
  # 2. then clear visible screen
  # For some terminal 'e[3J' need to be sent explicitly to clear scrollback
  clear && printf '\e[3J'
  # .reset-prompt: bypass the zsh-syntax-highlighting wrapper
  # https://github.com/sorin-ionescu/prezto/issues/1026
  # https://github.com/zsh-users/zsh-autosuggestions/issues/107#issuecomment-183824034
  # -R: redisplay the prompt to avoid old prompts being eaten up
  # https://github.com/Powerlevel9k/powerlevel9k/pull/1176#discussion_r299303453
  # tput reset
  zle && zle .reset-prompt && zle -R
}

zle -N clear-scrollback-buffer
bindkey '^l' clear-scrollback-buffer

# edit-command-line
autoload -Uz edit-command-line
if [[ $TERM == eterm-color ]]; then
    bindkey -M vicmd 'V' edit-command-line-emacs
    bindkey -M vicmd 'v' edit-command-line-emacs
    zle -N edit-command-line-emacs
    function edit-command-line-emacs {
        print '\033TeRmCmD LeaderToggle off'
        edit-command-line
    }
else
    bindkey -M vicmd 'V' edit-command-line
    bindkey -M vicmd 'v' edit-command-line
    zle -N edit-command-line
fi

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

# vi-mode
if is-at-least 5.0.8; then

    bindkey -a j history-beginning-search-forward
    bindkey -a k history-beginning-search-backward

    # select-bracketed
    autoload -U select-bracketed
    for m in visual viopp; do
        for c in {a,i}${(s..)^:-'()[]{}<>bB'}; do
            bindkey -M $m $c select-bracketed
        done
    done
    zle -N select-bracketed

    # select-quoted
    autoload -U select-quoted
    for m in visual viopp; do
        for c in {a,i}{\',\",\`}; do
            bindkey -M $m $c select-quoted
        done
    done
    zle -N select-quoted

    # surround
    autoload -Uz surround
    bindkey -a cs change-surround
    bindkey -a ds delete-surround
    bindkey -a ys add-surround
    bindkey -M visual S add-surround
    zle -N delete-surround surround
    zle -N add-surround surround
    zle -N change-surround surround

fi

# plugins
bindkey '^g' zaw
bindkey '^r' zaw-history
bindkey '^t' zaw-process
bindkey '^o' zaw-systemctl-user
bindkey '^u' dwim

autoload -U filter-select; filter-select -i

zstyle ':filter-select' case-insensitive yes
zstyle ':filter-select' extended-search yes
zstyle ':filter-select' hist-find-no-dups yes
zstyle ':filter-select' max-lines 30
zstyle ':filter-select' rotate-list yes

bindkey -M filterselect '\e' send-break
bindkey -M filterselect '^[[3;5~' backward-kill-word
bindkey -M filterselect '^j' down-line-or-history
bindkey -M filterselect '^k' up-line-or-history

