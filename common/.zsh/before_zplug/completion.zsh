##!/usr/bin/env zsh

# https://www.gnu.org/software/coreutils/manual/html_node/General-output-formatting.html
eval $(dircolors -p | perl -pe 's/^((CAP|OTHER|SET|STICKY)\w+).*/$1 00/' | dircolors -)

# menuselect
autoload -U bashcompinit && bashcompinit
autoload -U compinit && compinit
zstyle ':completion:*' menu select
zstyle ':completion:*:complete:*' matcher-list 'm:{[:lower:][:upper:]}={[:upper:][:lower:]}' '+l:|=* r:|=*'
zstyle ':completion:*:default' list-colors ${(s.:.)LS_COLORS}
