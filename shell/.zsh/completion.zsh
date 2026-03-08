##!/usr/bin/env zsh

# https://www.gnu.org/software/coreutils/manual/html_node/General-output-formatting.html
eval $(dircolors -p | perl -pe 's/^((CAP|OTHER|SET|STICKY)\w+).*/$1 00/' | dircolors -)

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
