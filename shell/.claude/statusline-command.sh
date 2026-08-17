#!/usr/bin/env bash
input=$(cat)

# printf/awk float formatting must not depend on the user's locale
export LC_NUMERIC=C

# -- Parse all fields in one jq call (`?` guards missing keys) --
eval "$(printf '%s' "$input" | jq -r '
    @sh "model=\(.model.display_name // "")",
    @sh "used_pct=\(.context_window.used_percentage // 0 | floor)",
    @sh "duration_ms=\(.cost.total_duration_ms // 0 | floor)",
    @sh "lines_added=\(.cost.total_lines_added // 0)",
    @sh "lines_removed=\(.cost.total_lines_removed // 0)",
    @sh "cost_usd=\(.cost.total_cost_usd // 0)",
    @sh "output_style=\(.output_style.name // "")",
    @sh "five_hour_reset=\((.rate_limits?.five_hour?.resets_at) // 0)",
    @sh "five_hour_used=\((.rate_limits?.five_hour?.used_percentage) // 0 | floor)",
    @sh "seven_day_reset=\((.rate_limits?.seven_day?.resets_at) // 0)",
    @sh "seven_day_used=\((.rate_limits?.seven_day?.used_percentage) // -1 | floor)",
    @sh "cc_version=\(.version // "")",
    @sh "cwd=\(.cwd // "")",
    @sh "transcript_path=\(.transcript_path // "")"
' 2>/dev/null)"

cwd=${cwd:-$PWD}

# -- OAuth usage cache --
# The stdin rate_limits block carries only the 5-hour and 7-day (all models)
# windows. The per-model weekly bucket ("Fable 5 limit" in /usage) exists only
# on the endpoint /usage itself queries: GET api.anthropic.com/api/oauth/usage.
# We refresh a cache in the background at most every $usage_ttl seconds and
# never block rendering on the network.
cache_dir=${CLAUDE_STATUSLINE_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/claude-statusline}
usage_cache=$cache_dir/oauth-usage.json
usage_ttl=300
mkdir -p "$cache_dir" 2>/dev/null

[ -n "$CLAUDE_STATUSLINE_DEBUG" ] && printf '%s' "$input" > "$cache_dir/last-stdin.json"

now=$(date +%s)

# stat(1) is not portable: -f %m is BSD/macOS, -c %Y is GNU/Linux. The Mac and
# the NUC both run this file, and on Linux the BSD form used to fail silently --
# every cache age read as infinite, so each render cleared the fetch lock and
# spawned another curl.
#
# Order matters: try the GNU form first. GNU stat *accepts* -f as
# --file-system and exits 0 while printing a block of filesystem stats, so a
# BSD-first probe never falls through on Linux -- it just returns garbage.
# BSD stat has no -c at all and exits 1, so it falls through cleanly on macOS.
mtime() {
    stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null
}

cache_age=999999
if [ -f "$usage_cache" ]; then
    cache_age=$(( now - $(mtime "$usage_cache" || echo 0) ))
fi
# Clear a lock left behind by a killed fetcher
if [ -d "$cache_dir/.fetch.lock" ]; then
    lock_age=$(( now - $(mtime "$cache_dir/.fetch.lock" || echo "$now") ))
    [ "$lock_age" -gt 120 ] && rmdir "$cache_dir/.fetch.lock" 2>/dev/null
fi
if [ "$cache_age" -gt "$usage_ttl" ] && mkdir "$cache_dir/.fetch.lock" 2>/dev/null; then
    (
        trap 'rmdir "$cache_dir/.fetch.lock" 2>/dev/null' EXIT
        # macOS: Claude Code stores OAuth creds in the Keychain (first access
        # pops a one-time dialog - click "Always Allow"). Linux: plain file.
        token=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null \
            | jq -r '.claudeAiOauth.accessToken // empty')
        if [ -z "$token" ] && [ -f "$HOME/.claude/.credentials.json" ]; then
            token=$(jq -r '.claudeAiOauth.accessToken // empty' "$HOME/.claude/.credentials.json" 2>/dev/null)
        fi
        # The User-Agent matters: without a claude-code/* UA this endpoint
        # lands in an aggressively rate-limited bucket and 429s forever.
        [ -n "$token" ] && curl -sf --max-time 4 "https://api.anthropic.com/api/oauth/usage" \
            -H "Authorization: Bearer $token" \
            -H "anthropic-beta: oauth-2025-04-20" \
            -H "Content-Type: application/json" \
            -H "User-Agent: claude-code/${cc_version:-2.1.0}" \
            -o "$usage_cache.tmp" && mv "$usage_cache.tmp" "$usage_cache"
    ) >/dev/null 2>&1 &
fi

# Pull the model-scoped weekly limit (Fable 5) out of the cached response.
# Primary: limits[] entries with kind=weekly_scoped and a model scope.
# Fallback: the seven_day_overage_included window if the API exposes it flat.
fable_pct=""
if [ -s "$usage_cache" ]; then
    IFS=$'\t' read -r fable_raw u7_raw <<EOF
$(jq -r '
    ( ((.limits // [])
        | map(select((.kind // "") == "weekly_scoped"
            and ((.scope.model.display_name // "") | ascii_downcase | contains("fable"))))
        | (.[0].percent // null))
      // (.seven_day_overage_included.utilization // null) ) as $f
    | [($f // "null" | tostring), ((.seven_day.utilization // "null") | tostring)]
    | @tsv' "$usage_cache" 2>/dev/null)
EOF
    if [ -n "$fable_raw" ] && [ "$fable_raw" != "null" ]; then
        # The endpoint has been observed reporting utilization both as a
        # 0-1 fraction and as a 0-100 percent. Calibrate against the stdin
        # seven_day used_percentage when we have both; else use a heuristic.
        fable_pct=$(awk -v f="$fable_raw" -v u7="$u7_raw" -v s7="$seven_day_used" 'BEGIN{
            scale = (f <= 1) ? 100 : 1
            # Calibrating against the weekly pair only discriminates when that
            # pair is nonzero: at 0 vs 0 both distances are 0 and the <= picks
            # 100, which multiplied a percent-scale Fable reading by 100 (2% ->
            # 200%) for the first hours of every new weekly window.
            if (u7 != "null" && u7 > 0 && s7 > 0) {
                d100 = u7 * 100 - s7; if (d100 < 0) d100 = -d100
                d1   = u7 - s7;       if (d1   < 0) d1   = -d1
                scale = (d100 <= d1) ? 100 : 1
            }
            p = f * scale + 0.5
            if (p < 0) p = 0
            if (p > 999) p = 999
            printf "%d", p
        }' 2>/dev/null)
    fi
fi

# -- Terminal width --
# Claude Code spawns the statusline without a controlling TTY, so </dev/tty
# fails and tput cols silently returns the terminfo default (often 80), which
# made the responsive layout hide the bars even on wide terminals. Walk up
# the process tree until we find an ancestor with a real TTY, then read its
# window size.
cols=$({ stty size </dev/tty | awk '{print $2}'; } 2>/dev/null)
if [ -z "$cols" ] || [ "$cols" = "0" ]; then
    pid=$PPID
    for _ in 1 2 3 4 5 6; do
        [ -z "$pid" ] || [ "$pid" = "0" ] || [ "$pid" = "1" ] && break
        tty_dev=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
        case "$tty_dev" in
            ''|\?*) ;;
            *)
                cols=$({ stty size <"/dev/$tty_dev" | awk '{print $2}'; } 2>/dev/null)
                [ -n "$cols" ] && [ "$cols" != "0" ] && break
                ;;
        esac
        pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
    done
fi
case "$cols" in ''|0) cols=${COLUMNS:-200} ;; esac
# Explicit override for testing or when TTY detection misbehaves
[ -n "$CLAUDE_STATUSLINE_COLS" ] && cols=$CLAUDE_STATUSLINE_COLS

# Reserve a margin so the rendered line is always strictly narrower than Claude
# Code's status area. Claude Code does NOT pass us its render width (verified: no
# width/cols field on stdin), so we detect the pane width above and lay out to it.
# But filling to the full width tears the display two ways:
#   1. last-column autowrap (DECAWM) leaves a pending wrap at the final cell;
#   2. Claude Code measures our line with its own wcwidth, which counts each
#      East-Asian-ambiguous Nerd Font icon as 1 cell while the terminal may draw
#      2 — so a line Claude thinks fits can wrap on screen, desyncing its inline
#      differential renderer and leaving stale rows until a ^L repaint.
# Holding two columns free guarantees no wrap regardless of that disagreement,
# without changing any glyph. Bump if you ever still see wrap (e.g. CJK in a path).
STATUS_WIDTH_MARGIN=2
cols=$(( cols - STATUS_WIDTH_MARGIN ))
[ "$cols" -lt 1 ] && cols=1

# -- Colors --
cyan='\033[36m'  blue='\033[34m'  green='\033[32m'
yellow='\033[33m' red='\033[31m'  magenta='\033[35m'
black='\033[30m'
# Faint on the default foreground, not a palette slot. Ghostty follows the system
# between custom-light and custom-dark, and a fixed slot inverts with it: palette 0
# is #282a2e on the dark background but #ece3cc on the light one, so "black" reads
# as near-white half the day. Dim stays a muted version of whatever the foreground
# currently is, in both themes.
dim='\033[2m'

reset='\033[0m'

# -- Nerd Font icons (each counted as 2 visible cells for width math) --
icon_model=$'\U000F06A9'     # nf-md-robot
icon_dir=$'\U000F024B'       # nf-md-folder
icon_branch=$'\UE725'        # nf-dev-git_branch
icon_clock=$'\U000F0150'     # nf-md-clock_fast
icon_ctx=$'\U000F05AF'       # nf-md-window_maximize (context window)
icon_block=$'\U000F0954'     # nf-md-timer_sand
icon_week=$'\U000F00ED'      # nf-md-calendar
icon_fable=$'\U000F0068'     # nf-md-auto_fix (weekly Fable 5 limit)
icon_style=$'\U000F03D7'     # nf-md-palette
icon_warm=$'\U000F0238'      # nf-md-fire (prompt cache still warm)
icon_cold=$'\U000F0717'      # nf-md-snowflake (prompt cache expired)
ICON_W=2                      # width budget per icon (most NF icons render 2-wide)

sep_str=" "
SEP_W=${#sep_str}

# Threshold-based color shared by most gauges. blue < 50% ≤ yellow < 80% ≤ red.
threshold_color() {
    local pct=$1
    if   [ "$pct" -ge 80 ]; then printf '%s' "$red"
    elif [ "$pct" -ge 50 ]; then printf '%s' "$yellow"
    else                         printf '%s' "$blue"
    fi
}

# The weekly Fable gauge runs to 100% like the others. The weekly_scoped percent
# is already a fraction of the Fable-only cap (Claude Code labels it the "Fable 5
# limit"), not of the all-models weekly pool -- the endpoint currently reports
# weekly_all at 34% and Fable at 46%, which only works if the denominators
# differ. 100% is the cliff: past it Fable runs on usage credits ("Now using
# usage credits for Fable") or stops. So the shared ramp applies, with red at 80%
# still arriving a fifth of the allowance short of the cliff. At 100% the bar
# goes black: no longer a warning, just the burnt-out state. Black is palette 0
# (#282a2e on the #1d1f21 background), so it reads as spent rather than as
# another alert competing with the gauges above it.
fable_threshold_color() {
    local pct=$1
    if [ "$pct" -ge 100 ]; then printf '%s' "$black"
    else                        threshold_color "$pct"
    fi
}

# Build a "<sep><color><icon> [<bar> ]<value><reset>" segment into a named var.
# When width=0 the bar is omitted (collapsed form).
build_gauge() {
    local _var=$1 color=$2 icon=$3 value=$4 pct=$5 width=$6
    if [ "$width" -gt 0 ]; then
        local filled=$(( pct * width / 100 ))
        [ "$filled" -gt "$width" ] && filled=$width
        local empty=$(( width - filled ))
        local bar="" i
        for ((i = 0; i < filled; i++)); do bar+="█"; done
        for ((i = 0; i < empty; i++)); do bar+="░"; done
        printf -v "$_var" '%s%s%s %s %s%s' "$sep_str" "$color" "$icon" "$bar" "$value" "$reset"
    else
        printf -v "$_var" '%s%s%s %s%s' "$sep_str" "$color" "$icon" "$value" "$reset"
    fi
}

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
    # --path-format needs git >= 2.31; an older git treats it as a pathspec and
    # echoes it back, which fed "--path-format=absolute\n.git" to dirname. Ask for
    # the plain form (relative to cwd on every version) and absolutize it here.
    git_common_dir=$(git -C "$cwd" rev-parse --git-common-dir 2>/dev/null)
    case "$git_common_dir" in
        /*) ;;
        '') ;;
        *) git_common_dir=$(cd "$cwd" && cd "$git_common_dir" 2>/dev/null && pwd) ;;
    esac
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
    secs_left=$(( five_hour_reset - now ))
    if [ "$secs_left" -gt 0 ]; then
        if [ "$secs_left" -ge 3600 ]; then
            block_reset="$((secs_left / 3600))h$((secs_left % 3600 / 60))m"
        else
            block_reset="$((secs_left / 60))m"
        fi
    fi
fi

# -- Static segments (always rendered the same; may be dropped to free space) --
model_txt="${model:-...}"
model_txt="${model_txt% (1M context)}"
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

# -- Prompt cache warmth --
# https://code.claude.com/docs/en/prompt-caching#cache-lifetime : cached prefixes
# expire after a gap of inactivity, and every request that hits the cache resets
# the timer. On a Claude subscription Claude Code asks for the 1-hour TTL; an API
# key or third-party provider gets 5 minutes unless ENABLE_PROMPT_CACHING_1H=1,
# and FORCE_PROMPT_CACHING_5M=1 overrides everything back down.
#
# Nothing on stdin reports cache state, so we infer the gap from the mtime of the
# transcript, which Claude Code appends to on every message and tool result. That
# tracks "time since the last turn" closely, but it is a proxy, not ground truth:
#   - it only measures elapsed time, so it cannot see the invalidations that are
#     not about time at all (model switch, /effort, /compact, an upgrade, an MCP
#     server reconnecting) -- those show warm here while actually being cold;
#   - background bash output appended during a break touches the transcript
#     without any request having refreshed the cache, reading as falsely warm;
#   - drawing on usage credits after passing a plan limit silently drops the TTL
#     to 5 minutes unless ENABLE_PROMPT_CACHING_1H=1, which we cannot detect.
# It is a hint about whether the next turn eats a full reprocess, not a promise.
cache_ttl=3600
if [ "$FORCE_PROMPT_CACHING_5M" = "1" ]; then
    cache_ttl=300
elif [ -z "$CLAUDE_CODE_USE_BEDROCK$CLAUDE_CODE_USE_VERTEX$ANTHROPIC_API_KEY" ] \
     || [ "$ENABLE_PROMPT_CACHING_1H" = "1" ]; then
    cache_ttl=3600
else
    cache_ttl=300
fi

seg_cache=""
seg_cache_w=0
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
    idle=$(( now - $(mtime "$transcript_path" || echo "$now") ))
    [ "$idle" -lt 0 ] && idle=0
    warm_left=$(( cache_ttl - idle ))
    if [ "$warm_left" -gt 0 ]; then
        if [ "$warm_left" -ge 3600 ]; then
            cache_txt="$((warm_left / 3600))h$((warm_left % 3600 / 60))m"
        elif [ "$warm_left" -ge 60 ]; then
            cache_txt="$((warm_left / 60))m"
        else
            cache_txt="${warm_left}s"
        fi
        # Warm is the uninteresting state, so it stays quiet until the window is
        # nearly gone: green with room to spare, yellow inside the last 5 minutes.
        if [ "$warm_left" -le 300 ]; then cache_color=$yellow; else cache_color=$green; fi
        cache_icon=$icon_warm
    else
        # Expired. Black, the same burnt-out treatment the Fable gauge gets past
        # its cliff -- the next turn reprocesses the history, but nothing is wrong.
        cache_txt="cold"
        cache_color=$black
        cache_icon=$icon_cold
    fi
    seg_cache="${sep_str}${cache_color}${cache_icon} ${cache_txt}${reset}"
    seg_cache_w=$(( SEP_W + ICON_W + 1 + ${#cache_txt} ))
fi

# -- Session cost (cost.total_cost_usd; needs Claude Code >= 2.1.211) --
seg_cost=""
seg_cost_w=0
case "$cost_usd" in
    ''|0|0.0) ;;
    *)
        cost_txt=$(printf '$%.2f' "$cost_usd" 2>/dev/null)
        if [ -n "$cost_txt" ] && [ "$cost_txt" != '$0.00' ]; then
            # Muted, not colored: the cost is there to glance at, and no
            # threshold ramp applies to it.
            seg_cost="${sep_str}${dim}${cost_txt}${reset}"
            seg_cost_w=$(( SEP_W + ${#cost_txt} ))
        fi
        ;;
esac

# -- Gauge inputs (built at the end via build_gauge once bar_width is decided) --
have_block=0
seg_block_w=0
if [ -n "$block_reset" ]; then
    have_block=1
    seg_block_w=$(( SEP_W + ICON_W + 1 + ${#block_reset} ))
fi
block_color=$(threshold_color "$five_hour_used")

# Weekly all-models gauge (stdin rate_limits.seven_day; -1 = not provided)
have_week=0
seg_week_w=0
week_val=""
if [ "$seven_day_used" -ge 0 ]; then
    have_week=1
    week_val="${seven_day_used}%"
    if [ "$seven_day_reset" != "0" ]; then
        wsecs=$(( seven_day_reset - now ))
        if [ "$wsecs" -ge 86400 ]; then
            week_val="${week_val} $((wsecs / 86400))d"
        elif [ "$wsecs" -gt 0 ]; then
            week_val="${week_val} $((wsecs / 3600))h"
        fi
    fi
    seg_week_w=$(( SEP_W + ICON_W + 1 + ${#week_val} ))
fi
week_color=$(threshold_color "${seven_day_used#-}")

# Weekly Fable 5 gauge (OAuth usage cache; absent until first successful fetch)
have_fable=0
seg_fable_w=0
fable_val=""
fable_color=$blue
if [ -n "$fable_pct" ]; then
    have_fable=1
    fable_val="${fable_pct}%"
    seg_fable_w=$(( SEP_W + ICON_W + 1 + ${#fable_val} ))
    fable_color=$(fable_threshold_color "$fable_pct")
fi

pct_txt="${used_pct}%"
ctx_no_bar_w=$(( SEP_W + ICON_W + 1 + ${#pct_txt} ))
ctx_color=$(threshold_color "$used_pct")

# -- Responsive layout --
# All gauges share one bar_width so they line up. Each bar costs
# (bar_width + 1) cells over its no-bar form (the +1 is the gap between bar
# and value). If we can't fit MIN_BAR per gauge, drop bars; if even no-bars
# overflows, drop segments in priority order
# (style → cache → duration → diff → block → week → branch → dir → cost).
# The Fable and context gauges are never dropped — they're the point.
MIN_BAR=8
MAX_BAR=30

total_fixed_w() {
    echo $(( seg_model_w + seg_dir_w + seg_branch_w + seg_diff_w
           + seg_style_w + seg_duration_w + seg_cache_w + seg_cost_w
           + seg_block_w + seg_week_w + seg_fable_w + ctx_no_bar_w ))
}

remaining=$(( cols - $(total_fixed_w) ))
num_bars=$(( 1 + have_block + have_week + have_fable ))
bar_width=0
if [ "$remaining" -ge $(( num_bars * MIN_BAR + num_bars )) ]; then
    bar_width=$(( (remaining - num_bars) / num_bars ))
    [ "$bar_width" -gt "$MAX_BAR" ] && bar_width=$MAX_BAR
fi

if [ "$bar_width" = "0" ]; then
    for drop_var in seg_style seg_cache seg_duration seg_diff seg_block seg_week seg_branch seg_dir seg_cost; do
        [ "$cols" -ge "$(total_fixed_w)" ] && break
        case "$drop_var" in
            seg_block)
                seg_block_w=0
                have_block=0
                ;;
            seg_week)
                seg_week_w=0
                have_week=0
                ;;
            *)
                eval "$drop_var=''"
                eval "${drop_var}_w=0"
                ;;
        esac
    done
fi

# -- Build the gauge segments now that bar_width is final --
seg_block=""
if [ "$have_block" = "1" ]; then
    build_gauge seg_block "$block_color" "$icon_block" "$block_reset" "$five_hour_used" "$bar_width"
fi
seg_week=""
if [ "$have_week" = "1" ]; then
    build_gauge seg_week "$week_color" "$icon_week" "$week_val" "$seven_day_used" "$bar_width"
fi
seg_fable=""
if [ "$have_fable" = "1" ]; then
    build_gauge seg_fable "$fable_color" "$icon_fable" "$fable_val" "$fable_pct" "$bar_width"
fi
build_gauge seg_ctx "$ctx_color" "$icon_ctx" "$pct_txt" "$used_pct" "$bar_width"

printf '%b' "${seg_model}${seg_dir}${seg_branch}${seg_diff}${seg_style}${seg_duration}${seg_cache}${seg_cost}${seg_block}${seg_week}${seg_fable}${seg_ctx}"
