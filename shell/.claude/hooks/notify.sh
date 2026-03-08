#!/usr/bin/env bash
# Claude Code notification hook
# Handles Stop, Notification, and PreToolUse events
# Sends desktop notifications via terminal-notifier (brew)

set -euo pipefail

input=$(cat)

session_id=$(echo "$input" | jq -r '.session_id // empty')
cwd=$(echo "$input" | jq -r '.cwd // empty')
notification_type=$(echo "$input" | jq -r '.notification_type // empty')
message=$(echo "$input" | jq -r '.message // empty')
tool_name=$(echo "$input" | jq -r '.tool_name // empty')
transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')

# Determine notification type, sound, and message
if [[ -n "$transcript_path" ]]; then
    type="task_complete"
    sound="Glass"
    msg=$(tac "$transcript_path" 2>/dev/null \
        | jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text' 2>/dev/null \
        | head -1 \
        | cut -c1-100)
    msg="${msg:-Task complete}"
elif [[ -n "$notification_type" ]]; then
    type="$notification_type"
    msg="${message:-Waiting for input}"
    case "$type" in
        permission_prompt) sound="Blow" ;;
        *) sound="Ping" ;;
    esac
elif [[ "$tool_name" == "ExitPlanMode" ]]; then
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

# Build focus script: switch to correct Ghostty window + tmux pane
focus_cmd="osascript -l JavaScript -e 'var se=Application(\"System Events\");var g=se.processes.byName(\"ghostty\");var items=g.menuBars[0].menuBarItems.byName(\"Window\").menus[0].menuItems();for(var i=0;i<items.length;i++){try{if(items[i].name().indexOf(\"${project}\")!==-1){items[i].click();break;}}catch(e){}}'"

# Detect tmux pane from parent claude process tty and append switch command
claude_tty=$(ps -o tty= -p $PPID 2>/dev/null | tr -d ' ')
if [[ -n "$claude_tty" && "$claude_tty" != "??" ]]; then
    tmux_target=$(tmux list-panes -a -F '#{pane_tty} #{pane_id}' 2>/dev/null \
        | grep "/dev/${claude_tty} " \
        | awk '{print $2}' \
        | head -1)
    if [[ -n "$tmux_target" ]]; then
        focus_cmd="${focus_cmd}; tmux select-window -t '${tmux_target}' \\; select-pane -t '${tmux_target}'"
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
