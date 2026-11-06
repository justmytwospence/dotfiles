#!/usr/bin/env zsh

autoload -Uz add-zsh-hook

function update-current-directory {
  local git_root=$(git rev-parse --show-toplevel 2>/dev/null)
  local dir=${git_root:-$PWD}
  if [[ -z $git_root ]]; then
    _prompt_pwd=%~
  else
    local parent=${git_root%/*}
    _prompt_pwd=${PWD#$parent/}
  fi
  if [[ -n $TMUX ]]; then
    tmux rename-window "${dir:t}"
  else
    print -Pn "\e]0;${dir:t:q}\a"
  fi
}
add-zsh-hook chpwd update-current-directory
update-current-directory

if [[ $TERM == eterm-color ]]; then
  add-zsh-hook chpwd eterm-track-directory
  function eterm-track-directory {
    print -P "\033AnSiTu %n"
    print -P '\033AnSiTc %d'
    if [[ -n $SSH_TTY || -n $SSH_CONNECTION ]]; then
      print "\033AnSiTh $(hostname)"
    else
      print "\033AnSiTh $(hostname -f)"
    fi
  }
  eterm-track-directory
fi
