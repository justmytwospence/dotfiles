#!/usr/bin/env bash

input=$(cat)

cwd=$(echo "$input" | jq -r '.cwd // empty')
cwd=${cwd:-$PWD}

# Git-aware short directory (mirrors pwd-prompt-info)
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
    venv_info=" (${venv_name})"
else
    venv_info=""
fi

# Model and context
model=$(echo "$input" | jq -r '.model.display_name // empty')
remaining=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty')

# SSH detection (red @ for SSH, cyan otherwise)
if [ -n "$SSH_TTY" ]; then
    at_color='\033[0;31m'   # red
else
    at_color='\033[0;36m'   # cyan
fi

blue='\033[0;34m'
white='\033[0;37m'
reset='\033[0m'

# Line 1: user@host:dir branch (venv)
printf "${white}%s${at_color}@%s${blue}:%s${reset}" \
    "$(whoami)" "$(hostname -s)" "$short_dir"

if [ -n "$branch" ]; then
    printf " ${white}%s${reset}" "$branch"
fi

if [ -n "$venv_info" ]; then
    printf "${white}%s${reset}" "$venv_info"
fi

# Line 2: timestamp | model ctx%
printf " ${white}%s${reset}" "$(date +%H:%M)"

if [ -n "$model" ]; then
    printf " ${white}| %s${reset}" "$model"
fi

if [ -n "$remaining" ]; then
    printf " ${white}ctx:%s%%${reset}" "$remaining"
fi
