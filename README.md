# Dotfiles

Personal dotfiles managed with [GNU Stow](https://www.gnu.org/software/stow/).

## Bootstrap a Fresh Mac

### 1. Install Xcode Command Line Tools

```sh
xcode-select --install
```

Wait for the installation to complete before continuing.

### 2. Clone this repo

Use HTTPS for the initial clone (SSH keys don't exist yet):

```sh
git clone https://github.com/justmytwospence/dotfiles.git ~/dotfiles
```

### 3. Run the bootstrap script

```sh
~/dotfiles/osx/bin/bootstrap-osx pro   # or: air
```

This will:
- Save the Mac's role in `~/.zshenv.local` (see [Mac roles](#mac-roles))
- Install Homebrew
- Stow the `shell` and `osx` packages to `~`
- Install the Homebrew packages and casks from `.Brewfile` for that role
- Install Python via `uv`
- Install the Rust stable toolchain via `rustup`
- Set Homebrew's zsh as the default shell
- Install Vim plugins
- Apply macOS system preferences (keyboard, dock, Finder, trackpad, etc.)

### 4. Set up SSH keys

Generate a new SSH key and add it to GitHub:

```sh
ssh-keygen -t ed25519 -C "github@spencerboucher.com"
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

Copy the public key and [add it to GitHub](https://github.com/settings/keys):

```sh
pbcopy < ~/.ssh/id_ed25519.pub
```

Then switch the dotfiles remote to SSH:

```sh
cd ~/dotfiles
git remote set-url origin git@github.com:justmytwospence/dotfiles.git
```

### 5. Open a new terminal

Launch Ghostty (or any terminal). The first shell session will:
- Bootstrap the Zinit plugin manager
- Lazy-load NVM on first use of `node`/`npm`/`nvm`
- Initialize fzf, zoxide, atuin, direnv, and rbenv

In Pi fullscreen under Ghostty, hold **Shift+Command** while clicking a link on
macOS (**Shift+Ctrl** on Linux). This lets Ghostty open it while Pi keeps mouse
scrolling, selection, and the sticky-prompt click. The Mac's Ghostty config
explicitly enables `link-url` and leaves shifted mouse clicks uncaptured.

## Stow Packages

| Package | Purpose | Platform |
|---------|---------|----------|
| `shell` | zsh, vim, tmux, git, ranger, and CLI tool configs | All |
| `osx` | Brewfile (role-gated: pro/air), Ghostty, Karabiner, herdr, macOS bootstrap | macOS |
| `nuc` | Host-specific config for the NUC | NUC |
| `exe` | Host-specific config and bootstrap for exe.dev VMs | exe.dev |
| `m0` | herdr-machine0 hub and spoke bootstrap, hub herdr config | m0 hub, spokes |
| `paseo-machine0` | paseo-machine0 hub and spoke bootstrap | Paseo hub, spokes |
| `emacs` | Emacs configuration and snippets | All |
| `jupyter` | Jupyter and IPython configs | All |
| `desktop` | Alacritty, Kitty, VS Code, Terminator | Linux |
| `i3` | i3 window manager | Linux |
| `gnome` | GNOME desktop settings | Linux |

Only `shell` and `osx` are stowed by the bootstrap script. Stow others manually as needed:

```sh
cd ~/dotfiles
stow emacs
```

The NUC stows `shell` and `nuc`; an exe.dev VM stows `shell` and `exe`; the m0 hub
and machine0 spokes stow `shell` and `m0`; the Paseo hub and its spokes stow `shell`
and `paseo-machine0`. Restow with `dotfiles-restow` rather than `stow -R`
directly: stow aborts the whole package when any target is a file it does not own,
which silently stops new files from linking while already-linked ones keep updating.
`dotfiles-restow` retries with the conflicting paths excluded and reports them.
Files whose readers refuse symlinks can be listed in `<pkg>/.stow-copy` (none are
today), kept out of stow by `.stow-local-ignore`, and installed as real copies by
`dotfiles-restow`; a copy that has drifted from the repo is reported, never
overwritten.

## herdr

[herdr](https://herdr.dev) is an "agent multiplexer" -- a tmux-like terminal that
runs and supervises AI coding agents (Claude Code, etc.), showing each pane as
blocked / working / done. It's installed via the Brewfile and integrated here:

- **Config**: host-specific, because the three machines need different herdr configs.
  `osx/.config/herdr/config.toml` is the Mac's: `terminal` theme so herdr follows
  Ghostty's light/dark, cwd-following splits, and in-app toasts in the top
  right (`delivery = "herdr"`). All three carry
  the same tmux-shaped navigation keys. `nuc/.config/herdr/config.toml`
  is the NUC's headless remote workspace: panes default into `~/homelab`, and its
  toasts render in the attached UI on the Mac (`delivery = "herdr"`). `exe/.config/herdr/config.toml` is the same headless shape for an
  exe.dev VM, with cwd-following splits like the Mac. All three stow to
  `~/.config/herdr/`; only `config.toml` is tracked, so sockets, logs, and session
  state stay machine-local. Validate with `herdr config check`; hot-reload with
  `herdr server reload-config`.
- **Claude hook**: `herdr integration install claude` writes the herdr-managed
  `~/.claude/hooks/herdr-agent-state.sh`, which reports the Claude session to herdr
  so panes resume after a server restart. That script is herdr-owned and not
  tracked; `bootstrap-osx` reinstalls it, and the hook wiring lives in
  `shell/.claude/settings.json`.
- **Agent skill**: `shell/.agents/skills/herdr/SKILL.md` lets a Claude session drive
  the multiplexer it runs inside (split panes for tests/logs, `herdr agent wait` on
  siblings). It self-gates on `HERDR_ENV=1`, so it is inert outside herdr.
- **Agents panel and alerts**: plain herdr config, no plugin. The Mac sets
  `agent_panel_sort = "priority"` (one queue across machines: blocked, done,
  working, idle, newest change first), `status_indicators = "symbols"`, one row
  per agent (state icon, workspace, then the tab and machine only when they are
  not the defaults "1" and "Local"), and in-app toasts in the top right
  (`[ui.toast] delivery = "herdr"`, `position = "top-right"`) when an agent on any
  connected machine turns blocked or done, except on the tab you are viewing.
  Clicking a toast, or `Ctrl-b o` while it shows, focuses the agent's pane on its
  machine. There is no macOS notification: herdr has one delivery mode, and an OS
  notification click can only raise Ghostty, not reach a pane. Sounds still play.
  herdr's `done` means finished and not yet viewed: looking at the agent is the
  acknowledgement, and it drops to idle.
  Outside herdr, tmux-agents does the equivalent on tmux window tabs (see
  "Plugins"); its hooks stay silent when `HERDR_ENV=1`.

### Navigation (Ctrl-b leader)

Spaces map to tmux windows; tabs are windows/layouts within one space. Ordinary
bindings are client-local, while custom commands execute on the selected server.

| After Ctrl-b | Action |
|---|---|
| `s`, `f` | Native Goto, every machine: spaces, tabs, agents; `/` begins search |
| `:` | Fuzzy command palette (see below) |
| `Ctrl-j` / `Ctrl-k` | Next/previous space (down/up sidebar order) |
| `Ctrl-h` / `Ctrl-l` | Previous/next pane, cycling through any split layout |
| `Ctrl-n` / `Ctrl-p` | Next/previous tab/window within the space |
| `Alt-h` / `Alt-l` | Previous/next tab/window aliases |
| `h/j/k/l` | Directional pane focus |
| `r` | Resize mode (Ctrl-h/j/k/l no longer resize) |
| `Enter` | Next agent in Agents panel order (most urgent first), any machine |
| `w` | Space chooser across every machine: Ctrl-j/k or Up/Down, Enter, Esc |
| `n/p`, `1..9` | Ordinary next/previous/indexed space |
| `Alt-1..9` | Indexed agent in the combined cross-machine sidebar (also without the prefix) |
| `G` | Unified worktree creation |
| `o`, `Ctrl-o`, `;` | Toast target (the agent behind the visible toast), pane cycle, last pane |

Without the prefix: `Alt-1..9` focuses the Nth agent and `Alt-j` / `Alt-k` walk down/up
the Agents list, on any machine; hold Alt to keep going.

`Ctrl-b Ctrl-j/k` moves through the selected machine's spaces
only: herdr's next/previous space never crosses machines. To change machine, use
`Ctrl-b w` then `Ctrl-j/k` and Enter, `Alt-j/k` for agents, or Goto (`Ctrl-b s`).

`f` mirrors tmux's find-window key. `Shift-Left/Right` remain tab aliases.
`Ctrl-b Ctrl-b` retains native literal-prefix passthrough.

Goto (`Ctrl-b s` or `f`), `Ctrl-b w`, and the agent keys span every connected machine.
Goto needs `/` before searching, offers `j/k` and arrows, workspace sections via
Left/Right, and native `b/w/i/d` filters (`a` restores all). Custom popup commands run
on the selected server only, so nothing here relies on one.
Native client-only actions (Settings, Copy mode, etc.) and every configured native
binding are searchable **Shortcut** rows: Enter shows how to invoke them after
closing the popup, rather than pretending an unsupported API exists. The unified
worktree shortcut is a hint too, so this picker never creates native worktrees.
Herdr already offers Goto and `/` filtering in keybinding help, not this combined
executable fzf palette. It is not an index of unopened projects or filesystem files.

`Ctrl-b :` opens `shell/.local/bin/herdr-commands`, an fzf popup (type to filter, no
`/`) over herdr's API commands (new/rename/close space, tab or pane; split, focus,
swap, resize, zoom; next/previous; reload config) and installed plugin actions, run
against the pane it was opened from. herdr runs popups on the machine you are viewing,
so the commands act there; it cannot switch machines, which Goto and the agent keys
do. Client-only actions (Goto, settings, copy mode, ...) are listed with their keys.
Names are prompted for; closing and plugin actions ask for `yes`. Needs Python 3 and
fzf on each herdr host (all have it).

Inherited fzf options are ignored; missing dependencies/API failures remain visible
in the popup.

References: [Herdr keyboard](https://herdr.dev/docs/keyboard/),
[configuration](https://herdr.dev/docs/configuration/),
[Agent view API](https://herdr.dev/docs/socket-api/#agent-view-queries).

### Plugins

Every plugin maintained here (the pi extensions, the herdr plugins, tmux-agents,
anthropic-billing-guard and paseo-machine0, listed below) lives in its own public repo and is
developed in `~/Projects/<plugin>`. Repos are named `<host>-<feature>` (`pi-`, `herdr-`), or by
feature when they serve several harnesses, and the repo name and the `~/Projects` directory
match. On a new Mac, clone each repo into `~/Projects` (with the `upstream` remote for the
pi-plan-mode fork). The pi extensions typecheck and test with
`npm ci && npm run check` in their checkout.

Dotfiles vendors no plugin code: it holds only the commit each plugin is pinned to, and each
host program installs the plugin itself. `plugins` (`shell/.local/bin/plugins`) reads the pins
and makes every install match them:

- **pi extensions** are git packages in `shell/.pi/agent/settings.json`, e.g.
  `git:github.com/justmytwospence/pi-tool-gate@<commit>`. pi clones each into
  `~/.pi/agent/git/github.com/justmytwospence/<plugin>` the first time it starts, but does
  not move an existing clone when the pin changes; `plugins sync` does.
- **opencode plugins** are git specs in `shell/.config/opencode/opencode.jsonc`'s `plugin`
  list, `"<name>@github:justmytwospence/<plugin>#<commit>"`. opencode installs each pin into
  `~/.cache/opencode/packages/` at startup (no build step; the npm cooldown does not apply to
  git), so `plugins sync` has nothing to do for them. `plugins try` prints an `OPENCODE_CONFIG`
  that loads the checkout as `<name>@file:<path>`, which replaces the pin (opencode keeps one
  plugin per package name).
- **everything else** is one line per plugin in a `.pins` file next to the config that uses
  it, so a host gets exactly the plugins of the packages stowed on it:
  `shell/.config/plugins/shell.pins` (every host), `osx/.config/plugins/osx.pins`, `nuc/...`,
  `exe/...`, `m0/...`, `paseo-machine0/...`. A line is `<kind> <owner>/<repo> <commit>`:
  - `herdr`: `herdr plugin install <owner>/<repo> --ref <commit>`, which runs the plugin's
    build step and registers it (the managed checkout lives under
    `~/.config/herdr/plugins/github/`). On a host without herdr the plugin is a plain
    checkout, so hooks that call into it still work.
  - `tmux`: a checkout under `~/.tmux/plugins/`, where `.tmux.conf` lists it as a TPM
    `@plugin`.
  - `git`: a plain checkout.

  Each such plugin is reachable at `~/.local/share/plugins/<repo>` (the checkout, or a link
  to where the host program installed it); the Claude Code and Codex hooks, the LaunchAgents,
  the opencode links and the `spoke` and `paseo-machine0` symlinks use that path.

```sh
plugins list              # every pin on this host and what is checked out
plugins sync              # install or move every plugin to its pin (after a dotfiles pull;
                          # the dotfiles-sync skill and the spoke sync scripts run it)
cd ~/Projects/<plugin>    # edit, test, commit here
plugins try <plugin>      # check this commit out in every installed copy (Mac), then
                          # /reload pi, `tmux source ~/.tmux.conf`, or the herdr reapply action
git push                  # publish the plugin
plugins pin <plugin>      # pin that commit in every pins file and settings.json (refuses
                          # unpushed commits) and sync
cd ~/dotfiles && git add -p shell/.pi/agent/settings.json '*/.config/plugins/*.pins' \
  && git commit -m "chore(plugins): bump <plugin>" && git push
```

Installing a herdr plugin does not run its startup hook: after a bump run its reapply action,
if it has one, or restart herdr. Push the plugin
before dotfiles, or the other machines cannot fetch the pinned commit.

Third-party plugins can instead be installed straight from GitHub with
`herdr plugin install <owner>/<repo> --yes`. The marketplace is public repos tagged
`herdr-plugin`.

- **pi extensions**, each a pinned git package in `shell/.pi/agent/settings.json`
  (`/reload` after a bump):
  - **pi-status-footer** -- the footer: project and branch, model, context gauge,
    session cost and Claude/Codex plan limits (`/status`). pi-cc-extensions'
    competing footer is off in `shell/.pi/agent/pi-cc-extensions.json`.
  - **pi-rewind** -- restores files alongside `/tree` and `/fork` from git tree
    snapshots; `/rewind-undo`.
  - **pi-clear-screen** -- `ctrl+l` clears the fullscreen transcript like a shell,
    keeping history. The model selector moved to `alt+m` and the tree's
    labeled-only filter to `ctrl+shift+l` in `shell/.pi/agent/keybindings.json`.
  - **pi-select-nav** -- `ctrl+j`/`ctrl+k` move in every picker, `j`/`k` in pickers
    without a text field, built-in or from any plugin. `keybindings.json` adds
    `ctrl+j`/`ctrl+k` to `tui.select.*` for keybinding-aware lists.
  - **pi-herdr-scrollbar-width** -- keeps the fullscreen exit transcript from
    wrapping in herdr panes with scrollbars.
  - **anthropic-billing-guard** -- see "Claude subscription billing"; also a `git`
    pin in `shell.pins`, which the opencode link
    `shell/.config/opencode/plugins/anthropic-billing-guard.js` points into.
  - **pi-brokered-auth** -- OAuth providers whose credentials come from a file a
    hub keeps fresh (`PI_BROKERED_AUTH_FILE`), so a rotating refresh token lives
    in one place. Inert without the variable; used on paseo-machine0 hosts (see
    "Paseo spokes on machine0").
  - **pi-subagents** -- the `subagent` tool: single, parallel and chain runs of
    `pi --mode rpc` children, foreground or async, fresh or forked context,
    optional worktrees, steer/stop/status; `/subagents`. Replaces the npm
    `pi-subagents`. Jev picks the agent, the model tier
    (`shell/.pi/agent/pi-subagents.json`) and the effort a call leaves open.
  - The Jev plugins below each call Jev through Pi's own classifier models
    (`ctx.modelRegistry.classify`, the `typesafe` provider and
    `TYPESAFE_API_KEY`), stand alone, fall back to Pi's normal behavior
    without it, record decisions as session entries, and read
    `~/.pi/agent/<name>.json` (defaults in each README):
    - **pi-tool-gate** -- auto-approves tool calls: read-only calls run, a short
      dangerous list asks you, Jev judges the rest; one push-back to the agent,
      then it asks you. Project rules in `.pi/tool-gate-rules.md`. `/gate`.
    - **pi-lean-context** -- Jev trims large tool output to what the step needs
      before it enters the context (full output saved to a file), and
      `/compact-jev` compacts in about a second with no LLM.
    - **pi-auto-effort** -- sets the thinking level per message you send,
      smoothed, capped at your last manual level. `/auto-effort`.
    - **pi-copy** -- `/yank` and `ctrl+shift+x`: a picker of replies, code,
      commands, paths and URLs from the session, ranked by Jev. Built-in
      `/copy` and `ctrl+x` are unchanged.
  - `shell/.pi/agent/extensions/worktree.ts` stays here: it is only a front end
    to `shell/.local/bin/worktree`.

- **herdr-machine0** (`m0.pins`,
  [repo](https://github.com/justmytwospence/herdr-machine0)) -- the m0 hub's
  plugin and the `spoke` CLI (`~/.local/bin/spoke` links into the install on the
  hub; spokes get a copy the hub pushes); see "machine0 spokes with an exe.dev
  hub". Its startup hook runs `spoke hubd`, which only the hub's herdr server
  triggers. Tests:
  `python3 -B -m unittest discover -s tests -t .` in its checkout.
- **paseo-machine0** (`paseo-machine0.pins`, a `git` pin,
  [repo](https://github.com/justmytwospence/paseo-machine0)) -- not a herdr
  plugin: the `paseo-machine0` CLI (`~/.local/bin/paseo-machine0` links into the
  checkout on the Paseo hub and every spoke), hubd (a systemd user unit on the
  hub) and the Spokes Paseo plugin (`paseo-plugin/`, which the hub's bootstrap
  registers with its daemon as a directory plugin; `paseo plugin reload machine0`
  there after a bump). See "Paseo spokes on
  machine0". Tests: the Python suite as above, and `npm run typecheck` in
  `paseo-plugin/`.
- **tmux-agents** (`shell.pins`, a `tmux` pin, and a pi package,
  [repo](https://github.com/justmytwospence/tmux-agents)) -- agent state on tmux
  window tabs (waiting red > done yellow > running green, with a count), a badge
  for detached Claude background agents, and desktop notifications for agents
  outside herdr: terminal-notifier on the Mac, and from SSH hosts a reverse tunnel
  (`RemoteForward 7877` in `~/.ssh/config`) to the launchd agent
  `osx/Library/LaunchAgents/com.spencerboucher.claude-notify.plist`, which runs its
  `bin/notify-recv`. A TPM `@plugin` in `.tmux.conf`; Claude Code (`bin/claude-hook`) and
  Codex (`bin/agent-state`) call it from their hooks in `shell/.claude/settings.json`
  and `shell/.codex/hooks.json`, pi loads it as a package, and opencode through the
  `shell/.config/opencode/plugins/tmux-agents.js` link. Inert inside herdr.
- **Claude Code mods** (`shell.pins`, `git` pins) -- plugins with a hooks module
  ([mods](https://code.claude.com/docs/en/plugins/mods/overview), Claude Code
  2.1.287+). `shell/.zshenv` lists the checkouts in `CLAUDE_CODE_PLUGIN_DIRS`, so
  they load in every Claude Code session started from a shell (not the Desktop app).
  - **claude-auto-effort**
    ([repo](https://github.com/justmytwospence/claude-auto-effort)) -- the port of
    pi-auto-effort: Jev sets the effort per prompt, capped at the session's own
    (`effortLevel`, `/effort`). `/auto-effort`. Tests: `claude plugin test` in its
    checkout.
  - **token-weather** -- Anthropic's sample mod from
    [claude-code-playground](https://github.com/anthropics/claude-code-playground/tree/main/claude-code/mods/token-weather):
    a context-window forecast above the prompt. Third-party, so bump its commit in
    `shell.pins` by hand.
  - Built-ins: `cc-plugin-you-should-know` (a side agent that flags things worth
    knowing above the prompt) is enabled in `shell/.claude/settings.json`;
    `cc-plugin-agents-md` (on by default) loads a project's `AGENTS.md` when it has
    no `CLAUDE.md`, so projects need no `CLAUDE.md` link or `@AGENTS.md` stub.
- **opencode plugins** (git pins in `opencode.jsonc`), ports of the Jev pi plugins; each calls
  Jev over its HTTP API with `TYPESAFE_API_KEY` and takes options as the second element of its
  `plugin` entry. Tests: `npm run check` in the checkout.
  - **opencode-auto-effort** -- sets the variant per prompt for the `build` agent, capped at
    the variant the prompt would have used; planners and scouts keep theirs.
  - **opencode-lean-context** -- Jev trims large tool output in `tool.execute.after`, reading
    back opencode's own truncation file so the cut middle is not lost. No `/compact-jev`.
  - **opencode-tool-gate** -- read-only calls run, a short dangerous list and confident Jev
    holds are blocked before opencode's permission check with a push-back; the agent may then
    ask you with the `question` tool (`Allow`/`Deny`), which lets that exact call through once.
    The config's `ask` rules still apply after it. Project rules in
    `.opencode/tool-gate-rules.md`.
## Phone access

Three iOS apps, for different jobs. Each is set up on the Mac, the NUC and the
exe.dev VM by one idempotent script, which `bootstrap-osx` and `bootstrap-exe` call
and the NUC runs by hand:

| | Heeler | Moshi | Paseo |
|---|---|---|---|
| For | the agents running in herdr, on every host at once | a terminal on any host, herdr or not | starting and steering agents in a chat UI |
| Shows | an agent console sorted by who needs you, each agent's live terminal, and a composer | a real terminal (plus an experimental Chat View) | a chat, with tool cards and approvals |
| Reaches a host by | SSH (WireGuard for the Mac and NUC) | SSH or mosh (WireGuard for the Mac and NUC) | Paseo's end-to-end encrypted relay, from anywhere |
| Pushes | Blocked and Done, end-to-end encrypted | approvals and "done" on the lock screen | agent finished or needs input |
| Host side | `heeler-setup` (a herdr plugin) | `moshi-setup` | `paseo-setup` |

Heeler and Moshi overlap on herdr's agents; Heeler is the one built for them.
Agents started in Paseo live in Paseo's daemon, not in herdr, so only Paseo sees
them, and it cannot see herdr's (its Import session can continue a Claude, Codex
or OpenCode conversation as a new Paseo agent; quit it in herdr first). Claude
Code's built-in Remote Control (on for every session) also puts any `claude`
running in herdr into the Claude iOS app.

Check a host with `herdr plugin list`, `moshi-hook doctor` and `paseo daemon
status`; re-running any of the scripts is always safe.

### Heeler

[Heeler](https://github.com/ZingerLittleBee/Heeler) is a native iOS app for herdr,
open source (AGPL) and early (one developer, App Store 0.1.x). `heeler-setup`
installs its herdr plugin from GitHub (the plugin registry is per user, so one
install covers every session) and updates it on each run. The plugin shows the
Pairing Code and sends the pushes, through the developer's relay, which only ever
sees ciphertext.

Once per host, with the phone: in the herdr window attached to that host, run
`herdr plugin action invoke heeler.pair` (on the NUC, `herdr --session homelab
plugin action invoke heeler.pair`), check the addresses the phone can reach, and
scan the QR from the popup. Scanning adds the host and puts the app's Device Key
in `~/.ssh/authorized_keys`. The NUC's herdr runs as the `homelab` session, which
the Pairing Code does not carry: set the host's herdr Session to `homelab` in the
app.

The exe.dev VM cannot pair by QR: its sshd uses its own host key rather than one
in `/etc/ssh` (which the code pins) and an `authorized_keys` that exe.dev manages.
Add it in the app by hand (address `<vm>.exe.xyz`, port 22, user `exedev`,
Device Key) and authorize the Device Key, the same one the Mac's
`~/.ssh/authorized_keys` gained when it paired, with
`ssh exe.dev ssh-key add '<key line>'`. The plugin is installed there anyway, for
the pushes.

### Moshi

[Moshi](https://getmoshi.app) is an iOS terminal: pick a running herdr session from
its session picker, and get agent approvals and "done" pushes on the lock screen.

`moshi-setup` owns everything on the host:

- **moshi-hook**, the daemon behind approvals, pushes, Chat View and the diff
  viewer: the `rjyo/moshi` tap on the Mac (in the Brewfile), upstream's
  `install.sh` into `~/.local/bin` on Linux. Every run updates it (`brew upgrade`
  on the Mac, `moshi-hook update` on Linux) and restarts the daemon when the
  version changes, so the three hosts stay on one version. Runs as a brew
  service or a systemd user service.
- **mosh and tmux** everywhere except mosh on exe.dev, which drops inbound UDP.
- **Agent hooks.** `moshi-hook install` writes the absolute path of whichever
  binary ran it and calls any other spelling stale, but `~/.claude/settings.json`
  and `~/.codex/hooks.json` are links into this repo. So the tracked copies call
  `/usr/local/bin/moshi-hook`, which `moshi-setup` symlinks to the real binary on
  each host (with sudo); moshi-hook resolves symlinks, so every host reads as
  current. Never run `moshi-hook install` for claude or codex on a host. Every
  other agent keeps its hook config in an untracked host file, so `moshi-setup`
  lets moshi-hook write those itself.
- **Codex** gets `daemon_auto_start` turned off. Codex 0.157's shared background
  server keeps the environment of the first terminal that started it, so every
  session would be attributed to that one pane.

moshi-hook also calls its claude and codex hooks stale when another tool appends
its own hooks after them in the same list (Orca does). When `moshi-hook doctor`
says they are out of date, run `moshi-setup --refresh-tracked-hooks` on the Mac:
it runs the installer in a scratch HOME and splices only moshi's entries, pointed
at `/usr/local/bin/moshi-hook`, back in last, in the file's existing key order.
Review and commit only what is moshi's.

Once per host, with the phone: in Moshi, **Easy Pair** and scan the QR from
`moshi-hook host setup --host <address> --name <label>`. That both saves the SSH
connection and pairs the hooks. Use the WireGuard addresses, which the phone
reaches through the homelab tunnel from anywhere: `172.16.255.1` for the NUC and
`10.13.13.3` for the Mac (not the `.local` name it offers by default, which only
resolves on the home LAN). An exe.dev VM cannot finish Easy Pair on its own:
exe.dev checks SSH keys against the account, not the VM's `authorized_keys`. Run
`moshi-hook host setup --host <vm>.exe.xyz --user exedev --force` there, scan it,
then register the key it wrote to `~/.ssh/authorized_keys` from the Mac with
`ssh exe.dev ssh-key add '<public key>'`, and set the connection to SSH, not mosh.

### Paseo

[Paseo](https://paseo.sh) runs Claude Code, Codex, OpenCode and pi behind a daemon
and drives them from its iOS, desktop, web and CLI clients in a chat UI.

`paseo-setup` gives every host the same shape:

- **An always-on daemon**: a launchd agent on the Mac (the desktop app, from the
  Brewfile, attaches to it instead of starting its own), a systemd user service on
  Linux, installed from npm. It is launched through `zsh -c`, which reads
  `.zshenv`: that is how the agents it spawns get PATH and the `PI_*` settings pi
  needs, with no second copy in Paseo's config. Restarts happen only when the
  version, the service or a restart-only setting changes, since a restart
  interrupts running agents.
- **Localhost only, no password.** The phone comes in through Paseo's relay,
  which is end-to-end encrypted. The desktop app reaches the other hosts over
  SSH (Settings, Add host, Remote SSH, `ssh://nuc`), which expects exactly a
  daemon on the remote's `127.0.0.1:6767`.
- **Models.** The script owns `agents.providers` in `~/.paseo/config.json`, which
  adds `claude-sonnet-5-5` (missing from Paseo's built-in Claude list as of
  0.10.1).
- **Codex** is installed from npm on a Linux host that lacks it.

Once per host, with the phone: `paseo daemon pair --relay` prints a QR; scan it
from the app's Add host. The QR is a standing grant to drive that host's agents.
An agent CLI has to be signed in on the host before Paseo can use it: pi and
opencode on the exe.dev VM are not yet.

## Coding agents

Four harnesses run side by side, each in its own herdr pane: **Claude Code**
(Anthropic), **Codex** (OpenAI), and the two multi-model harnesses **pi** and
**opencode**. The point of the shared configuration below is that a skill, an
instruction, or an MCP server is written once and works in all of them.

- **Skills**: every skill lives in `~/.agents/skills`, the cross-vendor
  convention that Codex, pi, opencode, Cursor and Zed all read with no
  configuration. Claude Code is the one exception -- it reads only
  `~/.claude/skills` and has no setting for extra roots -- so that path is a
  symlink to the canonical directory: one link for the whole set, nothing to
  keep in sync. `shell/.local/bin/skills-install` owns that directory -- it
  installs the third-party skills from the source list it carries and links the
  personal ones, authored here under `shell/.agents/skills/<name>/`. Bootstrap
  runs it on a new machine, and re-running it is also how skills are updated.
  It is the one place the skill set is declared; the CLI's lock file is
  disposable machine state.
- **Instructions**: `shell/.agents/AGENTS.md` is the single source, named for the
  cross-vendor convention and sitting beside the skills. Codex reads it through
  `shell/.codex/AGENTS.md`, Claude Code through `shell/.claude/CLAUDE.md`, pi
  through `shell/.pi/agent/AGENTS.md` and opencode through
  `shell/.config/opencode/AGENTS.md`, all symlinks to it inside the repo. Each
  tool loads only its own global path: Claude Code reads a project-level
  `AGENTS.md` (the built-in agents-md mod) but never a global one, and pi ignores `~/.claude/CLAUDE.md`.
  (opencode would fall back to `~/.claude/CLAUDE.md`, but its own path takes
  precedence, and exeuntu links it to Shelley's AGENTS.md.) Edit one file.
- **MCP**: the one thing that genuinely has to be written twice, because no two
  of these read the same file. `shell/.config/mcp/mcp.json` is the tool-agnostic
  file and declares the set; pi's built-in MCP support reads it through the
  `shell/.pi/agent/mcp.json` symlink (sign in with `/mcp` or `pi mcp login
  <name>`, check with `pi mcp list`), and opencode has the same servers in its
  own `mcp` block in `shell/.config/opencode/opencode.jsonc`. Claude Code
  (`~/.claude.json`) and Codex (`~/.codex/config.toml`) keep servers in
  machine-local files, so `shell/.local/bin/mcp-install` registers mcp.json's
  servers in both; bootstrap runs it, and re-running it after editing mcp.json
  is the sync. It never signs in: `/mcp` in Claude Code, `codex mcp login
  <name>`. Context7 is skipped for Claude Code, which gets it from the context7
  plugin.
- **herdr**: `herdr integration install <claude|codex|pi|opencode>` on each host
  lets herdr report each agent's state. Check with `herdr integration status`.
- **Claude subscription billing**: pi and opencode reach Claude through the
  Pro/Max subscription (pi-anthropic-auth, @ex-machina/opencode-anthropic-auth),
  but any request not shaped as Claude Code is billed per token to extra usage.
  Every subscription response says which pool paid
  (`anthropic-ratelimit-unified-representative-claim`: `five_hour`/`seven_day`
  or `overage`), so the anthropic-billing-guard plugin (see "Plugins", loaded by pi
  and by opencode) warns the moment one
  lands on `overage` and append it to `~/.local/state/anthropic-extra-usage.log`.
  pi's static `warnings.anthropicExtraUsage` notice stays on, and Claude Code's
  workflow cost warning stays on (clicking "Allow once" on it writes
  `skipWorkflowUsageWarning: true` back into `settings.json`; delete it again).
  Plan mode's planners run inside pi and use the providers pi-anthropic-auth
  registered, so they bill the subscription too.
- **Worktrees**: `shell/.local/bin/worktree` is the one way checkouts get made.
  They live in `<project>/.worktrees/<branch>` (ignored by `/.worktrees/` in
  `shell/.config/git/ignore`; the dot keeps pytest, pyright and tsc out of them)
  and open as a grouped herdr child space, or a tmux window outside herdr, with pi
  started in it; elsewhere the path is printed. Everything routes through it: pi's
  `/worktree` (`shell/.pi/agent/extensions/worktree.ts`, which replaced
  `@zenobius/pi-worktrees`), opencode's `/worktree`
  (`shell/.config/opencode/commands/worktree.md`), Claude Code's
  WorktreeCreate/WorktreeRemove hooks (so `claude -w`, `EnterWorktree` and
  `isolation: "worktree"` land there too), herdr's `prefix+G` popup, and the
  "Worktrees" rule in `AGENTS.md`. Claude Code never cleans up subagent
  worktrees a hook created, so a SubagentStop hook (`worktree hook
  claude-subagent-stop`) removes each finished one that holds no work;
  `worktree clean` sweeps any leftovers. Codex's own managed worktrees can only
  use one global pool, so they are switched off (`codex features disable
  worktrees`, run by the bootstrap scripts, since `~/.codex/config.toml` is
  machine-local). pi-subagents' `worktree: true` goes through `worktree new
  --no-open` as well. One exception remains: herdr's sidebar "New worktree" menu
  item still uses the global `[worktrees] directory` (herdr has no per-repo
  setting). Nothing blocks an agent from running `git worktree
  add` itself; the `AGENTS.md` rule is the only guard there.
- **opencode comes from npm, not Homebrew** (`npm install -g
  --allow-scripts=opencode-ai opencode-ai`). The 1.18.30 bottle crashes on every
  run in `SystemPrompt.environment`; the npm build works. `--allow-scripts` is
  required or the postinstall never fetches the real binary. macOS currently
  resolves to 1.18.29 because the darwin-arm64 package for 1.18.31 is missing;
  Linux gets 1.18.31.
- **Credentials are never tracked.** Each harness stores its own
  (`~/.claude/.credentials.json`, `~/.codex/auth.json`,
  `~/.local/share/opencode/auth.json`, `~/.pi/agent/auth.json`) and this repo is
  public. Sign in per machine: `claude` then `/login`, `codex`,
  `opencode auth login`.
- **Which subscription works where.**
  - *OpenAI*: pi and opencode both sign in with the ChatGPT subscription, which
    OpenAI permits in third-party harnesses; an OpenAI Platform API key is the
    pay-per-token alternative. Nothing here touches Anthropic's usage pools.
  - *Anthropic*: Claude Code uses the Max plan directly. pi and opencode reach it
    through community auth plugins (`@gotgenes/pi-anthropic-auth`,
    `@ex-machina/opencode-anthropic-auth`), which present the session as
    first-party so it draws plan limits. Note that Anthropic's terms reserve
    OAuth for "ordinary use of Claude Code and other native Anthropic
    applications", and that unmasked third-party OAuth traffic bills to Extra
    Usage at API rates instead — which is what you see if a plugin stops working
    after an upstream change.

### Planning

Plan in a strong model, implement in a cheaper one, and optionally let two models
plan the same task in parallel.

- **pi** loads pi-plan-mode
  ([repo](https://github.com/justmytwospence/pi-plan-mode)), originally a fork of
  `@narumitw/pi-plan-mode`, as a pinned git package in
  `shell/.pi/agent/settings.json`. `/plan [task]` (or `shift+tab`) opens one
  full-screen planner with a step bar: Settings, Tools, Planning, Review, Implement.
  - **Settings**: planner A, optionally planner B (two at most; Fable 5.1 and
    GPT-6 Astra by default), each with its effort and subagent model
    (`scoutModelMap`), the time limit, and preferences. ←/→ or ctrl+h/ctrl+l
    change a value; changes are saved to `shell/.pi/agent/pi-plan-mode.json`.
  - **Tools**: a tree of Shell (with `commandGrants`: `marimo` and `jev`, which
    runs `shell/.local/bin/jev-ask`), Subagents, `plannerToolsets` (web research),
    every MCP server and its tools, and Other tools from the other pi
    extensions. Jev (TypeSafe, through Pi's own classifier models and
    `TYPESAFE_API_KEY` from `~/.zshrc.local`) scores every tool for the task and
    preselects the useful ones.
  - **Planning/Review**: each planner is an in-process Pi session seeded with
    the conversation, shown in its own lane with a line to talk to it (both at
    once), its questions inline, and its plan once submitted. Actions: implement
    a plan, merge one plan into the other, add a second planner, export, save,
    discard. Esc hides the screen while planners keep working; `/plan` reopens it.
  - **Implement**: model, effort, and context (this conversation or a fresh
    session with only the plan), defaulting from `implementationModelMap`.
  - `planCompleteCommand`, pointed at `~/.claude/hooks/save-plan-to-obsidian.sh`
    (the hook Claude's ExitPlanMode uses), runs when a plan is implemented or
    exported.
  - pi loads it as a pinned git package; the dotfiles-sync skill runs
    `plugins sync` on each host. Development happens in `~/Projects/pi-plan-mode`
    (see "Plugins").
- **opencode** gets as close as config allows, in `shell/.config/opencode/`:
  - `agent.plan` (Opus, xhigh) and `agent.build` (Sonnet, high): Tab switches mode
    and model together, and `<leader>m` / `ctrl+t` override model and effort
    before sending. The plan block also restores read-only permissions that the
    global allow rules had been overriding.
  - `/multiplan <task>` runs the `planner-claude` (Fable 5.1) and `planner-gpt`
    (GPT-6 Astra) subagents in parallel, shows both plans, and asks whether to use
    one or synthesize. Each planner may delegate to its own read-only scout,
    `scout-opus` or `scout-sol`, which needs `subagent_depth: 2`. All of them
    have `webfetch`, your MCP servers, and `websearch` because `.zshenv` exports
    `OPENCODE_ENABLE_EXA=1` (opencode only offers that tool with the flag).
    Agent permissions are static, so narrowing tools for one run means saying so
    in the `/multiplan` task text.
  - `/implement-fresh` hands only the final plan to the `implementer` subagent, a
    fresh context; Tab to build keeps the conversation instead.
  - Not reachable without a plugin: a default implementation model that depends on
    which model planned, and a plan-complete hook.

## exe.dev

[exe.dev](https://exe.dev) sells Linux VMs that are managed entirely over SSH. One
is kept as a third machine beside the Mac and the NUC -- a disposable sandbox where
an agent can work without touching either real machine. The plan's vCPU and RAM are
one shared pool across all your VMs, not a size per VM, so the usual shape is a
single VM using the whole pool.

Two SSH destinations, and they behave differently: `ssh exe.dev <command>` is the
lobby (VM lifecycle, integrations, billing; no scp or shell), while
`ssh <vm>.exe.xyz` is the VM itself. `~/.ssh/config` pins the key for both and gives
the VMs the same reverse-forward pair as the nuc, so Claude Code running there
outside herdr can still reach this Mac's notifier.

Provisioning a replacement is five commands:

```sh
ssh exe.dev new --name <vm>                       # 5-52 chars; names are global
ssh exe.dev integrations add github --name <repo> \
    --repository justmytwospence/<repo> --attach vm:<vm> --act-as-user
ssh <vm>.exe.xyz 'git clone https://github.int.exe.xyz/justmytwospence/dotfiles.git ~/dotfiles \
    && ~/dotfiles/exe/bin/bootstrap-exe'
herdr machine add <vm>.exe.xyz --label <vm>       # from the Mac, interactive, once
ssh nuc 'docker exec wireguard cat /config/peer_exe/peer_exe.conf' \
  | ssh <vm>.exe.xyz '~/dotfiles/exe/bin/homelab-vpn install'   # Snowflake tunnel
```

- **GitHub without a key**: the VM has no GitHub SSH key. The exe.dev GitHub
  integration proxies `github.int.exe.xyz` instead, serving public repos outright
  and private ones that have an integration attached, with no token on the VM. The
  catch is `shell/.gitconfig`, which rewrites `https://github.com/` to
  `ssh://git@github.com/` and cannot work there; `bootstrap-exe` writes a
  `~/.gitconfig.local` that cancels that rewrite and routes your own repos through
  the proxy, so all three machines keep the identical `git@github.com:` remote. `gh`
  needs `GH_HOST=github.int.exe.xyz`, which the same script writes to
  `~/.zshenv.local`.
- **The image already has agents**: `exeuntu` ships `claude`, `codex`, and `pi` in
  `/usr/local/bin`, frozen at image build time. `bootstrap-exe` installs the native
  Claude Code build into `~/.local/bin` (where it can update itself, as on the other
  two machines) and refreshes Codex with `sudo exeuntu update codex`.
- **pi on the VM**: `/usr/local/bin/pi` links to `~/.local/pi`, the image's build,
  which `pi update` refuses to replace ("cannot self-update this installation")
  even though pi's banner says to run it. Update with `exeuntu update pi` (no sudo);
  `bootstrap-exe` does. Signing in is per machine as everywhere else, and a fresh
  VM's `auth.json` is empty. pi's first start also asks "Use exe.dev LLM
  integrations?": the answer is saved in `~/.pi/agent/exe-dev-llm-integration.json`.
  "I'll configure pi myself" keeps the subscriptions in `enabledModels`, but until
  `/login` has run pi starts with **no models at all**. Saying yes instead routes
  through exe.dev's metered `llm` integration. Anthropic's `/login` has a "Copy
  code login" method (pi 1.0+) for a browser on another machine. Delete the
  preference file to be asked again.
- **Snowflake leaves from home**: a Snowflake network policy allowlists only the
  home WAN IP, so the VM is peer `exe` (10.13.13.4) on the NUC's WireGuard server,
  like the Mac. The tunnel is split: `172.16.0.0/12` plus a `/32` per Snowflake
  account IP, nothing else, so everything else keeps the VM's own uplink.
  `exe/bin/homelab-vpn` resolves the account hosts from `~/.snowflake/config.toml`
  at tunnel start and on a 15-minute timer, where the Mac's WireGuard app profile
  lists the IPs by hand. The peer config holds a private key, so it stays on the NUC
  and is piped across by the last provisioning command above; that same command
  re-keys nothing and is safe to re-run. `homelab-vpn status` shows which uplink
  each Snowflake host takes.
- **Out of memory**: the image has no swap, and exe.dev's `sshd` gives every
  session `oom_score_adj -1000`, so herdr, its panes and every job under them
  are exempt from the kernel OOM killer. A job that fills memory livelocks the
  whole VM (SSH authenticates, then nothing answers; herdr shows
  "reconnecting") until `ssh exe.dev restart <vm>`. `shell/.zshenv` resets the
  score to 0 for each shell, and `exe/bin/exe-memory-guard` (run by
  `bootstrap-exe`) adds a 4 GB swap file and earlyoom, which kills the largest
  process first and spares sshd, init and the herdr server. `ssh exe.dev stat
  <vm> --json` shows memory and CPU over time from outside a hung VM.
- **What is not automated**: API keys (`TYPESAFE_API_KEY` for Jev, `MODEL_API_KEY`
  for Meta) are copied by hand from the Mac's `~/.zshrc.local` into the VM's
  `~/.zshrc.local`, never `~/.zshenv.local`, which `bootstrap-exe` regenerates.
  Without `TYPESAFE_API_KEY`, Plan mode's tool step shows "Jev Not used".
  `claude`, `codex` and `pi` need an interactive login, and
  `atuin login` is optional. The script prints these at the end.

## machine0 spokes with an exe.dev hub

[herdr-machine0](https://github.com/justmytwospence/herdr-machine0)
(the herdr-machine0 plugin, see "Plugins") runs agents on small per-project
[machine0](https://machine0.io) VMs, the **spokes**, and shows them all in one
herdr server, the **hub**: a dedicated exe.dev VM, `herdr-hub`, with 2 vCPU and 4 GB,
which the Mac adds like any other machine. A hub pane runs
`spoke attach <spoke> <slot>`, an ssh wrapper. The agent itself runs on the spoke
inside `dtach` and reports its state to the hub's herdr through a relay socket
forwarded over that ssh. herdr and Heeler
see spoke agents like local ones. The plugin README covers the design.

- **Spokes are clones** of the golden image `m0-spoke`, which `spoke image build`
  makes on a builder VM: the plugin's own `setup/spoke.sh` (harnesses, herdr CLI,
  dtach, the spoke pi extension), then this repo's part, wired up in the tracked
  `m0/.config/herdr-machine0/config.json`: `provision_command` runs
  `m0/bin/bootstrap-m0 --role spoke`, `sync_command` runs `m0/bin/sync-m0` on
  every spoke creation and `spoke sync`. Then it scrubs every credential. Spokes
  run the hub's copy of the plugin, pushed on every sync. `spoke new <name> --repo owner/repo` creates
  one (machine0 `large` in `us-west` by default; `--size gpu-…` gives a GPU spoke
  in `us-east`), syncs dotfiles, clones the repos and opens its herdr space on the
  hub. Usually simpler: **a new space on the hub asks which repo it is for**.
  Each repo gets one spoke named after it (the repo in `~/Projects/<repo>`),
  and each worktree is a tab in that repo's space (`spoke worktree <repo>
  <branch>`, or `worktree new` from an agent there). "scratch" makes a repo-less
  spoke; Esc keeps a plain hub shell. `prefix+N` on the hub (or the Mac, with herdr-hub selected) is a popup for a new
  agent or a new spoke. `worktree new` on a spoke opens the checkout as another
  hub pane on the same spoke.
- **Idle spokes suspend themselves** after 2 hours (every slot idle or done, no
  background work, load under 0.3; `spoke keep-awake <name>` exempts one) and
  then cost only image storage. A suspended spoke's pane says so: Enter wakes it,
  which takes a few minutes and gives it a new IP, and the agent comes back in
  the same session. `prefix+Z` suspends the focused spoke now.
- **Logins live only on the hub.** Claude (pi and Claude Code) uses one
  `claude setup-token` token, which the hub pushes to spokes. ChatGPT and Radius
  are brokered: the hub's broker holds the only refresh token and hands spokes
  short-lived access tokens on request, so no spoke ever needs `/login` and
  nothing falls back to API billing. Meta and TypeSafe keys are pushed with the
  token. `spoke secrets show` lists what is set.
- **Provisioning the hub**:

  ```sh
  ssh exe.dev new --name herdr-hub && ssh exe.dev resize herdr-hub --cpu=2 --memory=4
  ssh exe.dev integrations add github --name dotfiles \
      --repository justmytwospence/dotfiles --attach vm:herdr-hub --act-as-user
  ssh herdr-hub.exe.xyz 'git clone https://github.int.exe.xyz/justmytwospence/dotfiles.git ~/dotfiles \
      && ~/dotfiles/m0/bin/bootstrap-m0 --role hub'
  herdr machine add herdr-hub.exe.xyz --label herdr-hub      # from the Mac, once
  ```

  `bootstrap-m0 --role hub` runs the plugin's `spoke setup hub` for its own
  needs; `spoke doctor` then checks the whole hub. The script ends with the
  steps that need a person: the machine0 API token,
  ssh key and `m0` profile (its GitHub integration gives spokes `gh`), the Claude
  setup-token, `spoke secrets login` for the broker, the API keys, and the first
  `spoke image build --fresh`. Heeler and Moshi add the hub as they would any
  exe.dev VM.
- **Spoke state that matters is pushed**, not left on the VM: `spoke rm` refuses
  while any repo has uncommitted or unpushed work, and archives the agents'
  sessions to the hub first. Snowflake's home-IP tunnel (`homelab-vpn`) is not set
  up on spokes.
- **Moving the hub** to machine0 (if the exe pool's shared CPU turns out to be
  too contended) is `bootstrap-m0 --role hub --host machine0` on a machine0
  `large` VM; spokes do not care where the hub is.

## Paseo spokes on machine0

[paseo-machine0](https://github.com/justmytwospence/paseo-machine0)
(the paseo-machine0 plugin, see "Plugins") is the Paseo counterpart of the herdr setup above,
and fully separate from it: its own hub, image, profile, key, VMs and logins.
Every project gets a machine0 VM `paseo-<name>` running its own Paseo daemon,
reached by the Paseo apps through Paseo's encrypted relay. A dedicated exe.dev
VM, `paseo-hub` (2 vCPU, 4 GB, in the Personal pool), creates, wakes,
suspends and removes spokes, holds every login and pushes credentials to the
spokes, and adds a **Spokes** screen to the Paseo app. The hub is never between
you and an agent: if it is down, spokes and the apps keep working. The plugin
README covers the design; `docs/spike.md` there tracks what still needs a real
VM to confirm.

- **Spokes are clones** of the golden image `paseo-machine0-spoke`, built by
  `paseo-machine0 image build` from
  `paseo-machine0/bin/bootstrap-paseo-machine0 --role spoke` (no herdr, Moshi or
  Heeler; Paseo through `paseo-setup`). New spoke on the Spokes screen (or
  `paseo-machine0 new <name> --repo owner/repo`) names the host, pushes
  credentials, updates Paseo, clones the repos as Paseo projects and stores the
  spoke's pairing link.
- **Adding a spoke to the apps**: on the phone, Connect on its Spokes row opens
  the pairing link in the app (confirm once). On the desktop, Copy link, then
  Settings, Add host, Paste pairing link (or show the QR). Once per spoke per
  device; it survives suspend and resume.
- **Idle spokes suspend** after 2 hours with no agent running, no schedule, load
  under 0.3 and no permission request younger than a day; Wake on the Spokes
  screen brings one back (a few minutes) and updates Paseo while nothing runs.
  Keep awake exempts one.
- **Logins live only on the hub**, in `~/.config/paseo-machine0/secrets.env`
  (Claude setup-token, Meta and TypeSafe keys, the machine0 token) and the
  broker store (openai-codex and Radius, the only refresher). hubd pushes them
  to spokes; pi reads the brokered ones through pi-brokered-auth.
  `paseo-machine0 secrets show` lists what is set.
- **Orchestrators** run on the hub's own Paseo daemon; the `paseo-machine0`
  skill tells them how to start and follow work on a spoke with
  `paseo --host ssh://paseo-<name> ...`.
- **Provisioning the hub**:

  ```sh
  ssh exe.dev new --name=paseo-hub --cpu=2 --memory=4GB
  ssh exe.dev integrations attach dotfiles vm:paseo-hub   # takes a minute to apply
  ssh paseo-hub.exe.xyz 'git clone https://github.int.exe.xyz/justmytwospence/dotfiles.git ~/dotfiles \
      && ~/dotfiles/paseo-machine0/bin/bootstrap-paseo-machine0 --role hub'
  ```

  `bootstrap-m0 --role hub` runs the plugin's `spoke setup hub` for its own
  needs; `spoke doctor` then checks the whole hub. The script ends with the
  steps that need a person: the machine0 token, key
  and `paseo-machine0` profile (GitHub integration only; its env sets
  `MACHINE0_API_KEY` and `MACHINE0_MCP_URL` to dummies so spokes never receive a
  key that can manage the fleet), the Claude setup-token,
  `paseo-machine0 secrets login`, the API keys, pairing the hub in the apps, and
  the first `paseo-machine0 image build --fresh`.
- **Moving the hub** to machine0 (if the exe pool is too contended) is
  `bootstrap-paseo-machine0 --role hub --host machine0` on a machine0 `large`.

## Manual Post-Bootstrap Steps

- **Karabiner Elements**: Open the app and grant accessibility permissions
- **Raycast**: Import script commands from `~/raycast/script-commands/`
- **GPG keys**: Import from backup if needed, then configure `gpg-agent.conf` to use `pinentry-mac`
- **Node.js**: Run `nvm install --lts` for the latest LTS version
- **Ruby**: Run `rbenv install <version>` and `rbenv global <version>`

## Mac roles

The two Macs share one `osx` package. Only the Brewfile differs, through a
role: `pro` (the MacBook Pro, the desk machine) and `air` (the MacBook Air,
for travel). The role is `export DOTFILES_ROLE=pro|air` in `~/.zshenv.local`;
`bootstrap-osx pro|air` writes it. Unset counts as `air`, the smaller and safer
set: a Mac that forgot its role installs less, rather than having `brew bundle
cleanup` treat the full set as wanted.

`osx/.Brewfile` puts the heavy desk-only entries (Docker, XQuartz, gdal,
Postgres, Java/PlantUML, Podman, C++ and Kubernetes tooling, dbt, a few cargo
tools) in an `if pro ... end` block at the end. brew drops every environment
variable except `HOMEBREW_*` before it evaluates a Brewfile, so `shell/.zshenv`
mirrors `DOTFILES_ROLE` as `HOMEBREW_DOTFILES_ROLE`, which the Brewfile reads.

After a Brewfile change, on each Mac:

```sh
brew bundle install --global          # add what this role is missing
brew bundle cleanup --global          # preview what this role does not list
brew bundle cleanup --global --force  # remove it
```

## Local Overrides

Machine-specific config can be added to these files (not tracked by git):

- `~/.zshenv.local` -- environment variables, including the Mac role (`DOTFILES_ROLE`)
- `~/.zshrc.local` -- shell config
- `~/.gitconfig.local` -- git config (e.g., work email)
