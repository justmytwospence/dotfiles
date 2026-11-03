# Dotfiles project

Before changing this repo or applying its configuration, read `.agents/skills/chezmoi/SKILL.md` for general chezmoi mechanics. This file owns all project-specific policy, including host behavior, settings ownership, provisioning, secrets, and machine synchronization. Source paths below (such as `dot_config/...`, `.chezmoiscripts/`, `lib/...`) are relative to `home/`, the chezmoi source root (`docs/` spells them out as `home/...`); `AGENTS.md`, `README.md`, `docs/`, `.agents/` and `.worktrees/` are at the checkout root. Run `lib/` commands and tests from `home/`.

`AGENTS.md`, its `CLAUDE.md` symlink, and the project-local skill/Claude bridge are repo metadata, never deployed into `$HOME`. The chezmoi skill is reusable; do not put this project's policy in it.

## Source and change workflow

- Source is normally `~/Projects/dotfiles`; `.chezmoiroot` makes chezmoi read only its `home/` subdirectory (`chezmoi source-path` and `$CHEZMOI_SOURCE_DIR` are `~/Projects/dotfiles/home`). Everything chezmoi reads, `.chezmoi*` files and `lib/` included, goes under `home/`; repo metadata stays outside it. This keeps worktrees in `.worktrees/` invisible to chezmoi; inside the source, their `.chezmoidata/` would override the real data. Destination is `$HOME`. Targets are real files unless explicitly declared symlinks.
- **`$HOME` tracks committed `main`.** The main checkout is the deploy checkout: kept clean, on `main`, changed only by fast-forwards. A chezmoi pre-apply/pre-update hook (`lib/apply_guard.sh`, wired in `.chezmoi.toml.tmpl` on every host but boxes) refuses to apply from a linked worktree, another branch, or with uncommitted changes under `home/`; `DOTFILES_ALLOW_DIRTY_APPLY=1` overrides it for one deliberate command.
- **Every change is made in its own worktree**: this repo's standing request, so sessions run in parallel without touching each other or `$HOME`. Create `.worktrees/<branch>` from `main` (in herdr, `herdr worktree create --cwd ~/Projects/dotfiles --branch <branch> --path ~/Projects/dotfiles/.worktrees/<branch> --no-focus`), commit there, and land with `bin/land` (below). A worktree never applies, not even one target: to see a change live, land it, then fix forward or `git revert` and land again. Pin bumps are no exception; a throwaway worktree costs seconds.
- Check `git status --short` and `chezmoi source-path <target>` before editing. Edit source, never deployed copies, and preserve unrelated Git and live-state changes. Read the relevant script and runbook.
- **`bin/check [path]`** proves a checkout without touching `$HOME`: runs every test (`home/lib/test_*.py`, `bin/test_*.py`), then renders `main`'s committed tree and the checkout through `chezmoi archive --exclude scripts,encrypted,externals`, lists the targets that differ (names only, never contents), and checks each changed JSON, TOML, shell or ghostty target with its format's own parser. For one target's rendering use `chezmoi --source <checkout> cat <target>`; for other hosts, `--override-data '{"host":"nuc"}'`.
- **`bin/land [branch]`** (from the worktree, or with the branch name) is the only way a change reaches `$HOME`: it takes a lock (sessions land one at a time), refuses a dirty branch or a main checkout with changes under `home/`, fast-forwards `main` to `origin/main`, rebases the branch onto `main`, runs `bin/check`, fast-forwards `main`, pushes, runs `chezmoi init` when `.chezmoi.toml.tmpl` changed, applies and verifies, then syncs the NUC. A rebase conflict stops it with nothing merged: resolve in the worktree, `git rebase --continue`, run it again (rerere remembers the resolution). `--remove` (or later `bin/land --remove-only <branch>`) removes the landed worktree, its herdr space and branch; `bin/land main` publishes commits made directly on `main` (such as `chezmoi edit` of the secrets file). It runs on the Macs only.
- The tracked `.githooks/pre-push` runs the tests on any push of `main` that `bin/land` did not already check; the `dotfiles-repo` converge section sets `core.hooksPath` and `rerere.enabled` in this checkout.
- Our config excludes scripts from ordinary diffs and verbose dry-run output. Inspect `chezmoi diff --include scripts --exclude encrypted` separately from file previews. Excluding encrypted entries does not hide secrets in templates; scope secret-bearing previews further.
- Test rendered syntax, host branches, and settings merges before landing (`bin/check`, plus targeted tests for new behavior). A landing applies everything; when provisioning must converge, that is the full apply that runs both scripts. Verify with `chezmoi verify --exclude scripts <target>...`, inspect residual `chezmoi status`, and test the affected program. Both scripts always remain pending `R`.
- Never use blanket `add`/`re-add`, `--force`, `destroy`, `state reset`, or `purge`. Approved repo-wins may use **scoped** `apply --force <target>` after review. Host-wins means curating source or an allowed local override; do not capture partial-ownership settings with `re-add`.
- Commit only this change's files using a conventional commit. Landing (merge, push, apply, NUC sync) needs authorization like any push; `bin/land` then performs **Machine synchronization** below. Unpushed source cannot reach another host through `update`.

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
| CodexBar config and `com.steipete.codexbar` preferences (Macs) | `.chezmoidata/codexbar.json`: explicit non-secret preferences, five provider entries and layout rules win; credentials and unrelated state survive through `lib/codexbar_settings.py`, not a `modify_*` target |

- Managed JSON files are inputs, excluded from deployment. Hooks merge managed-first per event, preserving unrelated live hooks; hooks of retired tools (`DENY` in `lib/agent_settings.py`: Superset, moshi-hook, Orca, tmux-agents) are purged. Hook deduplication uses command/script identity, not arbitrary deep equality. Some fields replace wholesale; inspect the implementation rather than assuming every list merges.
- Never enable a component's original npm or Git package alongside its suite copy. Tests for the settings merge and managed configuration: `(cd home && python3 -B -m unittest lib/test_agent_settings.py)`.
- Deleting a managed key/hook does **not** necessarily delete its live value: it can survive as unmanaged state. MCP removal likewise needs explicit cleanup. Test intended deletions and absent/valid/malformed input cases; do not flatten live state into a tracked whole-file replacement.
- Marker-scoped MCP entries produce project overrides and Codex trust entries for immediate repos under `~/Projects`, not their worktrees. A full apply can therefore change files outside this repo. See `docs/agents.md`.
- CodexBar settings converge on Macs only. Edit `.chezmoidata/codexbar.json`, never capture its live config or preferences plist: those hold credentials and runtime state. The helper preserves provider order, unlisted providers/fields, account tokens and manual cookies, and merges managed layouts across existing compatibility generations. A running app is gracefully restarted only on real managed drift; an initially stopped app stays stopped. Sign-ins, Keychain access, credential files, iCloud/device state and startup registration stay machine-local. Read-only check from the checkout root: `python3 -B home/lib/codexbar_settings.py --settings home/.chezmoidata/codexbar.json --check` (0 converged, 1 drift, 2 error). Tests: `(cd home && python3 -B -m unittest lib/test_codexbar_settings.py)`.

## Project policy ownership

- Project permissions and directory grants are Git-owned by each repository: `.pi/tool-gate.json`, `.claude/settings.json`, `.codex/config.toml` and `.opencode/opencode.jsonc`. Chezmoi owns only generic global defaults, never a project grant inventory or ongoing project-policy writers. Marker-scoped MCP overrides remain separate.
- Pi shared policy follows the active checkout root; `.pi/tool-gate.local.json` follows the main checkout and stays ignored, as do Claude local settings. Managed globals select shared saves and prohibit user-scope mutation; edit source for global changes. Explicitly approved local-only repository exceptions remain excluded, never committed by dotfiles.
- Pi boundaries apply on every host; native sandbox host selection remains unchanged. Codex defines an inheritable `self` profile everywhere without enabling new defaults outside native-policy hosts. Native path syntax and literal sibling lists are owned by project files; see `docs/agents.md`.
- Retirement verifies each machine's tracked replacements before deleting covered generated policy or duplicate local grants. Missing/unpublished replacements, malformed files and unmatched approvals remain intact. Never modify tracked Codex/OpenCode policy or use broad `.chezmoiremove` entries to migrate ownership. An excluded local replacement does not qualify for generic legacy cleanup.

## Provisioning and dependencies

Provisioning is exactly two scripts, both run on every apply, each rendered per host:

| Script | Job |
|---|---|
| `.chezmoiscripts/run_before_bootstrap.sh.tmpl` | Before any file is written: Mac Xcode CLT and Homebrew; Linux NodeSource (NUC) and the apt list (sudo only when something is missing) |
| `.chezmoiscripts/run_after_converge.sh.tmpl` | After the files: one section per concern from `.chezmoitemplates/converge/`, in order: `retired`, `brew-bundle` / `linux-tools`, `uv-tools`, `login-shell`, `pi-packages`, `herdr-plugins`, `herdr-hooks`, `herdr-status`, `aac-touchid`, `herdr-menu`, `paseo`, `omnigent-host`, `macos-defaults`, `codexbar`, `lid-sleep-sudoers`, `project-mcp`, `dotfiles-repo`. Each section gates itself by host |

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
- Maintained plugins are developed under `~/Projects`, never in installed copies. Follow `docs/plugins.md` for native local testing and publication. Publish first, then edit the pins: Pi specs in `private_dot_pi/private_agent/settings.managed.json` (release tags, each with its commit in `.chezmoidata/pi_tag_commits.json`), Herdr refs in `.chezmoidata/herdr_plugins.json`, chezmoi external URLs and checksums in `.chezmoiexternal.toml.tmpl`; the converge script installs them. There is no custom plugin manager.
- Global third-party skills are pinned, checksummed archives in `.chezmoiexternal.toml.tmpl`; personal global skills live under `dot_agents/skills`. The reusable chezmoi skill is installed project-locally in `.agents/skills`, with a Claude bridge under `.claude/skills`; its local installation does not make its content project policy.
- Release cooldown (`docs/cooldown.md`): each package manager holds releases younger than seven days in its own config (`~/.npmrc`, pnpm `config.yaml`, `~/.yarnrc.yml`, `~/.bunfig.toml`, uv `uv.toml`, pip on the Macs), rendered from `.chezmoidata/cooldown.json`. `cooldownExempt` holds the standing exemptions (Pi, herdr via `"cooldown": false`, marimo and my own packages). `cooldownAllow` holds exact `pkg@version` npm-registry releases let through early, read natively by pnpm, yarn and bun and by pi's `npm-cooldown`; entries go inert once the release is a week old. A uv tool takes a per-package cutoff that the `uv-tools` section drops after seven days. Overrides are only for a release I asked for; never disable the cooldown (`--min-release-age=0`, broad excludes, `exclude-newer = false`).
- `.chezmoiexternal.toml` uses pinned URLs plus checksums; update both together. Review archive paths/strip counts and deletion effects of `exact = true`. Do not edit installed external contents; consumers of newly installed externals belong in a converge section.

## Secrets and boundaries

Age encryption is configured in `.chezmoi.toml.tmpl`; identity `~/.config/chezmoi/key.txt` stays untracked. Secret source is `dot_config/private_dotfiles/encrypted_private_secrets.env.age`, deployed only on eligible hosts with the key. Edit via `chezmoi edit ~/.config/dotfiles/secrets.env`, not by writing plaintext into Git.

Encryption protects source, not deployed plaintext. Render/diff/debug/archive output can expose secrets; avoid printing them. Harness authentication is machine-local and interactive, never committed. AgentBox Git operations go through its hub; do not add credentials inside a box.

## Machine synchronization

Use after a dotfiles commit, push, or apply. Local apply only changes this machine; NUC `update` pulls published source and then applies it. Never imply an unpushed local edit reached another host.

### Sequence

When landing is authorized, commit only this logical change in its worktree and run, from that worktree:

```sh
bin/land            # or: bin/land <branch> from elsewhere; add --remove from outside the worktree
```

It performs, in order: lock, fast-forward `main` to `origin/main`, rebase, `bin/check`, fast-forward `main`, `git push origin main`, `chezmoi init` (only when `.chezmoi.toml.tmpl` changed) and `chezmoi apply`, `chezmoi verify --exclude scripts`, then `ssh spencer@nuc '~/.local/bin/chezmoi update --no-tty'` (plus `init` and `apply` there when the config template changed) and a check that the NUC's checkout is at the pushed commit. It stops at the first failure and says what is done and what is not; a failure after the push means published but not fully deployed, so finish the remaining steps by hand rather than landing again. `--no-apply` and `--no-sync` skip those steps (report them as pending). Never push from another host: `bin/land` refuses to run on the NUC and in boxes. Do not hide an error behind a pipe or continue after a failed push/apply; never push an unrelated main branch.

Verify the commit on both hosts with `git -C ~/Projects/dotfiles log -1 --oneline`. Check `chezmoi verify --exclude scripts` (or scoped changed targets), inspect residual `chezmoi status`, and check actual deployed files/programs. Classify drift rather than treating any nonzero exit as success.

- **NUC:** Debian, host `nuc`, using `~/.local/bin/chezmoi`; its herdr server is the default session, the only one. A Mac Brewfile change is not a NUC installation; the NUC follows `.chezmoidata/linux.json`. An apt-list change needs sudo, so `update --no-tty` stops at the bootstrap script: rerun `chezmoi apply` in an interactive ssh session.
- **Other Mac (`mac-pro` or `mac-air`):** out of reach from here and never remote-managed. It picks up whatever is pushed at its next `chezmoi update`, so do not list it as pending, remind me to update it, or end with a step for it. Mention it only when that update alone will not work there (a manual step or a known failure on that host).
- **AgentBox boxes (`agentbox-box`):** not synced remotely; each reapplies `origin/main` on startup through its repository's `agentbox.yaml` task. See `docs/agentbox.md`.

### Conflicts and failures

`chezmoi update` normally runs `git pull --autostash --rebase` then apply; the apply guard refuses before the pull when that host's checkout is off `main` or has changes under `home/` (inspect them there; never discard them blindly). An unavailable host, failed pull, script error, or unresolved drift means synchronization is incomplete.

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
