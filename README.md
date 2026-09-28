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
~/dotfiles/osx/bin/bootstrap-osx
```

This will:
- Install Homebrew
- Stow the `shell` and `osx` packages to `~`
- Install all Homebrew packages and casks from `.Brewfile`
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
| `osx` | Brewfile, Ghostty, Karabiner, herdr, macOS bootstrap | macOS |
| `nuc` | Host-specific config for the NUC | NUC |
| `exe` | Host-specific config and bootstrap for exe.dev VMs | exe.dev |
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

The NUC stows `shell` and `nuc`; an exe.dev VM stows `shell` and `exe`. Restow with `dotfiles-restow` rather than `stow -R`
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
  Ghostty's light/dark, cwd-following splits, `[ui.toast] delivery = "system"` for
  desktop alerts, and the full tmux keybinding mirror. `nuc/.config/herdr/config.toml`
  is the NUC's headless remote workspace: panes default into `~/homelab` and toasts
  render in the attached UI (`delivery = "herdr"`), since the NUC has no desktop
  notifier. `exe/.config/herdr/config.toml` is the same headless shape for an
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
- **Notifications**: `notify.sh` defers to herdr when `HERDR_ENV=1` (and labels the
  pane with the agent's name); outside herdr the tmux `@cc_state` tab system and the
  terminal-notifier / SSH path are unchanged. On the Mac, herdr's toasts are in-app
  only and the herdr-focus-notify plugin sends the desktop alerts.

### Plugins

herdr plugins live in their own public repos, pinned here as git submodules under
`plugins/` and activated with `herdr plugin link`. (`plugins/pi-plan-mode` is a
pi package, not a herdr plugin; see "Planning".) `plugins/` is not a stow package,
so `dotfiles-restow` never touches it, and `git pull` does not check submodules out:

```sh
git submodule update --init --recursive
herdr plugin link ~/dotfiles/plugins/<plugin>    # once per host; survives restarts
herdr plugin action invoke <id>.reapply          # linking skips the startup hook
```

Third-party plugins can instead be installed straight from GitHub with
`herdr plugin install <owner>/<repo> --yes`. The marketplace is public repos tagged
`herdr-plugin`.

- **herdr-attention-queue** (`plugins/herdr-attention-queue`,
  [repo](https://github.com/justmytwospence/herdr-attention-queue)) -- orders the
  Agents panel blocked > done > working > idle, and keeps a finished agent `done`
  until it works again or is marked reviewed, instead of clearing it on view.
  Linked on the Mac and the NUC; each herdr server orders its own agents, so on
  herdr 0.9.0 the list is grouped Local then NUC.
  - Keys: `prefix+a` mark reviewed, `prefix+shift+a` mark all reviewed,
    `prefix+m` mark done again.
  - The Mac config needs `agent_panel_sort = "spaces"`: with the NUC connected as a
    machine, `priority` re-sorts the combined list and discards plugin views. If the
    Agents header toggle was ever clicked, herdr's saved choice in
    `~/.local/state/herdr/client-shell/*.json` overrides config; delete its
    `agent_panel_sort` key with the client detached.
  - Run `herdr plugin action invoke attention-queue.clear` before unlinking.
- **herdr-focus-notify** (`plugins/herdr-focus-notify`,
  [fork](https://github.com/justmytwospence/herdr-focus-notify) of
  [yankewei/herdr-focus-notify](https://github.com/yankewei/herdr-focus-notify),
  pinned to its `feat/workspace-label-in-title` branch, which names the workspace in
  the title, e.g. "overmatch · claude finished") -- clickable macOS notifications
  (via `alerter`) when an agent turns blocked or done; clicking focuses that agent's
  workspace, tab, and pane, which herdr's own `system` toasts cannot do. Needs herdr
  0.9.1 for both the server and the attached client: 0.9.0 never emits
  `pane.focused`, so no terminal is learned and clicks are no-ops. Mac only, so the Mac config sets
  `[ui.toast] delivery = "herdr"` to avoid duplicate alerts.
  - Linking runs its `cargo build`; afterwards run
    `herdr plugin action invoke herdr-focus-notify.test`.
  - Focus a pane once per workspace so it learns which terminal to activate.

## Moshi

[Moshi](https://getmoshi.app) is the iOS terminal for reaching herdr from the
phone: SSH or mosh into a host, pick a running herdr session from its session
picker, and get agent approvals and "done" pushes on the lock screen. herdr's own
docs recommend it for iPhone. The unofficial herdr-specific clients (herdr-ios,
HerdrChat, Drover, herdr-gui) are young single-author projects; revisit if one
matures.

The app is installed from the App Store. Everything on the host side is
`shell/.local/bin/moshi-setup`, which `bootstrap-osx` and `bootstrap-exe` call and
the NUC runs by hand. It is idempotent:

- **moshi-hook**, the daemon behind approvals, pushes, Chat View and the diff
  viewer, from the `rjyo/moshi` tap on the Mac (in the Brewfile) and from
  upstream's `install.sh` into `~/.local/bin` on Linux. Both also install `moshi`,
  a `tmux new-session -A` launcher. Runs as a brew service or a systemd user
  service.
- **mosh and tmux** everywhere except mosh on exe.dev, which drops inbound UDP.
- **Agent hooks.** `moshi-hook install` writes the absolute path of whichever
  binary ran it and calls any other spelling stale, but `~/.claude/settings.json`
  and `~/.codex/hooks.json` are links into this repo. So the tracked copies call
  `/usr/local/bin/moshi-hook`, which `moshi-setup` symlinks to the real binary on
  each host (with sudo); moshi-hook resolves symlinks, so every host
  reads as current. Never run `moshi-hook install` for claude or codex on a host.
  Every other agent (pi, opencode, and gemini, cursor, kimi where installed) keeps
  its hook config in an untracked host file, so `moshi-setup` lets moshi-hook
  write those itself.
- **Codex** gets `daemon_auto_start` turned off. Codex 0.157's shared background
  server keeps the environment of the first terminal that started it, so every
  session would be attributed to that one pane.

When a moshi-hook upgrade changes the hook set, `moshi-hook doctor` reports claude
or codex hooks as out of date. Refresh the tracked copies on the Mac with
`moshi-setup --refresh-tracked-hooks`, then review and commit the result. It runs
the installer in a scratch HOME and splices only moshi's entries, pointed at
`/usr/local/bin/moshi-hook`, into the repo's files in their existing key order;
the installer itself would re-sort every key in `settings.json`.

The per-host steps need the phone and are not scripted:

1. **Pair the hooks**: in Moshi, Settings -> Hooks -> copy token, then
   `moshi-hook pair --token <token>` and restart the service. The pairing secret
   stays on the host (the Keychain on the Mac, a file store on Linux), never in
   this repo.
2. **Add the host to the app.** On the Mac and the NUC, `moshi-hook host setup
   --host <address> --name <label>` prints an Easy Pair QR. Use the WireGuard
   addresses, which the phone reaches through the homelab tunnel from anywhere:
   `172.16.255.1` for the NUC and `10.13.13.3` for the Mac (its fixed peer address;
   the iPhone is `10.13.13.2`, and the server forwards between peers). Not the
   `.local` name the Mac offers by default, which only resolves on the home LAN.
   An exe.dev VM cannot finish Easy Pair on its own: exe.dev checks SSH keys
   against the account, not the VM's `authorized_keys`. Run `moshi-hook host setup
   --host <vm>.exe.xyz --user exedev --force` there, scan it, then register the key
   it wrote to `~/.ssh/authorized_keys` from the Mac with
   `ssh exe.dev ssh-key add '<public key>'`. Set the connection to SSH, not mosh.
3. Restart any agent that was already running, then check with `moshi-hook doctor`.

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
  `AGENTS.md` but never a global one, and pi ignores `~/.claude/CLAUDE.md`.
  (opencode would fall back to `~/.claude/CLAUDE.md`, but its own path takes
  precedence, and exeuntu links it to Shelley's AGENTS.md.) Edit one file.
- **MCP**: the one thing that genuinely has to be written three times, because
  no two of these read the same file. `shell/.config/mcp/mcp.json` is the
  tool-agnostic file that pi reads (via the `pi-mcp-adapter` package, pinned in
  `shell/.pi/agent/settings.json`); opencode has its own `mcp` block in
  `shell/.config/opencode/opencode.jsonc`; Claude Code keeps user-scope servers
  in the untracked `~/.claude.json`. Add a server to all three, or decide it
  only matters in one.
- **herdr**: `herdr integration install <claude|codex|pi|opencode>` on each host
  lets herdr report each agent's state. Check with `herdr integration status`.
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

- **pi** loads `plugins/pi-plan-mode`
  ([repo](https://github.com/justmytwospence/pi-plan-mode)), a fork of
  `@narumitw/pi-plan-mode` pinned as a submodule and referenced by path in
  `shell/.pi/agent/settings.json`. It keeps upstream's read-only `/plan` and adds:
  - `/plan multi <task>`: one read-only planner per chosen model (Fable 5.1 and
    GPT-6 Astra by default), each a `pi --mode json` subprocess under the same
    Plan-mode policy, then read the candidates and use one or synthesize several
    with guidance. `/plan compare` reopens them, and the ready menu offers
    "Compare with other models".
  - Planners fan out read-only subagents through a `plan_subagents` tool, on the
    model `scoutModelMap` gives them (Fable to Opus 5.5, Astra to Sol). Scouts
    can only read and search, and their cost counts toward the planner's.
  - What planners may use is chosen per run: the planner picker has `Tool ·` rows
    for Shell (read-only commands), Subagents, and each `plannerToolsets` entry --
    Web research (`pi-web-access`) and MCP servers (`pi-mcp-adapter`) -- all on by
    default. Scouts inherit the toolsets. The main `/plan` session gets the same
    tools through `defaultPlanTools`, or per run with `/plan tools`.
  - An Implement screen with model, effort, and context (keep the conversation, or
    a fresh session with only the plan). Defaults come from
    `implementationModelMap`, keyed by the model that wrote the plan.
  - `planCompleteCommand`, pointed at `~/.claude/hooks/save-plan-to-obsidian.sh`,
    the hook Claude's ExitPlanMode uses. It replaces the old `plan-to-obsidian.ts`.
  - Settings live in `shell/.pi/agent/pi-plan-mode.json`, a normal stow link now
    that the fork follows symlinks.
  - pi loads the checkout directly, so each host needs `git submodule update --init`
    and `npm ci --omit=dev` in `plugins/pi-plan-mode` (the dotfiles-sync skill does
    both).
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
- **What is not automated**: `claude` and `codex` need an interactive login, and
  `atuin login` is optional. The script prints these at the end.

## Manual Post-Bootstrap Steps

- **Karabiner Elements**: Open the app and grant accessibility permissions
- **Raycast**: Import script commands from `~/raycast/script-commands/`
- **GPG keys**: Import from backup if needed, then configure `gpg-agent.conf` to use `pinentry-mac`
- **Node.js**: Run `nvm install --lts` for the latest LTS version
- **Ruby**: Run `rbenv install <version>` and `rbenv global <version>`

## Local Overrides

Machine-specific config can be added to these files (not tracked by git):

- `~/.zshenv.local` -- environment variables
- `~/.zshrc.local` -- shell config
- `~/.gitconfig.local` -- git config (e.g., work email)
