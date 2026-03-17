##!/usr/bin/env zsh

autoload -Uz add-zsh-hook

if [[ -n $TMUX ]]; then
  add-zsh-hook chpwd tmux-track-directory
  function tmux-track-directory {
    local dir=${$(git rev-parse --show-toplevel 2>/dev/null):-$PWD}
    tmux rename-window "${dir:t}"
  }
else
  add-zsh-hook chpwd terminal-track-directory
  function terminal-track-directory {
    local dir=${$(git rev-parse --show-toplevel 2>/dev/null):-$PWD}
    echo -ne "\033]0;${dir:t}\007"
  }
fi

if [[ $TERM == eterm-color ]]; then
  add-zsh-hook chpwd eterm-track-directory
  function eterm-track-directory {
    print -P "\033AnSiTu %n"
    print -P '\033AnSiTc %d'
    if [[ -n "$SSH_TTY" ]]; then
      print "\033AnSiTh $(hostname)"
    else
      print "\033AnSiTh $(hostname -f)"
    fi
  }
  eterm-track-directory
fi
