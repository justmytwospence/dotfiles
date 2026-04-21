#!/usr/bin/env bash
# Claude Code notification hook
# Handles Stop, Notification, and PreToolUse events
# Sends desktop notifications via cmux (when available) or terminal-notifier

set -u

input=$(cat)

session_id=$(echo "$input" | jq -r '.session_id // empty')
cwd=$(echo "$input" | jq -r '.cwd // empty')
hook_event_name=$(echo "$input" | jq -r '.hook_event_name // empty')
notification_type=$(echo "$input" | jq -r '.notification_type // empty')
message=$(echo "$input" | jq -r '.message // empty')
tool_name=$(echo "$input" | jq -r '.tool_name // empty')
transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')

# Determine notification type, sound, and message based on hook event
if [[ "$hook_event_name" == "Stop" ]]; then
    type="task_complete"
    sound="Glass"
    subtitle="Task complete"
    msg=$(tac "$transcript_path" 2>/dev/null \
        | jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text' 2>/dev/null \
        | head -1 \
        | cut -c1-100 \
        || true)
    msg="${msg:-Task complete}"
elif [[ "$hook_event_name" == "Notification" ]]; then
    type="$notification_type"
    msg="${message:-Waiting for input}"
    case "$type" in
        permission_prompt) sound="Blow"; subtitle="Permission needed" ;;
        *) sound="Ping"; subtitle="Notification" ;;
    esac
elif [[ "$hook_event_name" == "PreToolUse" ]]; then
    if [[ "$tool_name" == "ExitPlanMode" ]]; then
        type="plan_ready"
        sound="Hero"
        subtitle="Plan ready"
        msg="Plan ready for review"
    elif [[ "$tool_name" == "AskUserQuestion" ]]; then
        type="question"
        sound="Funk"
        subtitle="Question"
        msg="Question waiting for answer"
    else
        exit 0
    fi
else
    exit 0
fi

# Cooldown (5s dedup per type, skip for permission_prompt)
cooldown_file="/tmp/claude-notify-${type}"
if [[ "$type" != "permission_prompt" && -f "$cooldown_file" ]]; then
    if [[ "$(uname)" == "Darwin" ]]; then
        last=$(stat -f %m "$cooldown_file" 2>/dev/null || echo 0)
    else
        last=$(stat -c %Y "$cooldown_file" 2>/dev/null || echo 0)
    fi
    now=$(date +%s)
    if (( now - last < 5 )); then
        exit 0
    fi
fi
touch "$cooldown_file"

# Project name from cwd
project="Claude Code"
if [[ -n "$cwd" ]]; then
    git_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)
    project=$(basename "${git_root:-$cwd}")
fi

title="Claude Code -- $project"

# --- SSH: use escape sequences (Ghostty OSC 777 + BEL for sound) ---
if [[ -n "${SSH_CLIENT:-}${SSH_CONNECTION:-}" ]]; then
    printf '\e]777;notify;%s;%s\a\a' "$title" "${msg:0:200}" > /dev/tty
    exit 0
fi

# --- cmux: native notifications with focus suppression built in ---
if [[ -n "${CMUX_WORKSPACE_ID:-}" ]]; then
    cmux notify \
        --title "$title" \
        --subtitle "$subtitle" \
        --body "${msg:0:200}" &
    exit 0
fi

# --- Linux: no desktop notification mechanism available ---
if [[ "$(uname)" != "Darwin" ]]; then
    exit 0
fi

# --- macOS: terminal-notifier for Ghostty / other terminals ---

# Walk process tree to find TTY
pid=$$
claude_tty=""
while [ "$pid" -gt 1 ] 2>/dev/null; do
    tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    if [ -n "$tty" ] && [ "$tty" != "??" ]; then
        claude_tty="$tty"
        break
    fi
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
done

# Detect tmux pane
tmux_target=""
if [[ -n "$claude_tty" ]]; then
    tmux_target=$(tmux list-panes -a -F '#{pane_tty} #{pane_id}' 2>/dev/null \
        | grep "/dev/${claude_tty} " \
        | awk '{print $2}' \
        | head -1 \
        || true)
fi

# Check if the terminal running Claude is the frontmost app.
# In tmux, the process tree goes through the tmux server (a daemon), so we
# walk the tmux client's parent chain instead of our own.
frontmost_pid=$(osascript -e 'tell application "System Events" to get unix id of first application process whose frontmost is true' 2>/dev/null || true)
terminal_is_focused=false
terminal_pid=""
if [[ -n "$frontmost_pid" ]]; then
    # Choose which process tree to walk: tmux client or our own
    if [[ -n "$tmux_target" ]]; then
        session=$(tmux display-message -p -t "$tmux_target" '#{session_name}' 2>/dev/null || true)
        walk_pid=$(tmux list-clients -t "$session" -F '#{client_pid}' 2>/dev/null | head -1 || true)
    else
        walk_pid=$$
    fi
    while [ "${walk_pid:-0}" -gt 1 ] 2>/dev/null; do
        if [[ "$walk_pid" == "$frontmost_pid" ]]; then
            terminal_is_focused=true
        fi
        app_path=$(ps -o comm= -p "$walk_pid" 2>/dev/null || true)
        if [[ -z "$terminal_pid" && "$app_path" == /Applications/* ]]; then
            terminal_pid="$walk_pid"
        fi
        [[ -n "$terminal_pid" && "$terminal_is_focused" == true ]] && break
        walk_pid=$(ps -o ppid= -p "$walk_pid" 2>/dev/null | tr -d ' ')
    done
fi

# Build focus script using terminal PID (no hardcoded app names)
focus_cmd=""
if [[ -n "$terminal_pid" ]]; then
    focus_cmd="osascript -e 'tell application \"System Events\" to set frontmost of (first application process whose unix id is ${terminal_pid}) to true'"
fi
if [[ -n "$tmux_target" ]]; then
    if [[ -n "$focus_cmd" ]]; then
        focus_cmd="${focus_cmd}; /opt/homebrew/bin/tmux select-window -t '${tmux_target}' \\; select-pane -t '${tmux_target}'"
    else
        focus_cmd="/opt/homebrew/bin/tmux select-window -t '${tmux_target}' \\; select-pane -t '${tmux_target}'"
    fi
fi

# Suppress notification if terminal is actively focused
if $terminal_is_focused; then
    if [[ -n "$tmux_target" ]]; then
        # tmux: suppress only if the exact pane's window is active
        pane_active=$(tmux display-message -p -t "$tmux_target" '#{window_active}' 2>/dev/null || true)
        [[ "$pane_active" == "1" ]] && exit 0
    else
        # Non-tmux: check if the active Ghostty tab's working directory matches ours.
        # This avoids suppressing notifications when Claude runs in a background tab.
        active_tab_cwd=$(osascript -e '
            tell application "Ghostty"
                set ft to focused terminal of selected tab of front window
                return working directory of ft
            end tell
        ' 2>/dev/null || true)
        if [[ -n "$active_tab_cwd" ]]; then
            # Suppress only if the active tab's cwd matches this session's cwd
            [[ "$active_tab_cwd" == "$cwd" ]] && exit 0
        else
            # Ghostty API unavailable (different terminal) -- fall back to app-level check
            exit 0
        fi
    fi
fi

# Send desktop notification in background
(
    terminal-notifier \
        -title "$title" \
        -message "${msg:0:200}" \
        -sound "$sound" \
        -group "claude-${session_id:-default}" \
        -execute "$focus_cmd"
) &

exit 0
