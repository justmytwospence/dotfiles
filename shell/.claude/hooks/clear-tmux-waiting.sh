#!/usr/bin/env bash
# Maintain the per-pane tmux option @cc_state that drives this pane's Claude
# tab indicator (aggregated per window by tmux-claude-agg):
#   running -> green tab. Set here on UserPromptSubmit and re-armed on every
#              PostToolUse, so turns that began without a UserPromptSubmit the
#              hook saw -- plan-mode resume after approval, Remote Control /rc
#              injected turns -- still go green. notify.sh sets waiting/done.
# Wired to UserPromptSubmit, PostToolUse, and SessionStart.
set -u

command -v tmux >/dev/null 2>&1 || exit 0

hook_event_name=""
session_id=""
if [ ! -t 0 ]; then
    input=$(cat 2>/dev/null || true)
    if [ -n "$input" ] && command -v jq >/dev/null 2>&1; then
        hook_event_name=$(echo "$input" | jq -r '.hook_event_name // empty' 2>/dev/null)
        session_id=$(echo "$input" | jq -r '.session_id // empty' 2>/dev/null)
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

case "$hook_event_name" in
    UserPromptSubmit|PostToolUse)
        # UserPromptSubmit: user just sent a prompt, Claude is about to run.
        # PostToolUse: Claude is mid-turn using tools. Either way it's working,
        # so (re)assert green. Overwriting @cc_state also clears any prior
        # waiting (red). The PostToolUse edge re-arms green for turns that began
        # without a UserPromptSubmit this hook saw (plan-mode resume after
        # approval, Remote Control /rc injected turns), which otherwise stay
        # blank for the whole turn. Stop clears it at turn end.
        tmux set-option -p -t "$pane_id" @cc_state running 2>/dev/null
        ;;
    SessionStart)
        # Fresh session / resume / /clear: nothing is running yet.
        tmux set-option -pu -t "$pane_id" @cc_state 2>/dev/null
        ;;
esac

# Recompute this window's tab now (a picker-opened bg session is a real pane,
# so unbind it from the detached-job map to avoid double-counting).
window_id=$(tmux display-message -p -t "$pane_id" '#{window_id}' 2>/dev/null)
[ -n "$window_id" ] && "$HOME/.local/bin/tmux-claude-agg" --window "$window_id" "$session_id" 2>/dev/null

exit 0
