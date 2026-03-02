#!/usr/bin/env bash
input=$(cat)

# -- Parse all fields in one jq call --
eval "$(echo "$input" | jq -r '
    @sh "model=\(.model.display_name // "")",
    @sh "used_pct=\(.context_window.used_percentage // 0 | floor)",
    @sh "cost=\(.cost.total_cost_usd // 0)",
    @sh "duration_ms=\(.cost.total_duration_ms // 0 | floor)",
    @sh "lines_added=\(.cost.total_lines_added // 0)",
    @sh "lines_removed=\(.cost.total_lines_removed // 0)",
    @sh "cwd=\(.cwd // "")",
    @sh "vim_mode=\(.vim.mode // "")"
' 2>/dev/null)"

cwd=${cwd:-$PWD}

# -- Colors --
cyan='\033[36m'  blue='\033[34m'  green='\033[32m'
yellow='\033[33m' red='\033[31m'  magenta='\033[35m'
dim='\033[90m'   white='\033[1;37m' reset='\033[0m'

# -- Directory & git --
git_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)
if [ -n "$git_root" ]; then
    short_dir=$(basename "$git_root")
    sub="${cwd#"$git_root"}"
    [ -n "$sub" ] && short_dir="${short_dir}${sub}"
else
    short_dir="${cwd/#$HOME/\~}"
fi
branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null)

# -- Duration --
total_secs=$((duration_ms / 1000))
if [ "$total_secs" -ge 3600 ]; then
    duration="$((total_secs / 3600))h$((total_secs % 3600 / 60))m"
elif [ "$total_secs" -ge 60 ]; then
    duration="$((total_secs / 60))m$((total_secs % 60))s"
else
    duration="${total_secs}s"
fi

# -- Context color --
if [ "$used_pct" -ge 90 ] 2>/dev/null; then
    bar_color=$red
elif [ "$used_pct" -ge 70 ] 2>/dev/null; then
    bar_color=$yellow
else
    bar_color=$green
fi

sep="${dim} · ${reset}"

# -- Build left side into a variable --
left=""
if [ -n "$vim_mode" ]; then
    if [ "$vim_mode" = "INSERT" ]; then
        left+="${green}${vim_mode}${reset}"
    else
        left+="${cyan}${vim_mode}${reset}"
    fi
    left+="$sep"
fi
left+="${magenta}${model:-...}${reset}"
left+="${sep}${blue}${short_dir}${reset}"
[ -n "$branch" ] && left+=" ${cyan}${branch}${reset}"
left+="${sep}${yellow}$(printf '$%.2f' "$cost")${reset}"
if [ "$lines_added" != "0" ] || [ "$lines_removed" != "0" ]; then
    left+="$sep"
    [ "$lines_added" != "0" ] && left+="${green}+${lines_added}${reset}"
    [ "$lines_removed" != "0" ] && left+=" ${red}-${lines_removed}${reset}"
fi
left+="${sep}${dim}${duration}${reset}"

# -- Output --
printf '%b' "$left"
printf "${sep}${bar_color}%s%%${reset}" "$used_pct"
