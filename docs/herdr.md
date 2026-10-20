# herdr

[herdr](https://herdr.dev) is an agent multiplexer: a tmux-like terminal that runs
and supervises coding agents, showing each pane as blocked, working or done.
Homebrew installs it on the Mac; the NUC's was installed by hand.

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
- **One NUC server for every laptop.** Once per Mac, save the NUC as a herdr machine:
  `herdr machine add nuc --label NUC`. With only the default session running there,
  setup picks it (non-interactive setup uses `default` too); `herdr machine list` should
  show session `default`. The profile lives in herdr's client state, not in this repo.
  A profile targets one session, and the herdr web UI reads only the default one, so
  keep agent work out of named sessions on the NUC: their panes would be invisible to
  the phone and to other laptops. To repoint an old profile, `herdr machine remove <id>`
  and add it again. The old `homelab` session was
  migrated on 2026-10-15 (pi conversations resumed in the default server) and is stopped;
  its data stays in `~/.config/herdr/sessions/homelab` until deleted with
  `herdr session delete homelab`.
- **The NUC's server** (the default session; `homelab` until 2026-10-13) runs under
  the systemd user unit `herdr.service` (`dot_config/systemd/user/`, NUC only, enabled by its
  `default.target.wants` link; linger is on), so it starts at boot and no longer lives
  in the SSH login that happened to start it. The unit skips itself while a server for
  is already running unsupervised; to move one under it, detach every client (an
  attached Mac restarts a stopped server within a second), wait until no agent is
  working, then `herdr server stop && systemctl --user start herdr` (agents come back
  through `resume_agents_on_restore`). Upgrade the binary, then
  `systemctl --user restart herdr`; never `herdr update --handoff` there
  ([herdr#4972](https://github.com/herdrdev/herdr/issues/4972)). On a Mac, the last client
  detaching currently stops the local server and its panes
  ([herdr#4920](https://github.com/herdrdev/herdr/issues/4920)): keep a window
  attached, or run what must outlive it on the NUC.
- **Agent hooks**: `herdr integration install <claude|codex|pi|opencode>` writes
  herdr's own hook scripts (e.g. `~/.claude/hooks/herdr-agent-state.sh`) and an
  entry in each harness's settings. The repo's managed Claude Code and Codex hooks
  already carry that entry with a portable `$HOME` path, so the installer's copy
  is folded into it on the next apply. The setup scripts run the installer once
  per host; `herdr integration status` checks it.
- **pi-herdr**: pi's own additions (docs/plugins.md): `$bg` on the agent row
  (background work still to report back), `$pr` on the space rows, and `herdr_child`, which starts interactive pi children in
  a tab, a split or a new worktree's space and relays their replies.
- **Agent skill**: `dot_agents/skills/herdr/SKILL.md` lets an agent drive the
  multiplexer it runs inside. It self-gates on `HERDR_ENV=1`.
- **Alerts**: an agent on any connected machine turning blocked or done raises a
  toast, except on the tab you are viewing. Clicking it, or `Ctrl-b o` while it
  shows, focuses that agent's pane on its machine. These built-in toasts remain
  enabled for remote coverage; sounds still play. `done` means finished and not
  yet viewed: looking at the agent drops it to idle. Outside herdr, tmux-agents
  does the equivalent on tmux tabs; its hooks stay silent under `HERDR_ENV=1`.
- **Native Mac alerts**: `~/Projects/herdr-native-notify` is linked locally on the
  configured Mac (not yet published/pinned). One native helper, shown as **Herdr**
  (user-configured Persistent), sends every alert, so Notification Center stacks
  them per Herdr space; the title leads with herdr's `×` or `✓` for the state, and a
  pane's alert is replaced in place when its state changes. Blocked alerts have
  no age expiry and are removed on unblock; finished alerts are removed after
  8 seconds by default (expiry is per alert, not per app). `Ctrl-b :` > **Native notifications: finished duration**
  configures the interval, or `herdr-native-notify set-duration 12`. The managed
  input is `dot_config/herdr/plugins/config/herdr-native-notify/config.json`;
  the action updates chezmoi source rather than the deployed file. The managed
  LaunchAgent starts the recovery watcher at login. No Ghostty window is
  remembered: the terminal showing Herdr, and the machine it shows, come from
  Herdr's `herdr {hostname}: {workspace}` window title, so new windows and tabs
  need nothing. An alert is suppressed while that window is frontmost on the
  agent's machine with its pane focused. Clicks focus the Herdr terminal and
  pane, refusing replaced occupants. Saved machines the local Herdr
  UI is attached to (federation) also get native alerts automatically, with no
  extra window: the watcher reads them via `herdr --machine <id> api snapshot`
  only while the local client's remote bridge is live, and withdraws them on
  detach. Clicks land on the exact machine and pane whatever the window shows:
  Herdr has no API to switch machines (discussion #4396), so the click narrows
  the Agents list to the target with a temporary agent view and sends the
  reserved `next_agent` key `ctrl+alt+shift+f12` (in `config.toml.tmpl`) to that
  terminal. Details are in the plugin README. For a dedicated remote window with
  exact pane routing, use **Native notifications: connect remote** or run
  `herdr-native-notify connect` on the Mac. It uses the saved NUC profile, opens a
  dedicated Ghostty window and automatically owns SSH, exact-surface routing,
  reconnection and cleanup. No tunnel or manual remote binding is needed; no
  remote plugin is installed. An explicit target is
  `herdr-native-notify connect nuc` (default session). Normal SSH config/authentication
  remains authoritative. Arbitrary SSH windows are not silently monitored.
  Local-only TUI suppression in a federated window still needs upstream Herdr
  support. The native removal API also removes
  Notification Center history; desktop presentation timing is OS-controlled and
  best effort. Deployment/testing details are in the plugin's README.

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
| `G` | new worktree in `<repo>/.worktrees` (config popup over `herdr worktree create --path`) |
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
