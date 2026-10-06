---
description: Git worktrees in <project>/.worktrees -- new|open|rm|ls|path (opens a herdr space or tmux window)
---
This ran `worktree $ARGUMENTS` (~/.local/bin/worktree, the shared worktree script) before you saw this message:

```
!`set -- $ARGUMENTS; [ $# -gt 0 ] || set -- ls; WORKTREE_FOCUS=1 "$HOME/.local/bin/worktree" "$@" 2>&1; echo "[exit $?]"`
```

Report the result in one or two lines: the checkout path, and where it opened (herdr space, tmux window, or nowhere). Do not run the command again, and take no other action.
