#!/usr/bin/env bash
# Maintain tmux window options that drive the status-bar tab indicator
# for this Claude session:
#   @claude_waiting  -> red (set by notify.sh on real prompts)
#   @claude_running  -> green tab (set here on UserPromptSubmit and re-armed
#                       on every PostToolUse, so turns that began without a
#                       UserPromptSubmit the hook saw -- plan-mode resume after
#                       approval, Remote Control /rc injected turns -- still go
#                       green; cleared by notify.sh on Stop)
# Wired to UserPromptSubmit, PostToolUse, and SessionStart.
set -u

command -v tmux >/dev/null 2>&1 || exit 0

hook_event_name=""
if [ ! -t 0 ]; then
    input=$(cat 2>/dev/null || true)
    if [ -n "$input" ] && command -v jq >/dev/null 2>&1; then
        hook_event_name=$(echo "$input" | jq -r '.hook_event_name // empty' 2>/dev/null)
    fi
fi

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

# Always clear the waiting flag — both prompts and session resets dismiss it.
tmux set-option -wu -t "$pane_id" @claude_waiting 2>/dev/null

case "$hook_event_name" in
    UserPromptSubmit|PostToolUse)
        # UserPromptSubmit: user just sent a prompt, Claude is about to run.
        # PostToolUse: Claude is mid-turn using tools. Either way it's working,
        # so (re)assert the spinner. The PostToolUse edge re-arms green for
        # turns that began without a UserPromptSubmit this hook saw (plan-mode
        # resume after approval, Remote Control /rc injected turns), which
        # otherwise stay blank for the whole turn. Stop clears it at turn end.
        tmux set-option -w -t "$pane_id" @claude_running 1 2>/dev/null
        ;;
    SessionStart)
        # Fresh session / resume / /clear: nothing is running yet.
        tmux set-option -wu -t "$pane_id" @claude_running 2>/dev/null
        ;;
esac

exit 0
