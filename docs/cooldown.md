# Release cooldown

New releases wait seven days before anything installs them. The point is background and
transitive updates: a compromised or broken release is usually caught and yanked inside that
window. It is not meant to block a release I ask for by name.

The cooldown is enforced by tools, never by an agent remembering it. This repository holds
the user-level half, which covers what is installed on my machines:

| Tool | Setting | Source |
| --- | --- | --- |
| npm | `min-release-age=7` | `home/dot_npmrc.tmpl` |
| pnpm | `minimumReleaseAge: 10080` (minutes), strict, `minimumReleaseAgeIgnoreMissingTime: false` | `home/.chezmoitemplates/pnpm-config.yaml` (`~/.config/pnpm/config.yaml`, `~/Library/Preferences/pnpm/config.yaml` on macOS) |
| uv | `exclude-newer = "7 days"` | `home/dot_config/uv/uv.toml` |
| Linux release binaries | `pin` picks the newest release past the cooldown | `home/lib/linux_releases.py` |
| chezmoi externals | pinned URL and checksum, chosen past the cooldown | `home/.chezmoiexternal.toml.tmpl` |

CI runners and Docker builds never see `$HOME`, so each project repository carries its own
half: `[tool.uv] exclude-newer` in `pyproject.toml` (with `uv sync --locked`, which checks
the lockfile against it; `--frozen` checks nothing), `minimumReleaseAge` in
`pnpm-workspace.yaml`, and an updater (Renovate) with a matching minimum release age for
Docker images, GitHub Actions and pinned URLs. Homebrew has no user-side cooldown (it
reviews and delays risky ecosystems itself); its `npm` and `uv` Brewfile entries go through
npm and uv and so follow the settings above.

## Standing exemptions

Hand-maintained in `home/.chezmoidata/cooldown.json` (`cooldownExempt`):

- npm/pnpm: Pi (`@earendil-works/*`; Homebrew on Macs). Renders the `.npmrc` excludes and
  the pnpm config.
- uv: the packages I maintain, where publishing is meant to be used at once: cloudposterior,
  arviz-mcp, and marimo with marimo-lens and agent-plugins. marimo is trusted enough to take
  on release day; marimo-lens ships its agent skill inside the package, so a held-back wheel
  would disagree with the skill installed from GitHub, and agent-plugins (how Lens serves that
  skill) moves in step with it.
- herdr (`"cooldown": false` in `linux.json`).

The uv exemptions are never in the user-level `uv.toml`: uv merges user settings into every
project's `uv.lock` `[options]`, and CI (with no such file) then fails `uv sync --locked`.
Instead:

- uv tools: the converge `uv-tools` section (`home/lib/uv_tools.py`) gives every installed
  tool whose requirements name one of them `exclude-newer-package <pkg>=false` in its receipt,
  which `uv tool upgrade` reuses.
- projects: a repository that wants one of them fresh says so in its own `pyproject.toml`
  (`[tool.uv.exclude-newer-package] marimo = false`).

## An explicitly requested release

When I ask to install or upgrade a specific thing (by name, or a specific version of it),
that exact release goes past the cooldown without asking. Only that package, only that
release: its dependencies, other packages, and any later release still wait.

On my machines:

| What | How |
| --- | --- |
| npm global or pi npm package | `cooldown-allow npm <pkg>[@<version>]` |
| uv tool | `cooldown-allow uv <pkg>[==<version>]` |
| Linux release binary | `python3 home/lib/linux_releases.py pin --tag <tag> <name>` |
| chezmoi external (skill, plugin archive) | pin the requested tag or commit and its checksum directly |

In a project repository, the native setting where one exists:

| Tool | How | Scope |
| --- | --- | --- |
| pnpm | `minimumReleaseAgeExclude: [<pkg>@<version>]` in `pnpm-workspace.yaml` | that version only, for good; `minimumReleaseAgeExcludePrune: true` drops it once the lockfile no longer uses it |
| uv | `[tool.uv.exclude-newer-package] <pkg> = "<that release's upload time>"` | that release and older; a later one waits. Remove it once the release is a week old, or the package stays frozen there |
| npm | none native (excludes are names only) | use pnpm |
| Renovate | request the update from the Dependency Dashboard's "Pending Status Checks" | that one update |

`cooldown-allow` (`home/dot_local/bin/executable_cooldown-allow`) records the exact release in
`home/.chezmoidata/cooldown.json` and installs it here. Without a version it takes the newest.
Add `--no-install` when something else installs it, for example a pi package whose pin
in `settings.managed.json` you bump. Commit the data file with the change that declares or
bumps the package, so every host follows:

- Macs: the converge script's `brew-bundle` section installs allowed releases of Brewfile `npm`/`uv` entries before
  `brew bundle`, which then finds them installed.
- Linux: its `linux-tools` section does the same for `home/.chezmoidata/linux.json`'s npm and uv lists.
- pi: `npm-cooldown` reads `~/.config/cooldown-allow.json` (rendered from the same data),
  pins a bare package name to its allowed release, and exempts only that package.

npm can only exempt a package by name, so an allowed npm release is installed with the name
exempted for that one command and the exact version pinned. A uv allowance exempts the
package up to its release's own upload time (`cutoff`, rounded up to the next second), so a
release published after it still waits.

A host installs an allowed release only for packages it declares. Allowances never apply to
updates I did not ask for: dependency bumps, `npm update -g` sweeps, lockfile refreshes or
a tool an agent decides to add. `cooldown-allow prune` drops lapsed entries (it also prunes
on every add); `cooldown-allow list` shows them.

Once the release is seven days old the allowance lapses and that package's updates follow
the cooldown again. uv keeps a tool's exact pin and cutoff in its receipt, so the converge
`uv-tools` section reinstalls a declared tool unpinned once its allowance has lapsed.

Release binaries and archives are exact pins already, so the cooldown only matters when
choosing what to pin: `pin --tag` picks the requested tag, and a later plain `pin` picks the
newest release past the cooldown again.
