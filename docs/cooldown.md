# Release cooldown

New releases wait seven days before anything installs them: npm (`min-release-age=7` in
`dot_npmrc.tmpl`), uv (`exclude-newer = "7 days"` in `dot_config/uv/uv.toml`), the Linux
release binaries (`lib/linux_releases.py`) and pinned archives. The point is background and
transitive updates: a compromised or broken release is usually caught and yanked inside that
window. It is not meant to block a release I ask for by name.

Standing exemptions: Pi (`@earendil-works/*`, Homebrew on Macs), herdr (`"cooldown": false`)
and the packages I maintain (`[exclude-newer-package]` in uv.toml).

## An explicitly requested release

When I ask to install or upgrade a specific thing (by name, or a specific version of it),
that exact release goes past the cooldown without asking. Only that package, only that
release: its dependencies, other packages, and any later release still wait. Once the
release is seven days old the allowance lapses and that package's updates follow the
cooldown again.

| What | How |
| --- | --- |
| npm global or pi npm package | `cooldown-allow npm <pkg>[@<version>]` |
| uv tool | `cooldown-allow uv <pkg>[==<version>]` |
| Linux release binary | `python3 lib/linux_releases.py pin --tag <tag> <name>` |
| chezmoi external (skill, plugin archive) | pin the requested tag or commit and its checksum directly |

`cooldown-allow` (`dot_local/bin/executable_cooldown-allow`) records the exact release in
`.chezmoidata/cooldown.json` and installs it here. Without a version it takes the newest.
Add `--no-install` when something else installs it, for example a pi package whose pin
in `settings.managed.json` you bump. Commit the data file with the change that declares or
bumps the package, so every host follows:

- Macs: `20-brew-bundle` installs allowed releases of Brewfile `npm`/`uv` entries before
  `brew bundle`, which then finds them installed.
- Linux: `25-linux-tools` does the same for `.chezmoidata/linux.json`'s npm and uv lists.
- pi: `npm-cooldown` reads `~/.config/cooldown-allow.json` (rendered from the same data),
  pins a bare package name to its allowed release, and exempts only that package.

A host installs an allowed release only for packages it declares. Allowances never apply to
updates I did not ask for: dependency bumps, `npm update -g` sweeps, lockfile refreshes or
a tool an agent decides to add. `cooldown-allow prune` drops lapsed entries (it also prunes
on every add); `cooldown-allow list` shows them.

Release binaries and archives are exact pins already, so the cooldown only matters when
choosing what to pin: `pin --tag` picks the requested tag, and a later plain `pin` picks the
newest release past the cooldown again.
