# Dotfiles

Personal dotfiles for a Mac, a homelab NUC and AgentBox boxes,
managed with [chezmoi](https://chezmoi.io). `~/dotfiles` is an ordinary git repo whose
`home/` subdirectory is the chezmoi source (`.chezmoiroot`); chezmoi writes real files (not
links) into `$HOME`, rendering templates per host, and converges each host with two
scripts that run on every apply.

## Layout

Paths in this table are under `home/`, except `docs/` and the repo metadata in the last row.

| Path | What it is |
|---|---|
| `dot_*`, `private_*`, `executable_*`, `symlink_*` | targets: `dot_zshrc.tmpl` becomes `~/.zshrc`, `dot_config/herdr/config.toml.tmpl` becomes `~/.config/herdr/config.toml` ([naming](https://chezmoi.io/reference/source-state-attributes/)) |
| `*.tmpl` | Go templates; host differences are `{{ if }}` branches on `.host`, `.role`, `.extras` |
| `modify_*` + `*.managed.json` | files a program also rewrites; the repo owns only its keys (below) |
| `.chezmoiscripts/` | two scripts run on every apply: `bootstrap` (before files: Xcode CLT, Homebrew, apt) and `converge` (after: the sections in `.chezmoitemplates/converge/`, each acting only when the real state differs; `retired` removes what the repo dropped) |
| `.chezmoi.toml.tmpl`, `.chezmoiignore`, `.chezmoiexternal.toml.tmpl` | host prompts, per-host exclusions, pinned and checksummed downloads (plugin archives, global skills, vim-plug, Linux release binaries) |
| `.chezmoidata/` | pins and lists the templates read: Linux packages, herdr plugins, cooldown allowances, aac-touchid, agent directory grants |
| `lib/` | the Python behind the `modify_` scripts and the converge script, with its tests (run them from `home/`) |
| `docs/` | runbooks (table at the end) |
| `.chezmoiroot`, `.agents/skills/chezmoi/`, `AGENTS.md`, `CLAUDE.md` | repo metadata at the checkout root, outside chezmoi's view: the pointer to `home/`, the reusable chezmoi skill, project policy |

## Hosts

`chezmoi init` asks once for the host, which picks the templates and scripts, and
for `extras`. The answers live in `~/.config/chezmoi/chezmoi.toml`.

| host | machine | one-liner |
|---|---|---|
| `mac-pro` | desk MacBook Pro (role `pro`: the full Brewfile) | see "New Mac" |
| `mac-air` | travel MacBook Air (role `air`: the Brewfile without the desk-only block) | see "New Mac" |
| `nuc` | the homelab NUC (dev environment from `.chezmoidata/linux.json`, docs/linux-packages.md; the server stack is `~/Projects/homelab`) | `chezmoi init --source ~/dotfiles --apply --promptChoice host=nuc` |
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

The converge script then installs the Brewfile, sets zsh as the login shell and Rust's
default toolchain, installs the pinned pi packages and herdr plugins, wires herdr into the
four harnesses, sets up Paseo, and applies the macOS defaults; chezmoi itself deploys
the pinned skills and plugin archives. Afterwards: an SSH
key for GitHub (`ssh-keygen -t ed25519`, add it, then
`git -C ~/dotfiles remote set-url origin git@github.com:justmytwospence/dotfiles.git`),
the age key (below), sign in to each harness ([docs/agents.md](docs/agents.md)),
pair the phone apps ([docs/phone-access.md](docs/phone-access.md)), grant Karabiner
its accessibility permission, and `rbenv install` a Ruby if needed. A second
`chezmoi apply` should print nothing; anything it does print is a step that did not
converge the first time.

Linux hosts install chezmoi to `~/.local/bin`, pinned:
`sh -c "$(curl -fsLS get.chezmoi.io)" -- -b ~/.local/bin -t v2.73.0`.

## Daily workflow

- Edit files in `~/dotfiles/home` (you or an agent), then `chezmoi apply`. Or
  `chezmoi edit --apply ~/.zshrc`. Never edit the copies in `$HOME`: the next apply
  replaces them. Commit and push as usual.
- Other hosts: `chezmoi update` (git pull, then apply; the converge script checks
  every pin and setting and acts only where the host differs). Agents follow [project policy and sync workflow](AGENTS.md#machine-synchronization)
  and the reusable [chezmoi skill](.agents/skills/chezmoi/SKILL.md).
- A program changed a managed file: inspect `chezmoi diff <file>` before applying.
  Scoped `chezmoi re-add <file>` captures regular-file drift but skips templates;
  for partial-ownership settings, curate the managed input instead. Apply may
  prompt before overwriting destination edits; never force blindly.
  `chezmoi verify --exclude scripts` checks file drift (the two always-run scripts
  stay pending); `chezmoi doctor` checks the install. Never run `chezmoi purge`: it
  deletes `~/dotfiles`.
- After `nvm install --lts`, run `nvm alias default 'lts/*'` once per host;
  `.zshenv` follows the alias to put node on PATH.

### Files programs rewrite

`~/.claude/settings.json`, `~/.codex/hooks.json`, `~/.pi/agent/settings.json`,
`~/.claude.json`, `~/.codex/config.toml` and `~/.config/ttt/settings.json` are `modify_`
targets. The repo keeps only its part in a `*.managed.json` (or `mcp.json`); on
apply, the managed keys win and everything else in the live file stays: pi's
`deviceId`, Claude Code's own state, hooks that herdr or agent-deck install.
Hooks are merged per event: the repo's first, then live hooks the repo does not
already have. Hooks naming retired tools (Superset, moshi-hook, Orca, tmux-agents) are purged everywhere. To share a hook a tool
installed on one host, paste it into the managed file.

## Secrets

`TYPESAFE_API_KEY` lives age-encrypted in
`home/dot_config/private_dotfiles/encrypted_private_secrets.env.age`; chezmoi writes
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

The Brewfile (`home/dot_Brewfile.tmpl`) ends with a desk-only block (Docker, XQuartz,
gdal, Postgres, PlantUML, Podman, C++ and Kubernetes tooling, local LLMs, dbt)
rendered only for `mac-pro`. It lists leaves only. `chezmoi apply` runs
`brew bundle check` when the Brewfile changes (and once a day for drift) and
`brew bundle install --global --no-upgrade` when something is missing. Removing a
line uninstalls nothing: add its uninstall step to
`home/.chezmoitemplates/converge/retired.sh`, or preview `brew bundle cleanup --global`
and then `--force`.

## Docs

| Doc | Covers |
|---|---|
| [docs/agents.md](docs/agents.md) | Claude Code, Codex, pi, opencode: skills, instructions, MCP, worktrees, billing, planning |
| [docs/plugins.md](docs/plugins.md) | plugins: native installers, chezmoi archives, pins and local testing |
| [docs/herdr.md](docs/herdr.md) | herdr config and the Ctrl-b key map |
| [docs/phone-access.md](docs/phone-access.md) | herdr PWA and iPhone push, terminal dialog fallback, Paseo |
| [docs/agentbox.md](docs/agentbox.md) | AgentBox: the NUC hub, NUC and Daytona boxes, logins, dotfiles in boxes |
| [docs/linux-packages.md](docs/linux-packages.md) | the Linux package manifest (`linux.json`) and pinned release binaries |
| [docs/cooldown.md](docs/cooldown.md) | the seven-day release cooldown and `cooldown-allow` |
| [docs/git-status.md](docs/git-status.md) | the shared git status line in zsh, tmux, Claude Code and herdr |
| [docs/jupyter.md](docs/jupyter.md) | the Jupyter and IPython configs |
