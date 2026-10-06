#!/usr/bin/env zsh

# https://www.gnu.org/software/coreutils/manual/html_node/General-output-formatting.html
if command -v vivid >/dev/null 2>&1; then
    if [[ $(defaults read -g AppleInterfaceStyle 2>/dev/null) == "Dark" ]]; then
        export LS_COLORS="$(vivid generate snazzy)"
    else
        export LS_COLORS="$(vivid generate catppuccin-latte)"
    fi
else
    eval $(dircolors -p | perl -pe 's/^((CAP|OTHER|SET|STICKY)\w+).*/$1 00/' | dircolors -)
fi

# Only run compinit if it hasn't been run yet (e.g., by zinit)
if ! command -v compdef &> /dev/null; then
  autoload -U bashcompinit && bashcompinit
  # Use cached completion dump if less than 24 hours old
  autoload -Uz compinit
  setopt EXTENDEDGLOB
  for dump in $HOME/.zcompdump(#qN.m+1); do
    compinit
  done
  compinit -C
else
  # compinit already loaded, just ensure bashcompinit is available
  autoload -U bashcompinit && bashcompinit
fi

zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'
zstyle ':completion:*' menu select
zstyle ':completion:*:complete:*' matcher-list 'm:{[:lower:][:upper:]}={[:upper:][:lower:]}' '+l:|=* r:|=*'
zstyle ':completion:*:default' list-colors ${(s.:.)LS_COLORS}

[[ -s $ZSH/completions/cortex.zsh ]] && source $ZSH/completions/cortex.zsh
