#!/usr/bin/env bash
# Claude Code notification hook
# Persistent alert when permission needed, temporary banner otherwise

input=$(cat)

eval "$(echo "$input" | jq -r '
    @sh "notification_type=\(.notification_type // "")",
    @sh "msg=\(.message // "Waiting for input")",
    @sh "cwd=\(.cwd // "")"
' 2>/dev/null)"

if [ -n "$cwd" ]; then
    git_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)
    if [ -n "$git_root" ]; then
        project=$(basename "$git_root")
    else
        project=$(basename "$cwd")
    fi
else
    project="unknown"
fi

title="Claude Code — $project"

if [ "$notification_type" = "permission_prompt" ]; then
    # Persistent alert — stays until dismissed
    alerter \
        --title "$title" \
        --message "$msg" \
        --sound Blow \
        --actions "Open" \
        --timeout 0 \
        2>/dev/null &
else
    # Temporary banner — auto-dismisses
    alerter \
        --title "$title" \
        --message "$msg" \
        --sound default \
        --timeout 5 \
        2>/dev/null &
fi

tmux display-message " $title: $msg" 2>/dev/null

true
