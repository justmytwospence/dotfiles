# herdr

[herdr](https://herdr.dev) is an agent multiplexer: a tmux-like terminal that runs
and supervises coding agents, showing each pane as blocked, working or done.
Homebrew installs it on the Mac; the exe VM and the m0 hub get it from the setup
scripts.

- **Config**: one template, `dot_config/herdr/config.toml.tmpl`, for every host.
  Shared: the `terminal` theme (follows Ghostty's light/dark), cwd-following
  splits, in-app toasts (`delivery = "herdr"`, top right), the priority-sorted
  Agents panel, symbol status indicators, one sidebar row per agent, pane history
  across restarts, 50 MB scrollback. Per host: the NUC opens new panes in
  `~/homelab`; the `[keys]` table and the custom-command popups are written only
  on the Macs, since key bindings are client-local (unless a client attaches with
  `--remote-keybindings server`) and custom commands run on whichever server is
  selected. Validate with
  `herdr config check`, hot-reload with `herdr server reload-config`.
- **Agent hooks**: `herdr integration install <claude|codex|pi|opencode>` writes
  herdr's own hook scripts (e.g. `~/.claude/hooks/herdr-agent-state.sh`) and an
  entry in each harness's settings. The repo's managed Claude Code and Codex hooks
  already carry that entry with a portable `$HOME` path, so the installer's copy
  is folded into it on the next apply. The setup scripts run the installer once
  per host; `herdr integration status` checks it.
- **Agent skill**: `dot_agents/skills/herdr/SKILL.md` lets an agent drive the
  multiplexer it runs inside. It self-gates on `HERDR_ENV=1`.
- **Alerts**: an agent on any connected machine turning blocked or done raises a
  toast, except on the tab you are viewing. Clicking it, or `Ctrl-b o` while it
  shows, focuses that agent's pane on its machine. There is no macOS notification
  (an OS notification click can only raise Ghostty); sounds still play. `done`
  means finished and not yet viewed: looking at the agent drops it to idle.
  Outside herdr, tmux-agents does the equivalent on tmux tabs; its hooks stay
  silent under `HERDR_ENV=1`.

## Navigation (Ctrl-b leader)

Spaces map to tmux windows; tabs are herdr's extra level within a space.

| After Ctrl-b | Action |
|---|---|
| `s`, `f` | Goto, every machine: spaces, tabs, agents; `/` begins search |
| `:` | fuzzy command palette (below) |
| `Ctrl-j` / `Ctrl-k` | next/previous space (sidebar order, selected machine only) |
| `Ctrl-h` / `Ctrl-l` | previous/next pane |
| `Ctrl-n` / `Ctrl-p`, `Alt-h` / `Alt-l` | next/previous tab |
| `h/j/k/l` | directional pane focus |
| `r` | resize mode |
| `Enter` | next agent in Agents panel order (most urgent first), any machine |
| `w` | space chooser across every machine: Ctrl-j/k or Up/Down, Enter, Esc |
| `n/p`, `1..9` | next/previous/indexed space |
| `Alt-1..9` | Nth agent across machines (also without the prefix) |
| `G` | new worktree (`~/.local/bin/worktree popup`) |
| `t` | toggle the file viewer split (herdr-file-viewer) |
| `o`, `Ctrl-o`, `;` | toast target, pane cycle, last pane |

Without the prefix, `Alt-1..9` focuses the Nth agent and `Alt-j`/`Alt-k` walk the
Agents list on any machine. To change machine use `Ctrl-b w`, `Alt-j/k` or Goto.
`Ctrl-b Ctrl-b` sends a literal prefix.

`Ctrl-b :` opens `~/.local/bin/herdr-commands`, an fzf popup over herdr's API
commands (new/rename/close space, tab or pane; split, focus, swap, resize, zoom;
reload config) and installed plugin actions, run against the pane it was opened
from on the machine you are viewing. Client-only actions (Goto, settings, copy
mode) are listed with their keys. Names are prompted for; closing and plugin
actions ask for `yes`. Needs Python 3 and fzf on each herdr host.

References: [keyboard](https://herdr.dev/docs/keyboard/),
[configuration](https://herdr.dev/docs/configuration/),
[agent view API](https://herdr.dev/docs/socket-api/#agent-view-queries).
