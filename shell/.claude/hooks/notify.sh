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

# Turn ended -> update the tmux tab, no desktop notification. Two triggers:
#   Stop                    -- the turn completed normally
#   Notification/idle_prompt -- Claude's own "session is now idle" signal, which
#                               ALSO fires when a turn ended without a Stop hook
#                               (e.g. it was interrupted), so it clears tabs that
#                               Stop missed. Neither is a request for input.
# In the active window we clear the indicator; in a background window mark "done".
if [[ "$hook_event_name" == "Stop" || ( "$hook_event_name" == "Notification" && "$notification_type" == "idle_prompt" ) ]]; then
    if command -v tmux >/dev/null 2>&1; then
        pid=$$
        claude_tty=""
        while [ "$pid" -gt 1 ] 2>/dev/null; do
            tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
            if [ -n "$tty" ] && [ "$tty" != "??" ]; then
                claude_tty="$tty"; break
            fi
            pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        done
        if [ -n "$claude_tty" ]; then
            pane_id=$(tmux list-panes -a -F '#{pane_tty} #{pane_id}' 2>/dev/null \
                | grep "/dev/${claude_tty} " \
                | awk '{print $2}' \
                | head -1)
            if [ -n "$pane_id" ]; then
                # Claude finished its turn. In the active window clear the
                # indicator; in a background window mark it done (yellow).
                pane_active=$(tmux display-message -p -t "$pane_id" '#{window_active}' 2>/dev/null || true)
                if [[ "$pane_active" == "1" ]]; then
                    tmux set-option -pu -t "$pane_id" @cc_state 2>/dev/null
                else
                    tmux set-option -p -t "$pane_id" @cc_state done 2>/dev/null
                fi
                window_id=$(tmux display-message -p -t "$pane_id" '#{window_id}' 2>/dev/null)
                [ -n "$window_id" ] && "$HOME/.local/bin/tmux-claude-agg" --window "$window_id" "$session_id" 2>/dev/null
            fi
        fi
    fi
    exit 0
fi

# Determine notification type, sound, and message based on hook event
if [[ "$hook_event_name" == "Notification" ]]; then
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

# (idle_prompt is handled at the top -- it clears the tab and exits before here.)

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

# Lead the title with the agent's auto-generated name -- the clearest "which
# agent" -- falling back to the project. The name lives in the daemon's per-job
# state, keyed by the first 8 chars of the session id. When we have a name, fold
# the project into the subtitle so both are visible.
agent_name=""
if [[ -n "$session_id" ]]; then
    agent_name=$(jq -r '.name // empty' "$HOME/.claude/jobs/${session_id:0:8}/state.json" 2>/dev/null)
fi
if [[ -n "$agent_name" ]]; then
    title="$agent_name"
    [[ "$project" != "Claude Code" ]] && subtitle="$subtitle · $project"
else
    title="Claude Code -- $project"
fi

# --- SSH: prefer the reverse tunnel back to the Mac (full fidelity:
# terminal-notifier with per-event sounds, via claude-notify-recv). The
# tunnel is an ssh RemoteForward: remote 127.0.0.1:7877 -> the local
# launchd socket (com.spencerboucher.claude-notify). bash opens the port
# via /dev/tcp, so the remote host needs nothing installed; if the
# forward isn't up (or bash lacks /dev/tcp) fall back to escape
# sequences (Ghostty OSC 777 + BEL for sound).
if [[ -n "${SSH_CLIENT:-}${SSH_CONNECTION:-}" ]]; then
    port="${CLAUDE_NOTIFY_PORT:-7877}"
    payload=$(jq -cn \
        --arg title "$title" --arg subtitle "$subtitle" \
        --arg message "${msg:0:200}" --arg sound "$sound" \
        --arg session "${session_id:0:8}" \
        '{title: $title, subtitle: $subtitle, message: $message, sound: $sound, session: $session}')
    if printf '%s\n' "$payload" 2>/dev/null > "/dev/tcp/127.0.0.1/${port}"; then
        exit 0
    fi
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
pane_active=""
if [[ -n "$claude_tty" ]]; then
    tmux_target=$(tmux list-panes -a -F '#{pane_tty} #{pane_id}' 2>/dev/null \
        | grep "/dev/${claude_tty} " \
        | awk '{print $2}' \
        | head -1 \
        || true)
fi

# Flag the pane so its window tab turns red in the tmux status bar. Only set
# for prompts that actually need user action (permission_prompt,
# AskUserQuestion, ExitPlanMode); idle_prompt is skipped to avoid a
# sticky red tab during routine idle. Cleared on UserPromptSubmit.
if [[ -n "$tmux_target" ]]; then
    pane_active=$(tmux display-message -p -t "$tmux_target" '#{window_active}' 2>/dev/null || true)
    if [[ "$pane_active" != "1" && "$type" != "idle_prompt" ]]; then
        tmux set-option -p -t "$tmux_target" @cc_state waiting 2>/dev/null
        window_id=$(tmux display-message -p -t "$tmux_target" '#{window_id}' 2>/dev/null)
        [ -n "$window_id" ] && "$HOME/.local/bin/tmux-claude-agg" --window "$window_id" "$session_id" 2>/dev/null
    fi
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
