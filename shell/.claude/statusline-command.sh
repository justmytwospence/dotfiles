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
    @sh "cwd=\(.cwd // "")"
' 2>/dev/null)"

cwd=${cwd:-$PWD}

# -- Colors --
cyan='\033[36m'  blue='\033[34m'  green='\033[32m'
yellow='\033[33m' red='\033[31m'  magenta='\033[35m'
dim='\033[90m'   reset='\033[0m'

# -- Nerd Font icons --
icon_model=$'\U000F09F5'     # nf-md-creation (sparkle)
icon_dir=$'\U000F024B'       # nf-md-folder
icon_branch=$'\UE725'        # nf-dev-git_branch
icon_cost=$'\UF155'          # nf-fa-dollar
icon_clock=$'\U000F0150'     # nf-md-clock_fast (clock with speed lines)
icon_ctx=$'\U000F035B'       # nf-md-memory

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

# -- Context bar --
if [ "$used_pct" -ge 90 ] 2>/dev/null; then
    bar_color=$red
elif [ "$used_pct" -ge 70 ] 2>/dev/null; then
    bar_color=$yellow
else
    bar_color=$green
fi
filled=$((used_pct / 10))
empty=$((10 - filled))
bar=""
for ((i = 0; i < filled; i++)); do bar+="█"; done
for ((i = 0; i < empty; i++)); do bar+="░"; done

sep="${dim} · ${reset}"

# -- Build output --
left=""
left+="${magenta}${icon_model} ${model:-...}${reset}"
left+="${sep}${blue}${icon_dir} ${short_dir}${reset}"
[ -n "$branch" ] && left+=" ${cyan}${icon_branch} ${branch}${reset}"
if [ "$lines_added" != "0" ] || [ "$lines_removed" != "0" ]; then
    left+=" "
    [ "$lines_added" != "0" ] && left+="${green}+${lines_added}${reset}"
    [ "$lines_removed" != "0" ] && left+=" ${red}-${lines_removed}${reset}"
fi
left+="${sep}${yellow}${icon_cost} $(printf '$%.2f' "$cost")${reset}"
left+="${sep}${cyan}${icon_clock} ${duration}${reset}"
left+="${sep}${bar_color}${icon_ctx} ${bar} ${used_pct}%${reset}"

# -- Output --
printf '%b' "$left"
