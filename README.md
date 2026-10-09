# Dotfiles

Personal dotfiles for a Mac, a homelab NUC and AgentBox boxes,
managed with [chezmoi](https://chezmoi.io). `~/dotfiles` is the
chezmoi source directory and an ordinary git repo; chezmoi writes real files (not
links) into `$HOME`, rendering templates and running setup scripts per host.

## Layout

| Path | What it is |
|---|---|
| `dot_*`, `private_*`, `executable_*`, `symlink_*` | targets: `dot_zshrc.tmpl` becomes `~/.zshrc`, `dot_config/herdr/config.toml.tmpl` becomes `~/.config/herdr/config.toml` ([naming](https://chezmoi.io/reference/source-state-attributes/)) |
| `*.tmpl` | Go templates; host differences are `{{ if }}` branches on `.host`, `.role`, `.extras` |
| `modify_*` + `*.managed.json` | files a program also rewrites; the repo owns only its keys (below) |
| `.chezmoiscripts/` | install scripts: `run_once_` (once per host), `run_onchange_` (when their input changes); `85-retired` uninstalls what the repo dropped |
| `.chezmoi.toml.tmpl`, `.chezmoiignore`, `.chezmoiexternal.toml` | host prompts, per-host exclusions, vim-plug at a pinned commit |
| `lib/agent_settings.py` | the merge behind the `modify_` scripts |
| `docs/` | runbooks (table at the end) |

## Hosts

`chezmoi init` asks once for the host, which picks the templates and scripts, and
for `extras`. The answers live in `~/.config/chezmoi/chezmoi.toml`.

| host | machine | one-liner |
|---|---|---|
| `mac-pro` | desk MacBook Pro (role `pro`: the full Brewfile) | see "New Mac" |
| `mac-air` | travel MacBook Air (role `air`: the Brewfile without the desk-only block) | see "New Mac" |
| `nuc` | the homelab NUC (set up by hand; chezmoi installs nothing system-wide there) | `chezmoi init --source ~/dotfiles --apply --promptChoice host=nuc` |
| `agentbox-box` | an AgentBox box (applied by a repo's `agentbox.yaml` task) | [docs/agentbox.md](docs/agentbox.md) |

`extras` is a comma-separated list, empty by default: `emacs` (`~/.emacs.d`, the
emacs user service), `jupyter` ([docs/jupyter.md](docs/jupyter.md)),
`linux-desktop` (i3, polybar, rofi, Alacritty, kitty, terminator, GNOME bits;
[linux-desktop/README.md](linux-desktop/README.md)). Change them by editing
`extras` in `~/.config/chezmoi/chezmoi.toml`, then `chezmoi apply`.

### New Mac

```sh
xcode-select --install                     # wait for it to finish
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/opt/homebrew/bin/brew shellenv)" && brew install chezmoi
git clone https://github.com/justmytwospence/dotfiles.git ~/dotfiles
chezmoi init --source ~/dotfiles --apply --promptChoice host=mac-pro --promptString extras=emacs
```

The scripts then install the Brewfile, set zsh as the login shell, install Python
(uv) and Rust, sync the plugins and skills, wire herdr into the four harnesses,
set up Paseo and Heeler, and apply the macOS defaults. Afterwards: an SSH
key for GitHub (`ssh-keygen -t ed25519`, add it, then
`git -C ~/dotfiles remote set-url origin git@github.com:justmytwospence/dotfiles.git`),
the age key (below), sign in to each harness ([docs/agents.md](docs/agents.md)),
pair the phone apps ([docs/phone-access.md](docs/phone-access.md)), grant Karabiner
its accessibility permission, and `rbenv install` a Ruby if needed. Run
`chezmoi apply` once more after the first one: the herdr installer adds hook entries
the second pass folds into the repo's.

Linux hosts install chezmoi to `~/.local/bin`, pinned:
`sh -c "$(curl -fsLS get.chezmoi.io)" -- -b ~/.local/bin -t v2.73.0`.

## Daily workflow

- Edit files in `~/dotfiles` (you or an agent), then `chezmoi apply`. Or
  `chezmoi edit --apply ~/.zshrc`. Never edit the copies in `$HOME`: the next apply
  replaces them. Commit and push as usual.
- Other hosts: `chezmoi update` (git pull, then apply; the plugin and skill syncs
  run when their inputs changed). The `dotfiles-sync` skill does this for every host.
- A program changed a managed file: `chezmoi diff` shows it; `chezmoi re-add <file>`
  keeps it, `chezmoi apply` discards it. `chezmoi verify` fails on any drift;
  `chezmoi doctor` checks the install. Never run `chezmoi purge`: it deletes
  `~/dotfiles`.
- After `nvm install --lts`, run `nvm alias default 'lts/*'` once per host;
  `.zshenv` follows the alias to put node on PATH.

### Files programs rewrite

`~/.claude/settings.json`, `~/.codex/hooks.json`, `~/.pi/agent/settings.json`,
`~/.claude.json` and `~/.codex/config.toml` are `modify_`
targets. The repo keeps only its part in a `*.managed.json` (or `mcp.json`); on
apply, the managed keys win and everything else in the live file stays: pi's
`deviceId`, Claude Code's own state, hooks that herdr, Orca or agent-deck install.
Hooks are merged per event: the repo's first, then live hooks the repo does not
already have. Hooks naming Superset or moshi-hook (retired tools) are purged everywhere. To share a hook a tool
installed on one host, paste it into the managed file.

## Secrets

`TYPESAFE_API_KEY` and `MODEL_API_KEY` live age-encrypted in
`dot_config/private_dotfiles/encrypted_private_secrets.env.age`; chezmoi writes
`~/.config/dotfiles/secrets.env` and `.zshenv` sources it, so non-interactive shells get it too. The key is
`~/.config/chezmoi/key.txt`, copied once per host over ssh and never committed:

```sh
scp ~/.config/chezmoi/key.txt <host>:.config/chezmoi/key.txt && ssh <host> chezmoi apply
```

Without the key the file is skipped (the Macs and the NUC use it; the
fleet hubs keep their own secret stores). Edit with
`chezmoi edit ~/.config/dotfiles/secrets.env`.

## Local overrides

Untracked, sourced or included after the managed files: `~/.zshenv.local`,
`~/.zshrc.local`, `~/.gitconfig.local` (e.g. a work email).

## Mac roles

The Brewfile (`dot_Brewfile.tmpl`) ends with a desk-only block (Docker, XQuartz,
gdal, Postgres, PlantUML, Podman, C++ and Kubernetes tooling, local LLMs, dbt)
rendered only for `mac-pro`. It lists leaves only. After a Brewfile change,
`chezmoi apply` runs `brew bundle install --global --no-upgrade`; to remove what
the file no longer lists, `brew bundle cleanup --global` (preview) and `--force`.

## Docs

| Doc | Covers |
|---|---|
| [docs/agents.md](docs/agents.md) | Claude Code, Codex, pi, opencode: skills, instructions, MCP, worktrees, billing, planning |
| [docs/plugins.md](docs/plugins.md) | the self-maintained plugins, pins, `plugins sync/try/pin` |
| [docs/herdr.md](docs/herdr.md) | herdr config and the Ctrl-b key map |
| [docs/phone-access.md](docs/phone-access.md) | Heeler, Paseo |
| [docs/agentbox.md](docs/agentbox.md) | AgentBox: the NUC hub, NUC and Daytona boxes, logins, dotfiles in boxes |
| [docs/migration.md](docs/migration.md) | moving a host from GNU Stow to chezmoi, and back |
| [docs/jupyter.md](docs/jupyter.md) | the Jupyter and IPython configs |
