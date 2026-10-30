# Dotfiles project

Before changing this repo or applying its configuration, read `.agents/skills/chezmoi/SKILL.md` for general chezmoi mechanics. This file owns all project-specific policy, including host behavior, settings ownership, provisioning, secrets, and machine synchronization. Source paths below (such as `dot_config/...`, `.chezmoiscripts/`, `lib/...`) are relative to `home/`, the chezmoi source root (`docs/` spells them out as `home/...`); `AGENTS.md`, `README.md`, `docs/`, `.agents/` and `.worktrees/` are at the checkout root. Run `lib/` commands and tests from `home/`.

`AGENTS.md`, its `CLAUDE.md` symlink, and the project-local skill/Claude bridge are repo metadata, never deployed into `$HOME`. The chezmoi skill is reusable; do not put this project's policy in it.

## Source and change workflow

- Source is normally `~/Projects/dotfiles`; `.chezmoiroot` makes chezmoi read only its `home/` subdirectory (`chezmoi source-path` and `$CHEZMOI_SOURCE_DIR` are `~/Projects/dotfiles/home`). Everything chezmoi reads, `.chezmoi*` files and `lib/` included, goes under `home/`; repo metadata stays outside it. This keeps worktrees in `.worktrees/` invisible to chezmoi; inside the source, their `.chezmoidata/` would override the real data. Destination is `$HOME`. Targets are real files unless explicitly declared symlinks.
- Check `git status --short` and `chezmoi source-path <target>` before editing. Edit source, never deployed copies, and preserve unrelated Git and live-state changes. Read the relevant script and runbook.
- Do not create a worktree unless requested. In an alternate checkout, use `chezmoi --source <checkout>` explicitly; normal apply still reads the configured checkout.
- Our config excludes scripts from ordinary diffs and verbose dry-run output. Inspect `chezmoi diff --include scripts --exclude encrypted` separately from file previews. Excluding encrypted entries does not hide secrets in templates; scope secret-bearing previews further.
- Test rendered syntax, host branches, and settings merges before applying. Apply reviewed targets; use a full apply when provisioning must converge (it runs both scripts). Verify with `chezmoi verify --exclude scripts <target>...`, inspect residual `chezmoi status`, and test the affected program. Both scripts always remain pending `R`.
- Never use blanket `add`/`re-add`, `--force`, `destroy`, `state reset`, or `purge`. Approved repo-wins may use **scoped** `apply --force <target>` after review. Host-wins means curating source or an allowed local override; do not capture partial-ownership settings with `re-add`.
- Commit only this change's files using a conventional commit when authorized. After commit/push/apply, follow **Machine synchronization** below; unpushed source cannot reach another host through `update`.

## Hosts and templates

`.chezmoi.toml.tmpl` defines the current hosts and generates `~/.config/chezmoi/chezmoi.toml` during init. Its `prompt*Once` answers become `[data]`; ordinary apply does not regenerate that config. After changing the template, run `chezmoi init` on each host (it reuses the stored answers; chezmoi warns until then). The template records `.chezmoi.workingTree` (the repo) as `sourceDir`, never `.chezmoi.sourceDir` (`home/`).

| Host | Policy |
|---|---|
| `mac-pro` | Desk Mac, role `pro`: full Brewfile and local-model services |
| `mac-air` | Travel Mac, role `air`: lighter Brewfile |
| `nuc` | Debian hub: Linux manifest for the dev environment; the server stack stays in `~/Projects/homelab` |
| `agentbox-box` | Box bootstrap; no herdr, follows `docs/agentbox.md` |

- Branch on `.host`, `.role`, `.extras`. `.extras` is a comma-separated list: `emacs`, `jupyter`, `linux-desktop`. Change machine-local answers in config, or deliberately regenerate with `init`; do not encode one machine's choices in shared source.
- Use `.chezmoi.homeDir` for portable paths and `.chezmoitemplates/` for shared snippets. Preserve template newlines, script shebangs, and destination-format quoting.
- Local overrides are untracked `~/.zshenv.local`, `~/.zshrc.local`, `~/.gitconfig.local`. Shell overrides load last; Git's local include currently precedes managed identity keys, so it cannot override those keys. Check include order before relying on precedence.
- `.chezmoiignore` excludes `lib/`, managed merge inputs and per-host targets from deployment; its patterns match target paths. Repo-only files belong outside `home/`, not in `.chezmoiignore`. Dot-prefixed metadata is automatically ignored except `.chezmoi*`.

## Settings programs rewrite

`modify_*` wrappers import `lib/agent_settings.py` through the source path. Edit managed inputs unless changing merge behavior; test changes on fixtures, not production files.

| Target | Source and ownership |
|---|---|
| `~/.claude/settings.json` | `private_dot_claude/settings.managed.json`: managed keys win; hooks merge |
| `~/.codex/hooks.json` | `private_dot_codex/hooks.managed.json`: managed keys win; hooks merge |
| `~/.pi/agent/settings.json` | `private_dot_pi/private_agent/settings.managed.json`: managed keys win; additional local-path packages survive |
| `~/.pi/agent/pi-plan-mode.json` | Neighboring `pi-plan-mode.managed.json`: **live settings win**; defaults fill missing keys |
| `~/.config/ttt/settings.json` | `dot_config/ttt/settings.managed.json`: recursive managed-wins merge |
| `~/.claude.json`, `~/.codex/config.toml`, `~/.config/mcp/mcp.json` | `dot_config/mcp/mcp.managed.json` (`hosts` gates a server per machine), plus explicit pins in the merge library; unrelated application state survives |

- Managed JSON files are inputs, excluded from deployment. Hooks merge managed-first per event, preserving unrelated live hooks; hooks of retired tools (`DENY` in `lib/agent_settings.py`: Superset, moshi-hook, Orca, tmux-agents) are purged. Hook deduplication uses command/script identity, not arbitrary deep equality. Some fields replace wholesale; inspect the implementation rather than assuming every list merges.
- Never enable a component's original npm or Git package alongside its suite copy. Tests for the settings merge and managed configuration: `(cd home && python3 -B -m unittest lib/test_agent_settings.py)`.
- Deleting a managed key/hook does **not** necessarily delete its live value: it can survive as unmanaged state. MCP removal likewise needs explicit cleanup. Test intended deletions and absent/valid/malformed input cases; do not flatten live state into a tracked whole-file replacement.
- Marker-scoped MCP entries produce project overrides and Codex trust entries for immediate repos under `~/Projects`, not their worktrees. A full apply can therefore change files outside this repo. See `docs/agents.md`.

## Provisioning and dependencies

Provisioning is exactly two scripts, both run on every apply, each rendered per host:

| Script | Job |
|---|---|
| `.chezmoiscripts/run_before_bootstrap.sh.tmpl` | Before any file is written: Mac Xcode CLT and Homebrew; Linux NodeSource (NUC) and the apt list (sudo only when something is missing) |
| `.chezmoiscripts/run_after_converge.sh.tmpl` | After the files: one section per concern from `.chezmoitemplates/converge/`, in order: `retired`, `brew-bundle` / `linux-tools`, `uv-tools`, `login-shell`, `pi-packages`, `herdr-plugins`, `herdr-hooks`, `herdr-status`, `aac-touchid`, `herdr-menu`, `paseo`, `omnigent-host`, `macos-defaults`, `lid-sleep-sudoers`, `project-mcp`. Each section gates itself by host |

### Converge, never accumulate

- New provisioning is a section in `.chezmoitemplates/converge/` (a `converge_<name>` function plus `run converge_<name>`, included from `run_after_converge.sh.tmpl`), never a new script. Do not add `run_once_` or `run_onchange_` scripts.
- A section states desired state: it checks the real state first, cheaply, and acts only on a difference. It prints nothing when nothing changes and must be safe on every apply. Prefer the tool's own status (`herdr plugin list`, `herdr integration status`, a checkout's HEAD, `defaults read`); where there is none, use the `stamped`/`stamp` helpers (`~/.local/state/dotfiles/converge/`). Disruptive actions (restarts, sudo or password prompts, the aac-touchid vault lock, rebuilds) happen only on a real difference.
- A failed section records itself and the others still run; the script then fails, so the next apply retries. Never swallow a failure to keep apply green, except where a section says so explicitly (`project-mcp`).
- Pins and lists live in `.chezmoidata/` or the managed inputs, not in script bodies.
- No vestigial state. Removing or replacing anything this repo installed or configured (a package, plugin, hook, LaunchAgent or systemd unit, a managed file or a renamed target, a settings key, an MCP server, a skill) adds, in the same commit, an idempotent ensure-absent step to `converge/retired.sh` (or a `.chezmoiremove` entry for a plain target). Deleting the line that installed it is not enough: chezmoi, Homebrew, apt, npm and the settings merges all leave the old thing in place.
- Retired entries carry their retirement date. Prune one once it is absent on mac-pro and the NUC and more than three weeks old (mac-air is not reachable from here and catches up at its next update).
- Test with `(cd home && python3 -B -m unittest lib/test_plugin_deployment.py)` (all of them: `(cd home && python3 -B -m unittest lib/test_*.py)`): every host renders and passes `bash -n`, and sections are exercised with mocked commands. After an apply, a second apply must print nothing.

- Several installers swallow failures: exit 0 does not prove success. Verify plugin/skill/service state; a section that checks real state retries on the next apply. Never reset chezmoi's persistent state to rerun anything.
- Macs declare formula/cask/npm/uv dependencies in `dot_Brewfile.tmpl`, with desk-only dependencies in its role branch. Install does not upgrade or uninstall. Preview `brew bundle cleanup --global` before any authorized `--force` cleanup; retiring a deployed tool needs its step in `converge/retired.sh`.
- Linux hosts (`nuc`, `agentbox-box`) declare apt, release-binary, npm, uv and installer dependencies in `.chezmoidata/linux.json` (`docs/linux-packages.md`). Release binaries are pinned externals; bump them only with `python3 home/lib/linux_releases.py pin <name>`, which picks the newest release past the cooldown (herdr is `"cooldown": false`; `--tag` takes a release I asked for) and records checksums. Everything is install-only.
- Maintained plugins are developed under `~/Projects`, never in installed copies. Follow `docs/plugins.md` for native local testing and publication. Publish first, then edit the pins: Pi specs in `private_dot_pi/private_agent/settings.managed.json`, Herdr refs in `.chezmoidata/herdr_plugins.json`, chezmoi external URLs and checksums in `.chezmoiexternal.toml.tmpl`; the converge script installs them. There is no custom plugin manager.
- Global third-party skills are pinned, checksummed archives in `.chezmoiexternal.toml.tmpl`; personal global skills live under `dot_agents/skills`. The reusable chezmoi skill is installed project-locally in `.agents/skills`, with a Claude bridge under `.claude/skills`; its local installation does not make its content project policy.
- Release cooldown (`docs/cooldown.md`): each package manager holds releases younger than seven days in its own config (`~/.npmrc`, pnpm `config.yaml`, `~/.yarnrc.yml`, `~/.bunfig.toml`, uv `uv.toml`, pip on the Macs), rendered from `.chezmoidata/cooldown.json`. `cooldownExempt` holds the standing exemptions (Pi, herdr via `"cooldown": false`, marimo and my own packages). `cooldownAllow` holds exact `pkg@version` npm-registry releases let through early, read natively by pnpm, yarn and bun and by pi's `npm-cooldown`; entries go inert once the release is a week old. A uv tool takes a per-package cutoff that the `uv-tools` section drops after seven days. Overrides are only for a release I asked for; never disable the cooldown (`--min-release-age=0`, broad excludes, `exclude-newer = false`).
- `.chezmoiexternal.toml` uses pinned URLs plus checksums; update both together. Review archive paths/strip counts and deletion effects of `exact = true`. Do not edit installed external contents; consumers of newly installed externals belong in a converge section.

## Secrets and boundaries

Age encryption is configured in `.chezmoi.toml.tmpl`; identity `~/.config/chezmoi/key.txt` stays untracked. Secret source is `dot_config/private_dotfiles/encrypted_private_secrets.env.age`, deployed only on eligible hosts with the key. Edit via `chezmoi edit ~/.config/dotfiles/secrets.env`, not by writing plaintext into Git.

Encryption protects source, not deployed plaintext. Render/diff/debug/archive output can expose secrets; avoid printing them. Harness authentication is machine-local and interactive, never committed. AgentBox Git operations go through its hub; do not add credentials inside a box.

## Machine synchronization

Use after a dotfiles commit, push, or apply. Local apply only changes this machine; NUC `update` pulls published source and then applies it. Never imply an unpushed local edit reached another host.

### Sequence

This sequence is for the configured `~/Projects/dotfiles` checkout on branch `main`: verify source path and branch first. If working elsewhere, commit in that checkout and obtain authorization to merge into main before publishing/applying; never stage another checkout's work or push an unrelated main branch. Edit pins in the checkout you are working in; use its source explicitly when applying.

When commit/push is authorized, stage only this logical change; preserve unrelated drift:

```sh
git -C ~/Projects/dotfiles add <changed-paths>
git -C ~/Projects/dotfiles commit -m "<conventional commit>"
git -C ~/Projects/dotfiles push origin main
chezmoi apply
ssh -o BatchMode=yes -o ConnectTimeout=10 spencer@nuc \
  '~/.local/bin/chezmoi update --no-tty'
```

Run commands separately or with success-gated chaining: do not hide an error behind a pipe or continue after a failed push/apply. Never push from another host. If only local apply is authorized, report that propagation of uncommitted/unpushed source remains pending; do not invent permission to publish it.

Verify the commit on both hosts with `git -C ~/Projects/dotfiles log -1 --oneline`. Check `chezmoi verify --exclude scripts` (or scoped changed targets), inspect residual `chezmoi status`, and check actual deployed files/programs. Classify drift rather than treating any nonzero exit as success.

- **NUC:** Debian, host `nuc`, using `~/.local/bin/chezmoi`; its herdr server is the default session, the only one. A Mac Brewfile change is not a NUC installation; the NUC follows `.chezmoidata/linux.json`. An apt-list change needs sudo, so `update --no-tty` stops at the bootstrap script: rerun `chezmoi apply` in an interactive ssh session.
- **Other Mac (`mac-pro` or `mac-air`):** out of reach from here and never remote-managed. It picks up whatever is pushed at its next `chezmoi update`, so do not list it as pending, remind me to update it, or end with a step for it. Mention it only when that update alone will not work there (a manual step or a known failure on that host).
- **AgentBox boxes (`agentbox-box`):** not synced remotely; each reapplies `origin/main` on startup through its repository's `agentbox.yaml` task. See `docs/agentbox.md`.

### Conflicts and failures

`chezmoi update` normally runs `git pull --autostash --rebase` then apply. An unavailable host, failed pull, script error, or unresolved drift means synchronization is incomplete.

If apply stops on changed destination contents, inspect `chezmoi diff <target>` on that host. Never force blindly. User-approved repo-wins permits scoped `apply --force <target>`; host-wins means moving the change into shared source, a host branch, or a permitted local override.

If a remote rebase conflicts, do not resolve or discard the host's work blindly. Abort the rebase if one is in progress, inspect status, report and stop:

```sh
ssh spencer@nuc 'cd ~/Projects/dotfiles && git rebase --abort && git status --short'
```

Post-quantum key-exchange and remote-port-forwarding warnings are expected SSH noise, not evidence the command failed or succeeded. Preserve the actual SSH exit status when filtering output.

### Plugins and reloads

Publish the plugin commit first, verify it is on origin, then update its pin (see **Provisioning and dependencies**), and commit the changed dotfiles pins when authorized. Follow `docs/plugins.md` for locations and testing; never edit installed copies over SSH.

After sync, verify archives with scoped `chezmoi verify --exclude scripts`, Pi Git checkout HEADs against settings (`pi list`), and Herdr installs with `herdr plugin list`. Reload running pi with `/reload`, tmux with `tmux source ~/.tmux.conf`. Installing a herdr plugin does not run its startup hook: invoke its documented reapply action or restart herdr. For herdr-agentbox on the NUC, stop the old daemon then `agentbox-space daemon --ensure` as documented. Report off-pin plugins or failed reloads rather than silently accepting them.

## Runbooks

- `README.md`: human setup/layout guide
- `docs/agents.md`: harness ownership
- `docs/plugins.md`: plugin lifecycle
- `docs/herdr.md`: herdr config, hooks and key map
- `docs/phone-access.md`: herdr PWA, push, Paseo
- `docs/agentbox.md`: box bootstrap
- `docs/linux-packages.md`: Linux package manifest
- `docs/cooldown.md`: release cooldown, exemptions and per-tool overrides
- `docs/git-status.md`: the shared git status line
- `docs/jupyter.md`: Jupyter and IPython (extras)
