#!/usr/bin/env bash
# UserPromptSubmit hook: clear the @claude_waiting flag on this Claude
# session's tmux window so its status-bar tab returns to normal color.
set -u

command -v tmux >/dev/null 2>&1 || exit 0

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

[ -n "$claude_tty" ] || exit 0

pane_id=$(tmux list-panes -a -F '#{pane_tty} #{pane_id}' 2>/dev/null \
    | grep "/dev/${claude_tty} " \
    | awk '{print $2}' \
    | head -1)

[ -n "$pane_id" ] || exit 0

tmux set-option -wu -t "$pane_id" @claude_waiting 2>/dev/null
exit 0
