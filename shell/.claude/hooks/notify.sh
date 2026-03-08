#!/usr/bin/env bash
# Claude Code notification hook
# Handles Stop, Notification, and PreToolUse events
# Sends desktop notifications via terminal-notifier (brew)

set -euo pipefail

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
    msg=$(tac "$transcript_path" 2>/dev/null \
        | jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text' 2>/dev/null \
        | head -1 \
        | cut -c1-100)
    msg="${msg:-Task complete}"
elif [[ "$hook_event_name" == "Notification" ]]; then
    type="$notification_type"
    msg="${message:-Waiting for input}"
    case "$type" in
        permission_prompt) sound="Blow" ;;
        *) sound="Ping" ;;
    esac
elif [[ "$hook_event_name" == "PreToolUse" ]]; then
    if [[ "$tool_name" == "ExitPlanMode" ]]; then
        type="plan_ready"
        sound="Hero"
        msg="Plan ready for review"
    elif [[ "$tool_name" == "AskUserQuestion" ]]; then
        type="question"
        sound="Funk"
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
    last=$(stat -f %m "$cooldown_file" 2>/dev/null || echo 0)
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

# Build focus script: activate Ghostty + switch to correct tmux pane
focus_cmd="osascript -e 'tell application \"Ghostty\" to activate'"

# Detect tmux pane by walking up process tree to find a real TTY
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
if [[ -n "$claude_tty" ]]; then
    tmux_target=$(tmux list-panes -a -F '#{pane_tty} #{pane_id}' 2>/dev/null \
        | grep "/dev/${claude_tty} " \
        | awk '{print $2}' \
        | head -1)
    if [[ -n "$tmux_target" ]]; then
        focus_cmd="${focus_cmd}; /opt/homebrew/bin/tmux select-window -t '${tmux_target}' \\; select-pane -t '${tmux_target}'"
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
