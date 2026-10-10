---
name: chezmoi
description: "Manage this dotfiles project's chezmoi source, templates, host differences, settings merges, setup scripts, secrets, dependencies, and machine synchronization. Load before any dotfiles change or chezmoi add/apply/update/commit/push, including changes made from another repository."
---

# Chezmoi for this project

This is project policy, not a general-purpose installer. Reviewed against chezmoi v2.73.0's complete user guide, reference, and developer guide, and this repo's implementation. Consult the installed version's help for unfamiliar commands. Repo paths below are relative to the checkout root; linked references are relative to this skill.

## Ownership and paths

- Source state is this Git checkout; configured source is normally `~/dotfiles`. Destination is `$HOME`; target state is the desired result computed from source, machine config, and existing files. Targets are real files unless explicitly declared symlinks; this is no longer GNU Stow.
- Check `git status --short` and `chezmoi source-path <target>` before editing. Edit source, never deployed copies. In a worktree, use `chezmoi --source <checkout>` explicitly; normal apply still reads the configured checkout. Do not create a worktree unless requested.
- `dot_` means a leading dot; `.tmpl` means Go template. Thus `dot_Brewfile.tmpl` renders to `~/.Brewfile`. `private_` restricts permissions, not encryption; `executable_` sets executable bits; `encrypted_` stores encrypted source.
- `symlink_` sources are regular text files containing link destinations. Project metadata symlinks are ordinary Git symlinks, not chezmoi targets. Preserve attribute ordering; use [the naming reference](https://www.chezmoi.io/reference/source-state-attributes/) for unfamiliar combinations.
- Empty rendered files are removed unless `empty_`; empty symlink destinations remove links. `create_` initializes only missing files. Avoid `exact_`, `remove_`, or exact archives without reviewing what they delete.
- Dot-prefixed repo metadata (`.agents`, `.claude`, `.git`) is automatically ignored except `.chezmoi*`. Other repo-only paths belong in `.chezmoiignore`, which matches **target paths**, not source names. `.gitignore` only controls Git.
- Do not use blanket `add`, `re-add`, `--force`, `destroy`, or `state reset`. Never `chezmoi purge`: it deletes the source repo. Removing or ignoring a source does not uninstall its deployed target.

## Change workflow

1. Identify ownership and read the relevant source, script, and runbook. Preserve unrelated Git and live-state changes.
2. Edit the smallest source input. To manage a new existing file, use scoped `chezmoi add <target>`, then inspect its generated name/content. For templates, review any `--autotemplate` substitutions.
3. Render and preview before deployment:

   ```sh
   chezmoi cat <target>                        # rendered target; avoid secrets
   chezmoi diff <target>
   chezmoi diff --include scripts --exclude encrypted  # override hidden-script filter
   chezmoi apply --dry-run --verbose --exclude encrypted # nonencrypted target preview
   ```

   Our config excludes scripts from ordinary diffs and verbose dry-run output; the explicit **script diff** above overrides that filter. Inspect it separately: dry-run output alone is not a full provisioning preview. Excluding encrypted entries avoids their decrypted diffs, **not all possible secrets**: scope previews further for secret-bearing templates. Dry-run skips run-script execution, but rendering still executes modify transformations and may run template commands, hooks, or downloads: it is not a sandbox.
4. Check rendered syntax and application behavior. Test merges on fixtures, not production files; test templates with `chezmoi execute-template --file <source>`. Changes to host branches need representative host renders.
5. Apply reviewed targets with `chezmoi apply <target>...`; use full `chezmoi apply` when setup/sync scripts must run. Verify with `chezmoi verify --exclude scripts <target>...`, inspect remaining `chezmoi status`, and test the affected program. Always-run scripts appear as pending `R` and can make unfiltered verification fail even when files match.
6. Commit only this change's files using a conventional commit when authorized. After commit/push/apply, follow [machine synchronization](references/sync.md); an unpushed change cannot reach another host through `update`.

`chezmoi status` column 1 is destination drift since the last write; column 2 is what apply will change. `doctor` diagnoses chezmoi setup, not target correctness or successful provisioning.

If apply reports a changed target, inspect `chezmoi diff <target>` and resolve ownership before forcing anything. Repo-wins permits a **scoped** `apply --force <target>` after review. Host-wins means curate the source or an allowed local override. `re-add <target>` captures regular-file drift but skips templates; do not use it to capture partial-ownership settings.

## Hosts and templates

`.chezmoi.toml.tmpl` generates `~/.config/chezmoi/chezmoi.toml` during init. Its `prompt*Once` answers become `[data]`; ordinary apply does not regenerate that config.

| Host | Policy |
|---|---|
| `mac-pro` | Desk Mac, role `pro`: full Brewfile and local-model services |
| `mac-air` | Travel Mac, role `air`: lighter Brewfile |
| `nuc` | Debian hub: no automatic system-wide provisioning |
| `agentbox-box` | Box bootstrap; no herdr, follows `docs/agentbox.md` |

`.extras` is a comma-separated list: `emacs`, `jupyter`, `linux-desktop`. Change machine-local answers in config, or deliberately regenerate with `init`; do not encode one machine's choices in shared source. Current hosts are defined by the config template, not the historical migration runbook.

- Branch on `.host`, `.role`, `.extras`; use `.chezmoi.homeDir` and other system data for portable paths. Avoid hardcoded usernames, unstable environment dependencies, and nondeterministic output.
- Shared snippets live in `.chezmoitemplates/`; pass context with `{{ template "name" . }}`. `include` reads literal source; `includeTemplate` renders source.
- Preserve newlines when using whitespace trimming; scripts need the shebang at byte zero. Quote/serialize for the destination format.
- Local overrides are `~/.zshenv.local`, `~/.zshrc.local`, `~/.gitconfig.local`, untracked. Shell overrides load last; Git's local include currently precedes managed identity keys, so it cannot override those keys. Check include order before relying on precedence.

## Settings programs rewrite

`modify_*` scripts read the current file from stdin and emit the **complete** result on stdout, including when stdin is empty. Keep transformations deterministic, idempotent, and side-effect-free; diagnostics go to stderr. Wrappers import `lib/agent_settings.py` through the source path. Edit managed inputs unless changing merge behavior.

| Target | Source and ownership |
|---|---|
| `~/.claude/settings.json` | `dot_claude/settings.managed.json`: managed keys win; hooks merge |
| `~/.codex/hooks.json` | `dot_codex/hooks.managed.json`: managed keys win; hooks merge |
| `~/.pi/agent/settings.json` | `private_dot_pi/private_agent/settings.managed.json`: managed keys win; additional local-path packages survive |
| `~/.pi/agent/pi-plan-mode.json` | Neighboring `pi-plan-mode.managed.json`: **live settings win**; defaults fill missing keys |
| `~/.config/ttt/settings.json` | `dot_config/ttt/settings.managed.json`: recursive managed-wins merge |
| `~/.claude.json`, `~/.codex/config.toml` | `dot_config/mcp/mcp.json`, plus explicit pins in the merge library; unrelated application state survives |

Managed JSON files are inputs, excluded from deployment. Hooks merge managed-first per event, preserving unrelated live hooks; retired Superset/moshi hooks are purged. Hook deduplication uses command/script identity, not arbitrary deep equality. Some fields replace wholesale; inspect the implementation rather than assuming every list merges.

Deleting a managed key or hook does **not** necessarily delete its live value: it can survive as unmanaged state. MCP removal likewise needs explicit cleanup. Test intended deletions and absent/valid/malformed input cases; do not flatten live state into a tracked whole-file replacement.

Marker-scoped MCP entries produce project overrides and Codex trust entries for immediate repos under `~/Projects`, not their worktrees. A full apply can therefore change files outside this repo. See `docs/agents.md`.

## Scripts and dependencies

Target computation precedes execution: before scripts → targets (alphabetical, parents first) → after scripts. Do not rely on before scripts to provide already-rendered inputs or modify managed source/destination files during execution.

| Script | Trigger/purpose |
|---|---|
| `10-packages` | Before, once: bootstrap prerequisites |
| `20-brew-bundle` | On rendered Brewfile change, Macs only: install with `--no-upgrade` |
| `30-shell`, `50-agents`, `60-phone`, `70-macos-defaults`, `80-host` | Once: host/runtime/integration setup |
| `40-plugins`, `41-skills` | On dependency change: sync plugin pins and global skill sources |
| `45-worktree-links`, `46-project-mcp` | Every apply: links and project MCP overrides |
| `85-retired` | On script change: remove retired installs/state |

- `run_` runs every applicable apply. `run_once_` remembers successful **rendered content hashes**, regardless of filename—not “once forever.” `run_onchange_` remembers the last successful contents per filename. Changes can rerun provisioning; failures normally retry.
- Keep scripts idempotent and ordered. Hash dependencies into onchange comments (rendered hash for host-dependent input); reuse `script-path.sh`. Do not assume cwd is the source repo.
- Several installers swallow failures: exit 0 does not prove success, and unchanged scripts may not retry. Verify plugin/skill/service state and retry the actual installer if needed. Never reset all persistent state merely to rerun one script.
- Macs declare formula/cask/npm/uv dependencies in `dot_Brewfile.tmpl`, with desk-only dependencies in its role branch. Install does not upgrade or uninstall. Preview `brew bundle cleanup --global` before any authorized `--force` cleanup; retiring deployed tools may also need `85-retired`.
- Maintained plugins live in their own `~/Projects/<name>` repos, never installed copies. Publish first, then bump pins; follow `docs/plugins.md`. `plugins pin` edits and applies the configured source, not necessarily your current checkout; use it only from the main-checkout publication workflow. Global skills use `dot_local/bin/executable_skills-install`; personal global skills live under `dot_agents/skills`. This skill stays project-local in `.agents/skills`, with a Claude bridge under `.claude/skills`.
- npm and uv hold back new releases seven days, with configured exceptions. Do not bypass the cooldown without permission.
- `.chezmoiexternal.toml` is templated even without `.tmpl`. Externals are pinned URLs plus checksums; update both together. Archive paths/strip counts need review; `exact = true` deletes extra entries. Do not edit installed external contents; consumers of newly installed externals belong in after scripts.

## Secrets and boundaries

Age encryption is configured in `.chezmoi.toml.tmpl`; identity `~/.config/chezmoi/key.txt` stays untracked. Secret source is `dot_config/private_dotfiles/encrypted_private_secrets.env.age`, deployed only on eligible hosts with the key. Edit via `chezmoi edit ~/.config/dotfiles/secrets.env`, not by writing plaintext into Git.

Encryption protects source, not deployed plaintext. Render/diff/debug/archive output can expose secrets; avoid printing them. Harness authentication is machine-local and interactive, never committed. AgentBox Git operations go through its hub; do not add credentials inside a box.

## References

- [Sync and conflict handling](references/sync.md): local apply, NUC propagation, other Macs, reloads, failures.
- `README.md`: human setup/layout guide; `docs/agents.md`: harness ownership; `docs/plugins.md`: plugin lifecycle; `docs/agentbox.md`: box bootstrap; `docs/migration.md`: historical Stow migration.
- Upstream: [user guide](https://www.chezmoi.io/user-guide/command-overview/), [reference](https://www.chezmoi.io/reference/), [application order](https://www.chezmoi.io/reference/application-order/), [scripts](https://www.chezmoi.io/user-guide/use-scripts-to-perform-actions/), [templating](https://www.chezmoi.io/user-guide/templating/). Review the relevant page before introducing a feature not covered here.
