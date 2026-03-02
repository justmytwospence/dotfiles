#!/usr/bin/env bash

input=$(cat)

cwd=$(echo "$input" | jq -r '.cwd // empty')
cwd=${cwd:-$PWD}

# -- Left side: mirrors zsh prompt (user@host:dir branch (venv)) --

# Git-aware short directory
git_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)
if [ -n "$git_root" ]; then
    parent="${git_root%/*}"
    short_dir="${cwd#${parent}/}"
else
    home="$HOME"
    short_dir="${cwd/#$home/~}"
fi

# Git branch
branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null)

# Virtualenv
if [ -n "$VIRTUAL_ENV" ]; then
    venv_name=$(basename "$VIRTUAL_ENV")
fi

# Colors (base16 Tomorrow Night palette)
bold='\033[1m'
white='\033[1;37m'
cyan='\033[0;36m'
blue='\033[0;34m'
green='\033[0;32m'
yellow='\033[0;33m'
red='\033[0;31m'
dim='\033[0;90m'
reset='\033[0m'

# SSH detection
if [ -n "$SSH_TTY" ]; then
    at_color=$red
else
    at_color=$cyan
fi

# user@host:dir
printf "${white}%s${at_color}@%s${blue}:%s${reset}" \
    "$(whoami)" "$(hostname -s)" "$short_dir"

# branch
if [ -n "$branch" ]; then
    printf " ${white}%s${reset}" "$branch"
fi

# (venv)
if [ -n "$venv_name" ]; then
    printf " ${dim}(${cyan}%s${dim})${reset}" "$venv_name"
fi

# -- Right side: Claude info --

model=$(echo "$input" | jq -r '.model.display_name // empty')
remaining=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty')
cost=$(echo "$input" | jq -r '.cost.total_cost_usd // empty')
lines_added=$(echo "$input" | jq -r '.cost.total_lines_added // "0"')
lines_removed=$(echo "$input" | jq -r '.cost.total_lines_removed // "0"')

# Only show Claude info if we have model data
if [ -n "$model" ]; then
    printf " ${dim}|${reset}"

    # Model name
    printf " ${white}%s${reset}" "$model"

    # Context bar [========--] with color coding
    if [ -n "$remaining" ]; then
        remaining_int=${remaining%.*}

        # Color based on remaining context
        if [ "$remaining_int" -gt 50 ] 2>/dev/null; then
            bar_color=$green
        elif [ "$remaining_int" -gt 20 ] 2>/dev/null; then
            bar_color=$yellow
        else
            bar_color=$red
        fi

        # Build 10-char bar
        filled=$(( remaining_int / 10 ))
        empty=$(( 10 - filled ))
        bar=""
        for ((i=0; i<filled; i++)); do bar+="="; done
        for ((i=0; i<empty; i++)); do bar+="-"; done

        printf " ${bar_color}[%s]${reset} ${bar_color}%s%%${reset}" "$bar" "$remaining_int"
    fi

    # Cost
    if [ -n "$cost" ] && [ "$cost" != "0" ]; then
        printf " ${dim}\$%s${reset}" "$(printf '%.2f' "$cost")"
    fi

    # Lines changed (only if non-zero)
    if [ "$lines_added" != "0" ] || [ "$lines_removed" != "0" ]; then
        printf " "
        if [ "$lines_added" != "0" ]; then
            printf "${green}+%s${reset}" "$lines_added"
        fi
        if [ "$lines_removed" != "0" ]; then
            printf "${red}-%s${reset}" "$lines_removed"
        fi
    fi
fi
