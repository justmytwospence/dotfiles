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
- **Agent skill**: `shell/.claude/skills/herdr/SKILL.md` lets a Claude session drive
  the multiplexer it runs inside (split panes for tests/logs, `herdr agent wait` on
  siblings). It self-gates on `HERDR_ENV=1`, so it is inert outside herdr.
- **Notifications**: `notify.sh` defers to herdr's own toasts when `HERDR_ENV=1`
  (and labels the pane with the agent's name); outside herdr the tmux `@cc_state`
  tab system and the terminal-notifier / SSH path are unchanged.

### Plugins

herdr plugins live in their own public repos, pinned here as git submodules under
`plugins/` and activated with `herdr plugin link`. `plugins/` is not a stow package,
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

Provisioning a replacement is four commands:

```sh
ssh exe.dev new --name <vm>                       # 5-52 chars; names are global
ssh exe.dev integrations add github --name <repo> \
    --repository justmytwospence/<repo> --attach vm:<vm> --act-as-user
ssh <vm>.exe.xyz 'git clone https://github.int.exe.xyz/justmytwospence/dotfiles.git ~/dotfiles \
    && ~/dotfiles/exe/bin/bootstrap-exe'
herdr machine add <vm>.exe.xyz --label <vm>       # from the Mac, interactive, once
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
