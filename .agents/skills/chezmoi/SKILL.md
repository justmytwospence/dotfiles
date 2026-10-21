---
name: chezmoi
description: "Manage dotfiles with chezmoi: source and target state, file attributes, templates, host data, modify scripts, provisioning, externals, encryption, and safe add/apply/update workflows. Use when working with chezmoi or a chezmoi-managed dotfiles repository."
---

# Chezmoi

General-purpose chezmoi guidance. Repository-specific paths, host policies, ownership rules, and publishing/synchronization procedures belong in that repository's `AGENTS.md`, not in this skill. Read applicable project instructions first; do not assume a source directory, destination, host schema, package manager, encryption backend, or Git workflow.

Consult the installed version's help for unfamiliar commands and the upstream references below before introducing an unfamiliar feature.

## Locate ownership

- Distinguish **source state** (managed inputs), **destination state** (files currently on disk), and **target state** (desired result computed from source and configuration).
- Use `chezmoi source-path` to locate the configured source directory and `chezmoi source-path <target>` to find a target's source. Check Git status there before editing; preserve unrelated source and destination changes.
- Edit source inputs rather than deployed copies. `chezmoi edit <target>` edits the corresponding source; templates and modify scripts require understanding their inputs first.
- A `.chezmoiroot` file at the repository root makes a subdirectory the source: `chezmoi source-path`, `.chezmoi.sourceDir` and `$CHEZMOI_SOURCE_DIR` then point to that subdirectory, and `.chezmoi.workingTree` to the repository. chezmoi reads every `.chezmoidata` and `.chezmoi*` file anywhere under the source, so worktrees, nested checkouts and other copies of the repository must live outside it, or their data silently overrides the real data.
- When using an alternate checkout, pass `chezmoi --source <checkout> ...` explicitly. Ordinary commands otherwise use the configured source, not necessarily the current working directory.
- Read `.chezmoiignore`, configuration, scripts, and relevant runbooks to establish ownership and side effects before applying anything.

## Source attributes

- `dot_` means a leading dot; `.tmpl` means a Go template. For example, `dot_zshrc.tmpl` renders to `.zshrc` in the destination directory.
- `private_` restricts permissions, not encryption; `executable_` sets executable bits; `encrypted_` stores encrypted source. Preserve attribute ordering; check the [naming reference](https://www.chezmoi.io/reference/source-state-attributes/) for combinations.
- `symlink_` sources are regular text files containing link destinations. Ordinary Git symlinks used for repository metadata are different.
- Empty rendered files are removed unless `empty_`; empty symlink destinations remove links. `create_` initializes only missing files. Review deletion effects before using `exact_`, `remove_`, or exact archives.
- Dot-prefixed source metadata is automatically ignored except `.chezmoi*`. Other repository-only paths belong in `.chezmoiignore`, which matches **target paths**, not source names. `.gitignore` only controls Git.
- Removing or ignoring a source entry does not uninstall its deployed target. Plan any intended cleanup explicitly.

## Safe change workflow

1. Identify ownership and read the source and any transformations, templates, scripts, or external dependencies involved.
2. Edit the smallest managed input. For a new existing file, use scoped `chezmoi add <target>`, then inspect the generated name/content. Review `--autotemplate` substitutions rather than accepting them blindly.
3. Render and preview only the affected targets:

   ```sh
   chezmoi cat <target>             # rendered contents; avoid secret-bearing targets
   chezmoi diff <target>
   chezmoi apply --dry-run --verbose <target>
   ```

   Inspect configured include/exclude filters: scripts may be hidden from ordinary diff or dry-run output. To review script changes explicitly, use `chezmoi diff --include scripts --exclude encrypted`. Excluding encrypted entries avoids their decrypted diffs, **not all possible secrets**; templates can also contain secrets.

   Dry-run skips run-script execution, but rendering can execute modify transformations and template commands, hooks, or downloads. It is not a sandbox.
4. Check rendered syntax and application behavior. Test transformations on fixtures, not production files. Use `chezmoi execute-template --file <source>` for templates and representative configuration data for host branches.
5. Apply reviewed targets with `chezmoi apply <target>...`. A full apply can run provisioning and other side effects; inspect them first. Verify with `chezmoi verify --exclude scripts <target>...`, inspect remaining `chezmoi status`, and test the affected program.
6. Commit/publish only when authorized, following project policy. Local apply does not publish source or synchronize other machines. `chezmoi update` pulls source and applies on the machine where it runs; remote access and propagation policy are project-specific.

Avoid blanket `add`/`re-add`, force operations, `destroy`, and persistent-state resets without explicit scope and authorization. `chezmoi purge` deletes the source directory as well as chezmoi's configuration; it is not an ordinary cleanup command.

## Drift and conflicts

- `chezmoi status` column 1 is destination drift since the last write; column 2 is what apply will change. `doctor` diagnoses chezmoi setup, not target correctness or successful provisioning.
- Always-run scripts can appear as pending `R` and make unfiltered verification fail even when files match. Classify remaining changes rather than treating a nonzero exit as success.
- If apply reports changed destination contents, inspect `chezmoi diff <target>` and resolve ownership before forcing. Approved source-wins permits scoped `apply --force <target>`; destination-wins means curating source or a supported local override.
- Scoped `re-add <target>` captures regular-file drift but skips templates. Do not use it to capture partial-ownership settings or accidentally track application state.
- Preserve local Git work when updating. If a pull/rebase conflicts, inspect and report the conflict; do not discard another machine's changes to make synchronization succeed.

## Templates and machine data

- `.chezmoi.toml.tmpl` generates chezmoi configuration during init. `prompt*Once` answers can populate `[data]`; ordinary apply does not regenerate that config. After the template changes, chezmoi warns until `chezmoi init` regenerates it (stored answers are reused). With `.chezmoiroot`, record `.chezmoi.workingTree`, not `.chezmoi.sourceDir`, as `sourceDir`.
- `chezmoi update` resolves the source before it pulls: a pull that adds or moves `.chezmoiroot` takes effect on the next run, and that one apply can fail on paths that moved.
- Use the repository's actual custom data schema for host branches. Use `.chezmoi.homeDir` and other system data for portable paths; avoid hardcoded usernames, unstable environment dependencies, and nondeterministic output.
- Shared snippets live in `.chezmoitemplates/`; pass context with `{{ template "name" . }}`. `include` reads literal source; `includeTemplate` renders source.
- Preserve newlines when trimming whitespace; scripts need the shebang at byte zero. Quote or serialize values for the destination format.
- Local overrides and precedence depend on the consuming program and repository. Inspect include/source order rather than assuming a local file always wins.

## Partial ownership and modify scripts

`modify_*` scripts read the current file from stdin and emit the **complete** result on stdout, including when stdin is empty. Keep transformations deterministic, idempotent, and side-effect-free; diagnostics go to stderr.

- Locate the managed inputs and merge implementation before changing program-rewritten settings. Ownership, list deduplication, and precedence are repository-specific.
- Preserve unmanaged state; do not flatten the live file into a tracked whole-file replacement.
- Deleting a managed key may leave its live value behind as unmanaged state. Test intended removals explicitly.
- Test absent, valid, malformed, and repeated inputs; check idempotence and preservation of unrelated values.

## Scripts and externals

- Target computation precedes execution: before scripts → targets (alphabetical, parents first) → after scripts. Do not rely on before scripts to provide already-rendered inputs or mutate managed source/destination files during execution.
- `run_` runs every applicable apply. `run_once_` remembers successful **rendered content hashes**, regardless of filename—not “once forever.” `run_onchange_` remembers the last successful contents per filename. Changes can rerun provisioning; failures normally retry.
- Hash-triggered scripts never notice drift: a deleted plugin or a reset setting stays wrong until the script's text changes. Where drift matters, prefer an always-run script whose steps check the actual state first and act only on a difference; keep those checks cheap and gate disruptive actions (restarts, password prompts) on a real difference.
- macOS runs `#!/bin/bash` as bash 3.2: under `set -u` an empty array is unset, so expand possibly empty arrays as `${a[@]+"${a[@]}"}`. Test scripts with the bash the host will use.
- Keep scripts idempotent and ordered; do not assume cwd is the source directory. Include dependency hashes in onchange script content when dependent inputs should trigger a rerun; use rendered hashes for host-dependent inputs.
- Verify actual installer/service state: an installer may swallow errors, and a successful recorded script may not retry. Diagnose or rerun the specific operation rather than resetting all persistent state.
- Package installation, upgrades, removal, release cooldowns, and maintained-plugin publication are project policy. Do not infer them from chezmoi itself.
- `.chezmoiexternal.toml` is templated even without `.tmpl`. Prefer pinned URLs with checksums; update both together. Review archive paths and strip counts; `exact = true` deletes extra entries. Edit external declarations rather than installed contents; consumers of newly installed externals belong in after scripts.

## Secrets

- Inspect the repository's encryption/password-manager configuration before editing secrets. Keep keys and credentials out of tracked plaintext; use `chezmoi edit <secret-target>` for encrypted sources when configured.
- Encryption protects source, not deployed plaintext. Render, diff, debug, archive, and command output can expose secrets; scope previews carefully and avoid printing them.
- `private_` is only a permission attribute. Never treat it as encryption or as a reason credentials are safe to commit.

## Upstream references

- [Command overview](https://www.chezmoi.io/user-guide/command-overview/) and [reference](https://www.chezmoi.io/reference/)
- [Source-state attributes](https://www.chezmoi.io/reference/source-state-attributes/)
- [Application order](https://www.chezmoi.io/reference/application-order/)
- [Scripts](https://www.chezmoi.io/user-guide/use-scripts-to-perform-actions/)
- [Templating](https://www.chezmoi.io/user-guide/templating/)
