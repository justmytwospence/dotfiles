#!/usr/bin/env bash
input=$(cat)

# -- Parse all fields in one jq call (`?` guards missing keys) --
eval "$(printf '%s' "$input" | jq -r '
    @sh "model=\(.model.display_name // "")",
    @sh "used_pct=\(.context_window.used_percentage // 0 | floor)",
    @sh "duration_ms=\(.cost.total_duration_ms // 0 | floor)",
    @sh "lines_added=\(.cost.total_lines_added // 0)",
    @sh "lines_removed=\(.cost.total_lines_removed // 0)",
    @sh "output_style=\(.output_style.name // "")",
    @sh "five_hour_reset=\((.rate_limits?.five_hour?.resets_at) // 0)",
    @sh "cwd=\(.cwd // "")"
' 2>/dev/null)"

cwd=${cwd:-$PWD}

# -- Terminal width --
cols=$(stty size </dev/tty 2>/dev/null | awk '{print $2}')
[ -z "$cols" ] || [ "$cols" = "0" ] && cols=$(tput cols 2>/dev/null)
[ -z "$cols" ] || [ "$cols" = "0" ] && cols=${COLUMNS:-120}

# -- Colors --
cyan='\033[36m'  blue='\033[34m'  green='\033[32m'
yellow='\033[33m' red='\033[31m'  magenta='\033[35m'
reset='\033[0m'

# -- Nerd Font icons (each counted as 2 visible cells for width math) --
icon_model=$'\U000F06A9'     # nf-md-robot
icon_dir=$'\U000F024B'       # nf-md-folder
icon_branch=$'\UE725'        # nf-dev-git_branch
icon_clock=$'\U000F0150'     # nf-md-clock_fast
icon_ctx=$'\U000F035B'       # nf-md-memory
icon_block=$'\U000F0954'     # nf-md-timer_sand
icon_style=$'\U000F03D7'     # nf-md-palette
ICON_W=2                      # width budget per icon (most NF icons render 2-wide)

sep_str=" "
SEP_W=${#sep_str}

# Truncate long strings to keep the tail (more identifying info than the prefix).
# "feature/some-very-long-branch-name" -> "…ng-branch-name"
truncate_left() {
    local max=$1 s=$2
    if [ "${#s}" -gt "$max" ]; then
        printf '…%s' "${s: -$((max - 1))}"
    else
        printf '%s' "$s"
    fi
}

# -- Directory & git --
git_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)
in_worktree=0
if [ -n "$git_root" ]; then
    git_dir=$(git -C "$cwd" rev-parse --absolute-git-dir 2>/dev/null)
    git_common_dir=$(git -C "$cwd" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
    if [ -n "$git_common_dir" ] && [ "$git_dir" != "$git_common_dir" ]; then
        # In a linked worktree — show the main project name instead of the
        # worktree dir (which usually duplicates the branch name).
        in_worktree=1
        short_dir=$(basename "$(dirname "$git_common_dir")")
    else
        short_dir=$(basename "$git_root")
        sub="${cwd#"$git_root"}"
        [ -n "$sub" ] && short_dir="${short_dir}${sub}"
    fi
else
    short_dir="${cwd/#$HOME/\~}"
fi
short_dir=$(truncate_left 22 "$short_dir")
branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null)
# In a worktree the branch is the worktree's identifier — keep it whole.
if [ "$in_worktree" = "0" ]; then
    branch=$(truncate_left 22 "$branch")
fi

git_marks=""
git_marks_w=0
if [ -n "$branch" ]; then
    if [ -n "$(git -C "$cwd" status --porcelain 2>/dev/null)" ]; then
        git_marks+="${yellow}●${reset}"
        git_marks_w=$((git_marks_w + 1))
    fi
    counts=$(git -C "$cwd" rev-list --left-right --count '@{u}...HEAD' 2>/dev/null)
    if [ -n "$counts" ]; then
        behind=${counts%%$'\t'*}
        ahead=${counts##*$'\t'}
        if [ "$ahead" != "0" ]; then
            git_marks+="${green}↑${ahead}${reset}"
            git_marks_w=$((git_marks_w + 1 + ${#ahead}))
        fi
        if [ "$behind" != "0" ]; then
            git_marks+="${red}↓${behind}${reset}"
            git_marks_w=$((git_marks_w + 1 + ${#behind}))
        fi
    fi
fi

# -- Session duration --
total_secs=$((duration_ms / 1000))
if [ "$total_secs" -ge 3600 ]; then
    duration="$((total_secs / 3600))h$((total_secs % 3600 / 60))m"
elif [ "$total_secs" -ge 60 ]; then
    duration="$((total_secs / 60))m$((total_secs % 60))s"
else
    duration="${total_secs}s"
fi

# -- 5-hour rate-limit reset --
block_reset=""
if [ -n "$five_hour_reset" ] && [ "$five_hour_reset" != "0" ]; then
    secs_left=$(( five_hour_reset - $(date +%s) ))
    if [ "$secs_left" -gt 0 ]; then
        if [ "$secs_left" -ge 3600 ]; then
            block_reset="$((secs_left / 3600))h$((secs_left % 3600 / 60))m"
        else
            block_reset="$((secs_left / 60))m"
        fi
    fi
fi

# -- Context bar color (used for the icon + percent — matches the highest zone) --
if [ "$used_pct" -ge 80 ]; then
    bar_color=$red
elif [ "$used_pct" -ge 50 ]; then
    bar_color=$yellow
else
    bar_color=$blue
fi

# -- Build segments, tracking visible width alongside the rendered string --
# seg_X holds the rendered string (with colors); seg_X_w holds its visible cell width.

model_txt="${model:-...}"
seg_model="${magenta}${icon_model} ${model_txt}${reset}"
seg_model_w=$(( ICON_W + 1 + ${#model_txt} ))

seg_dir="${sep_str}${blue}${icon_dir} ${short_dir}${reset}"
seg_dir_w=$(( SEP_W + ICON_W + 1 + ${#short_dir} ))

seg_branch=""
seg_branch_w=0
if [ -n "$branch" ]; then
    seg_branch="${sep_str}${cyan}${icon_branch} ${branch}${reset}"
    seg_branch_w=$(( SEP_W + ICON_W + 1 + ${#branch} ))
    if [ -n "$git_marks" ]; then
        seg_branch+=" ${git_marks}"
        seg_branch_w=$(( seg_branch_w + 1 + git_marks_w ))
    fi
fi

seg_diff=""
seg_diff_w=0
if [ "$lines_added" != "0" ] && [ "$lines_removed" != "0" ]; then
    seg_diff="${sep_str}${green}+${lines_added}${reset} ${red}-${lines_removed}${reset}"
    seg_diff_w=$(( SEP_W + 1 + ${#lines_added} + 1 + 1 + ${#lines_removed} ))
elif [ "$lines_added" != "0" ]; then
    seg_diff="${sep_str}${green}+${lines_added}${reset}"
    seg_diff_w=$(( SEP_W + 1 + ${#lines_added} ))
elif [ "$lines_removed" != "0" ]; then
    seg_diff="${sep_str}${red}-${lines_removed}${reset}"
    seg_diff_w=$(( SEP_W + 1 + ${#lines_removed} ))
fi

seg_style=""
seg_style_w=0
if [ -n "$output_style" ] && [ "$output_style" != "default" ]; then
    seg_style="${sep_str}${magenta}${icon_style} ${output_style}${reset}"
    seg_style_w=$(( SEP_W + ICON_W + 1 + ${#output_style} ))
fi

seg_duration="${sep_str}${cyan}${icon_clock} ${duration}${reset}"
seg_duration_w=$(( SEP_W + ICON_W + 1 + ${#duration} ))

seg_block=""
seg_block_w=0
if [ -n "$block_reset" ]; then
    seg_block="${sep_str}${yellow}${icon_block} ${block_reset}${reset}"
    seg_block_w=$(( SEP_W + ICON_W + 1 + ${#block_reset} ))
fi

# Context segment width without a bar — just sep + icon + space + pct.
pct_txt="${used_pct}%"
ctx_no_bar_w=$(( SEP_W + ICON_W + 1 + ${#pct_txt} ))

# -- Responsive layout --
# The bar is decorative; we'd rather drop it than evict another segment.
# If the bar fits at MIN_BAR with everything else, render it.
# Otherwise hide the bar; if even that's too cramped, drop segments in
# priority order: style → 5h-reset → session timer → git +/- → branch → dir.
MIN_BAR=10
MAX_BAR=30

total_fixed_w() {
    echo $(( seg_model_w + seg_dir_w + seg_branch_w + seg_diff_w
           + seg_style_w + seg_duration_w + seg_block_w + ctx_no_bar_w ))
}

# Adding a bar costs one space + bar_width cells.
bar_space=$(( cols - $(total_fixed_w) - 1 ))

if [ "$bar_space" -lt "$MIN_BAR" ]; then
    # Hide the bar before touching other segments.
    for drop_var in seg_style seg_block seg_duration seg_diff seg_branch seg_dir; do
        [ "$cols" -ge "$(total_fixed_w)" ] && break
        eval "$drop_var=''"
        eval "${drop_var}_w=0"
    done
    ctx_mid=" "
else
    if [ "$bar_space" -gt "$MAX_BAR" ]; then
        bar_width=$MAX_BAR
    else
        bar_width=$bar_space
    fi
    filled=$(( used_pct * bar_width / 100 ))
    [ "$filled" -gt "$bar_width" ] && filled=$bar_width
    empty=$(( bar_width - filled ))
    bar=""
    for ((i = 0; i < filled; i++)); do bar+="█"; done
    for ((i = 0; i < empty; i++)); do bar+="░"; done
    ctx_mid=" ${bar} "
fi

left="${seg_model}${seg_dir}${seg_branch}${seg_diff}${seg_style}${seg_duration}${seg_block}${sep_str}${bar_color}${icon_ctx}${ctx_mid}${pct_txt}${reset}"

printf '%b' "$left"
