# Dotfiles project

Before changing this repo or applying its configuration, read `.agents/skills/chezmoi/SKILL.md` for general chezmoi mechanics. This file owns all project-specific policy, including host behavior, settings ownership, provisioning, secrets, and machine synchronization. Paths below are relative to the checkout root unless stated otherwise.

`AGENTS.md`, its `CLAUDE.md` symlink, and the project-local skill/Claude bridge are repo metadata, never deployed into `$HOME`. The chezmoi skill is reusable; do not put this project's policy in it.

## Source and change workflow

- Source is normally `~/dotfiles`; destination is `$HOME`. Targets are real files unless explicitly declared symlinks; this is no longer GNU Stow.
- Check `git status --short` and `chezmoi source-path <target>` before editing. Edit source, never deployed copies, and preserve unrelated Git and live-state changes. Read the relevant script and runbook.
- Do not create a worktree unless requested. In an alternate checkout, use `chezmoi --source <checkout>` explicitly; normal apply still reads the configured checkout.
- Our config excludes scripts from ordinary diffs and verbose dry-run output. Inspect `chezmoi diff --include scripts --exclude encrypted` separately from file previews. Excluding encrypted entries does not hide secrets in templates; scope secret-bearing previews further.
- Test rendered syntax, host branches, and settings merges before applying. Apply reviewed targets; use a full apply only when setup/sync scripts must run. Verify with `chezmoi verify --exclude scripts <target>...`, inspect residual `chezmoi status`, and test the affected program. Always-run scripts remain pending `R`.
- Never use blanket `add`/`re-add`, `--force`, `destroy`, `state reset`, or `purge`. Approved repo-wins may use **scoped** `apply --force <target>` after review. Host-wins means curating source or an allowed local override; do not capture partial-ownership settings with `re-add`.
- Commit only this change's files using a conventional commit when authorized. After commit/push/apply, follow **Machine synchronization** below; unpushed source cannot reach another host through `update`.

## Hosts and templates

`.chezmoi.toml.tmpl` defines the current hosts and generates `~/.config/chezmoi/chezmoi.toml` during init. Its `prompt*Once` answers become `[data]`; ordinary apply does not regenerate that config. Do not use the historical migration runbook as the current host specification.

| Host | Policy |
|---|---|
| `mac-pro` | Desk Mac, role `pro`: full Brewfile and local-model services |
| `mac-air` | Travel Mac, role `air`: lighter Brewfile |
| `nuc` | Debian hub: Linux manifest for the dev environment; the server stack stays in `~/Projects/homelab` |
| `agentbox-box` | Box bootstrap; no herdr, follows `docs/agentbox.md` |

- Branch on `.host`, `.role`, `.extras`. `.extras` is a comma-separated list: `emacs`, `jupyter`, `linux-desktop`. Change machine-local answers in config, or deliberately regenerate with `init`; do not encode one machine's choices in shared source.
- Use `.chezmoi.homeDir` for portable paths and `.chezmoitemplates/` for shared snippets. Preserve template newlines, script shebangs, and destination-format quoting.
- Local overrides are untracked `~/.zshenv.local`, `~/.zshrc.local`, `~/.gitconfig.local`. Shell overrides load last; Git's local include currently precedes managed identity keys, so it cannot override those keys. Check include order before relying on precedence.
- `.chezmoiignore` excludes repo-only paths and managed merge inputs from deployment; its patterns match target paths. Dot-prefixed metadata is automatically ignored except `.chezmoi*`.

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

- Managed JSON files are inputs, excluded from deployment. Hooks merge managed-first per event, preserving unrelated live hooks; retired Superset/moshi hooks are purged. Hook deduplication uses command/script identity, not arbitrary deep equality. Some fields replace wholesale; inspect the implementation rather than assuming every list merges.
- The Pi suite migration is complete: do not enable the retired npm packages alongside suite components. Tests for the settings merge and managed configuration: `python3 -B -m unittest lib/test_agent_settings.py`.
- Deleting a managed key/hook does **not** necessarily delete its live value: it can survive as unmanaged state. MCP removal likewise needs explicit cleanup. Test intended deletions and absent/valid/malformed input cases; do not flatten live state into a tracked whole-file replacement.
- Marker-scoped MCP entries produce project overrides and Codex trust entries for immediate repos under `~/Projects`, not their worktrees. A full apply can therefore change files outside this repo. See `docs/agents.md`.

## Provisioning and dependencies

| Script | Trigger/purpose |
|---|---|
| `10-packages` | Before, on change: Mac bootstrap; Linux apt list (sudo, install-only) |
| `25-linux-tools` | On list change, Linux: uv tools, npm globals, vendor installers (install-only) |
| `20-brew-bundle` | On rendered Brewfile change, Macs only: install with `--no-upgrade` |
| `30-shell`, `50-agents`, `60-phone`, `70-macos-defaults`, `80-host` | Once: host/runtime/integration setup |
| `51-herdr-hooks` | On herdr version change: `herdr integration install` for claude/codex/pi/opencode, folded into the managed hooks |
| `05-plugin-archives` | Before, on archive changes: refuse to overwrite dirty/off-pin legacy plugin checkouts |
| `40-plugins` | On pin/settings changes: native Pi Git reconciliation and Herdr installs |
| `46-project-mcp` | Every apply: project MCP overrides |
| `85-retired` | On script change: remove retired installs/state |

- Keep scripts idempotent and ordered. Hash dependencies into onchange comments (rendered hash for host-dependent input); reuse `script-path.sh`. Do not assume cwd is the source repo or rely on before scripts to supply already-rendered inputs.
- Several installers swallow failures: exit 0 does not prove success, and unchanged scripts may not retry. Verify plugin/skill/service state and retry the actual installer if needed. Never reset all persistent state merely to rerun one script.
- Macs declare formula/cask/npm/uv dependencies in `dot_Brewfile.tmpl`, with desk-only dependencies in its role branch. Install does not upgrade or uninstall. Preview `brew bundle cleanup --global` before any authorized `--force` cleanup; retiring deployed tools may also need `85-retired`.
- Linux hosts (`nuc`, `agentbox-box`) declare apt, release-binary, npm, uv and installer dependencies in `.chezmoidata/linux.json` (`docs/linux-packages.md`). Release binaries are pinned externals; bump them only with `python3 lib/linux_releases.py pin <name>`, which honors the seven-day cooldown (except entries marked `"cooldown": false`, currently herdr, or an explicitly requested `--tag`) and records checksums. Everything is install-only.
- Maintained plugins are developed under `~/Projects`, never in installed copies. Follow `docs/plugins.md` for native local testing and publication. Publish first, then edit native package specs/Herdr refs or chezmoi external URLs and checksums. There is no custom plugin manager.
- Global third-party skills are pinned, checksummed archives in `.chezmoiexternal.toml.tmpl`; personal global skills live under `dot_agents/skills`. The reusable chezmoi skill is installed project-locally in `.agents/skills`, with a Claude bridge under `.claude/skills`; its local installation does not make its content project policy.
- npm and uv hold back new releases seven days, with configured exceptions. Pi (`@earendil-works/*`, Homebrew on Macs) and herdr (Homebrew on Macs, `"cooldown": false` on Linux) are exempt. A release I explicitly ask to install or upgrade goes through without asking, exactly that release and only that package, via `docs/cooldown.md` (`cooldown-allow`, recorded in `.chezmoidata/cooldown.json` so provisioning on every declaring host accepts it, and lapsing after seven days). Never bypass the cooldown otherwise: not with `--min-release-age=0`, a broad `min-release-age-exclude`, or a far-future uv date for a package I don't maintain.
- `.chezmoiexternal.toml` uses pinned URLs plus checksums; update both together. Review archive paths/strip counts and deletion effects of `exact = true`. Do not edit installed external contents; consumers of newly installed externals belong in after scripts.

## Secrets and boundaries

Age encryption is configured in `.chezmoi.toml.tmpl`; identity `~/.config/chezmoi/key.txt` stays untracked. Secret source is `dot_config/private_dotfiles/encrypted_private_secrets.env.age`, deployed only on eligible hosts with the key. Edit via `chezmoi edit ~/.config/dotfiles/secrets.env`, not by writing plaintext into Git.

Encryption protects source, not deployed plaintext. Render/diff/debug/archive output can expose secrets; avoid printing them. Harness authentication is machine-local and interactive, never committed. AgentBox Git operations go through its hub; do not add credentials inside a box.

## Machine synchronization

Use after a dotfiles commit, push, or apply. Local apply only changes this machine; NUC `update` pulls published source and then applies it. Never imply an unpushed local edit reached another host.

### Sequence

This sequence is for the configured `~/dotfiles` checkout on branch `main`: verify source path and branch first. If working elsewhere, commit in that checkout and obtain authorization to merge into main before publishing/applying; never stage another checkout's work or push an unrelated main branch. Edit pins in the checkout you are working in; use its source explicitly when applying.

When commit/push is authorized, stage only this logical change; preserve unrelated drift:

```sh
git -C ~/dotfiles add <changed-paths>
git -C ~/dotfiles commit -m "<conventional commit>"
git -C ~/dotfiles push origin main
chezmoi apply
ssh -o BatchMode=yes -o ConnectTimeout=10 spencer@nuc \
  '~/.local/bin/chezmoi update --no-tty'
```

Run commands separately or with success-gated chaining: do not hide an error behind a pipe or continue after a failed push/apply. Never push from another host. If only local apply is authorized, report that propagation of uncommitted/unpushed source remains pending; do not invent permission to publish it.

Verify the commit on both hosts with `git -C ~/dotfiles log -1 --oneline`. Check `chezmoi verify --exclude scripts` (or scoped changed targets), inspect residual `chezmoi status`, and check actual deployed files/programs. Classify drift rather than treating any nonzero exit as success.

- **NUC:** Debian, host `nuc`, using `~/.local/bin/chezmoi`; its herdr server is the default session (the only one; the old `homelab` session is retired). A Mac Brewfile change is not a NUC installation; the NUC follows `.chezmoidata/linux.json`. An apt-list change needs sudo, so `update --no-tty` stops at `10-packages`: rerun `chezmoi apply` in an interactive ssh session.
- **Other Mac (`mac-pro` or `mac-air`):** out of reach from here and never remote-managed. It picks up whatever is pushed at its next `chezmoi update`, so do not list it as pending, remind me to update it, or end with a step for it. Mention it only when that update alone will not work there (a manual step or a known failure on that host).
- **AgentBox boxes (`agentbox-box`):** not synced remotely; each reapplies `origin/main` on startup through its repository's `agentbox.yaml` task. See `docs/agentbox.md`.

### Conflicts and failures

`chezmoi update` normally runs `git pull --autostash --rebase` then apply. An unavailable host, failed pull, script error, or unresolved drift means synchronization is incomplete.

If apply stops on changed destination contents, inspect `chezmoi diff <target>` on that host. Never force blindly. User-approved repo-wins permits scoped `apply --force <target>`; host-wins means moving the change into shared source, a host branch, or a permitted local override.

If a remote rebase conflicts, do not resolve or discard the host's work blindly. Abort the rebase if one is in progress, inspect status, report and stop:

```sh
ssh spencer@nuc 'cd ~/dotfiles && git rebase --abort && git status --short'
```

Post-quantum key-exchange and remote-port-forwarding warnings are expected SSH noise, not evidence the command failed or succeeded. Preserve the actual SSH exit status when filtering output.

### Plugins and reloads

Publish the plugin commit first, verify it is on origin, then update its native spec/installer ref or external URL and checksum, and commit the changed dotfiles pins when authorized. Follow `docs/plugins.md` for locations and testing; never edit installed copies over SSH.

After sync, verify archives with scoped `chezmoi verify --exclude scripts`, Pi Git checkout HEADs against settings (`pi list`), and Herdr installs with `herdr plugin list`. Reload running pi with `/reload`, tmux with `tmux source ~/.tmux.conf`. Installing a herdr plugin does not run its startup hook: invoke its documented reapply action or restart herdr. For herdr-agentbox on the NUC, stop the old daemon then `agentbox-space daemon --ensure` as documented. Report off-pin plugins or failed reloads rather than silently accepting them.

## Runbooks

- `README.md`: human setup/layout guide
- `docs/agents.md`: harness ownership
- `docs/plugins.md`: plugin lifecycle
- `docs/agentbox.md`: box bootstrap
- `docs/linux-packages.md`: Linux package manifest
- `docs/migration.md`: historical Stow migration
