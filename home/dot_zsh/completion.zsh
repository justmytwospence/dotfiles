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

# compinit and bashcompinit run once, from zinit's turbo load in .zshrc
# (zicompinit), after the completion plugins have added their functions.

zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'
zstyle ':completion:*' menu select
zstyle ':completion:*:complete:*' matcher-list 'm:{[:lower:][:upper:]}={[:upper:][:lower:]}' '+l:|=* r:|=*'
zstyle ':completion:*:default' list-colors ${(s.:.)LS_COLORS}

[[ -s $ZSH/completions/cortex.zsh ]] && source $ZSH/completions/cortex.zsh
