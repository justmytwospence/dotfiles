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

The NUC stows `shell` and `nuc`. Restow with `dotfiles-restow` rather than `stow -R`
directly: stow aborts the whole package when any target is a file it does not own,
which silently stops new files from linking while already-linked ones keep updating.
`dotfiles-restow` retries with the conflicting paths excluded and reports them.

## herdr

[herdr](https://herdr.dev) is an "agent multiplexer" -- a tmux-like terminal that
runs and supervises AI coding agents (Claude Code, etc.), showing each pane as
blocked / working / done. It's installed via the Brewfile and integrated here:

- **Config**: host-specific, because the two machines need different herdr configs.
  `osx/.config/herdr/config.toml` is the Mac's: `terminal` theme so herdr follows
  Ghostty's light/dark, cwd-following splits, `[ui.toast] delivery = "system"` for
  desktop alerts, and the full tmux keybinding mirror. `nuc/.config/herdr/config.toml`
  is the NUC's headless remote workspace: panes default into `~/homelab` and toasts
  render in the attached UI (`delivery = "herdr"`), since the NUC has no desktop
  notifier. Both stow to `~/.config/herdr/`; only `config.toml` is tracked, so
  sockets, logs, and session state stay machine-local. Validate with
  `herdr config check`; hot-reload with `herdr server reload-config`.
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

There are no official herdr plugins yet. The "marketplace" is just public GitHub
repos tagged `herdr-plugin` (auto-indexed every 30 min); the only references are the
unmaintained examples in `ogulcancelik/herdr-plugin-examples`
(`agent-telegram-notify`, `github-link-preview`, `dev-layout-bootstrap`). Discover
and install with:

```sh
herdr plugin list
herdr plugin install <owner>/<repo>[/<subdir>]   # GitHub shorthand
herdr plugin link <path>                          # local dir with herdr-plugin.toml
```

Worth building locally when time allows (track under `shell/.config/herdr/plugins/`,
`herdr plugin link` it, add to `bootstrap-osx`):

- **worktree-bootstrap** -- on the `worktree.created` event, prep a new agent
  worktree (install deps, symlink `.env` / local config).
- **dev-layout** -- a one-key action that lays out an editor / agent / tests split
  via `layout.apply`.

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
