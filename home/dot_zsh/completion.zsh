#!/usr/bin/env zsh

# https://www.gnu.org/software/coreutils/manual/html_node/General-output-formatting.html
if command -v vivid >/dev/null 2>&1; then
    () {
        local theme=catppuccin-latte
        if [[ $(uname) == Darwin && $(defaults read -g AppleInterfaceStyle 2>/dev/null) == Dark ]]; then
            theme=snazzy
        fi
        local cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/zsh"
        local cache_file="$cache_dir/ls_colors.$theme"
        if [[ ! -s $cache_file ]]; then
            mkdir -p "$cache_dir"
            vivid generate "$theme" > "$cache_file.tmp.$$" && mv -f "$cache_file.tmp.$$" "$cache_file"
        fi
        export LS_COLORS="$(<$cache_file)"
    }
elif command -v dircolors >/dev/null 2>&1; then
    eval "$(dircolors -p | perl -pe 's/^((CAP|OTHER|SET|STICKY)\w+).*/$1 00/' | dircolors -)"
fi

# compinit and bashcompinit run once, from zinit's turbo load in .zshrc
# (zicompinit), after the completion plugins have added their functions.

zstyle ':completion:*' use-cache on
zstyle ':completion:*' cache-path "${XDG_CACHE_HOME:-$HOME/.cache}/zsh/zcompcache"
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'
zstyle ':completion:*' menu select
zstyle ':completion:*' group-name ''
zstyle ':completion:*' squeeze-slashes true
zstyle ':completion:*:descriptions' format '%F{yellow}-- %d --%f'
zstyle ':completion:*:warnings' format '%F{red}-- no matches found --%f'
zstyle ':completion:*:complete:*' matcher-list 'm:{[:lower:][:upper:]}={[:upper:][:lower:]}' '+l:|=* r:|=*'
zstyle ':completion:*:default' list-colors ${(s.:.)LS_COLORS}
zstyle ':completion:*:cd:*' ignore-parents parent pwd
zstyle ':completion:*:*:kill:*:processes' list-colors '=(#b) #([0-9]#) ([0-9a-z-]#)*=01;34=0=01'
