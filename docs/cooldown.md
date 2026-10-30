# Release cooldown

New releases wait seven days before anything installs them. The point is background and
transitive updates: a compromised or broken release is usually caught and yanked inside that
window. It is not meant to block a release I ask for by name.

Each tool enforces it through its own configuration; no agent tracks release dates.
Overrides name one exact release, only one I asked for.

## Settings

This repository holds the user-level half, which covers what is installed on my machines:

| Tool | Setting | Source |
| --- | --- | --- |
| npm | `min-release-age=7`; `min-release-age-exclude[]` takes names only | `home/dot_npmrc.tmpl` |
| pnpm | `minimumReleaseAge: 10080` (minutes), strict, `minimumReleaseAgeIgnoreMissingTime: false`; `minimumReleaseAgeExclude` takes names, globs and `pkg@version` | `home/.chezmoitemplates/pnpm-config.yaml` (`~/.config/pnpm/config.yaml`, `~/Library/Preferences/pnpm/config.yaml` on macOS) |
| yarn | `npmMinimalAgeGate: 10080` (minutes) and `npmPreapprovedPackages` | `home/dot_yarnrc.yml.tmpl` (`~/.yarnrc.yml`, the home config; a project's own `.yarnrc.yml` overrides it, uplft sets 0) |
| bun | `minimumReleaseAge = 604800` (seconds) and `minimumReleaseAgeExcludes`; also covers OpenCode's plugin installs, which run through its bundled bun | `home/dot_bunfig.toml.tmpl` (`~/.bunfig.toml`) |
| uv | `exclude-newer = "7 days"` | `home/dot_config/uv/uv.toml` |
| pip (Macs) | `uploaded-prior-to = P7D` | `home/dot_config/pip/pip.conf` |
| pi | `npm-cooldown`, a wrapper around npm, because `npm view` ignores the cooldown | `home/dot_local/bin/executable_npm-cooldown` |
| Linux release binaries | `pin` picks the newest release past the cooldown | `home/lib/linux_releases.py` |
| chezmoi externals | pinned URL and checksum, chosen past the cooldown | `home/.chezmoiexternal.toml.tmpl` |

Not covered: Homebrew (no setting; it reviews and delays risky ecosystems itself), cargo (only
the unstable `min-publish-age`), deno (only the unstable `--min-dep-age`, no global config)
and gem. Its `npm` and `uv` Brewfile entries go through npm and uv and so follow the settings
above.

CI runners and Docker builds never see `$HOME`, so each project repository carries its own
half: `[tool.uv] exclude-newer` in `pyproject.toml` (with `uv sync --locked`, which checks
the lockfile against it; `--frozen` checks nothing), `minimumReleaseAge` in
`pnpm-workspace.yaml`, and an updater (Renovate) with a matching minimum release age for
Docker images, GitHub Actions and pinned URLs.

## Standing exemptions

Hand-maintained in `home/.chezmoidata/cooldown.json` (`cooldownExempt`):

- npm: Pi (`@earendil-works/*`; Homebrew on Macs). The list renders the `.npmrc` excludes and
  the pnpm config, and also the yarn and bun configs (bun takes exact names only, so globs
  are skipped there).
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

## Letting one release through early

Only for a release I asked for. Its dependencies and the package's later releases keep the
cooldown, with nothing to expire or clean up except where noted.

On my machines:

| What | How |
| --- | --- |
| Any npm-registry package installed by pnpm, yarn, bun or pi | Add `"<pkg>@<version>"` to `cooldownAllow` in `home/.chezmoidata/cooldown.json`, apply, and install as usual (`pnpm add -g <pkg>@<version>`, `pi update npm:<pkg>`). Commit it with the change. Entries go inert once the release is a week old; deleting one later changes nothing. |
| Plain npm | `npm install -g --min-release-age-exclude=<pkg> <pkg>@<version>` |
| uv tool | ``uv tool install <pkg>==<version> --exclude-newer-package "<pkg>=$(date -u +%Y-%m-%dT%H:%M:%SZ)"``. The receipt keeps the cutoff, and converge `uv-tools` drops it and the pin after seven days. |
| uvx or `uv run --with` | `--exclude-newer-package <pkg>=false` for that command |
| pip | No per-package override; use uv. |
| Linux release binary | `python3 home/lib/linux_releases.py pin --tag <tag> <name>` |
| chezmoi external | Pin the tag or commit and its checksum. |

In a project repository:

| Tool | How |
| --- | --- |
| pnpm | `minimumReleaseAgeExclude: [<pkg>@<version>]` in `pnpm-workspace.yaml`, plus `minimumReleaseAgeExcludePrune: true`, which drops it once the lockfile stops using it |
| yarn | `npmPreapprovedPackages` in `.yarnrc.yml` |
| bun | `minimumReleaseAgeExcludes` in `bunfig.toml` |
| uv | `[tool.uv.exclude-newer-package] <pkg> = "<UTC now>"`. uv has no exact-version exemption (astral-sh/uv#19864 and #18792, open as of 2026-10-30), so the line freezes that package: any such timestamp older than seven days is stale, and should be deleted when touching dependencies. |
| Renovate | The Dependency Dashboard's "Pending Status Checks" |

A host installs an early release only where it is run. Provisioning is install-only, and
another host's next install picks the newest release past the cooldown.

## Debugging

- `npm view`, `pnpm view` and PyPI show releases the cooldown hides; `npm view <pkg> time --json`
  dates them.
- A "no matching version" or "no version satisfies" error from npm, pnpm, yarn or bun, or
  uv's "excluded by exclude-newer" hint, means nothing in the requested range is a week old
  yet.
- `pnpm config get minimumReleaseAgeExclude`, `yarn config get npmPreapprovedPackages` and
  `pip3 config list` show the effective settings.
