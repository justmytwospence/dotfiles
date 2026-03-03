#!/usr/bin/env bash
# Claude Code notification hook
# Persistent alert when permission needed, temporary banner otherwise
# Clicking the notification activates Ghostty

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

tmux display-message " $title: $msg" 2>/dev/null

# Run alerter in background subshell so the hook returns immediately
(
    if [ "$notification_type" = "permission_prompt" ]; then
        result=$(alerter \
            --title "$title" \
            --message "$msg" \
            --group "$TMUX_PANE" \
            --sound Blow \
            --actions "Open" \
            --timeout 0 \
            2>/dev/null)
    else
        result=$(alerter \
            --title "$title" \
            --message "$msg" \
            --group "$TMUX_PANE" \
            --sound default \
            --timeout 5 \
            2>/dev/null)
    fi

    if [ "$result" != "@TIMEOUT" ] && [ "$result" != "@CLOSED" ]; then
        osascript -e 'tell application "Ghostty" to activate' 2>/dev/null
    fi
) &

true
