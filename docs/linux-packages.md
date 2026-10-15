# Linux packages

The Linux counterpart of `dot_Brewfile.tmpl` for `nuc` and `agentbox-box`. One file,
`.chezmoidata/linux.json`, declares everything a Linux host's dev environment needs; the
NUC's server stack (Docker, networking, services) stays in `~/Projects/homelab`.

| Section | Installed by | When |
|---|---|---|
| `apt.common`, `apt.<host>` | `run_onchange_before_10-packages` (sudo) | the host's rendered list changes |
| `node_major` | same script: the NodeSource repository, NUC only | the major changes |
| `releases` | `.chezmoiexternal.toml.tmpl`: pinned, checksummed externals in `~/.local/bin` | every apply (a no-op when the file matches) |
| `uv`, `npm`, `installers` | `run_onchange_after_25-linux-tools` | the host's lists change |

Everything is install-only, like `brew bundle --no-upgrade`: removing an entry uninstalls
nothing. apt, uv, npm and installer entries are skipped when the package or executable is
already present, so tools with their own updaters (claude, pi) keep updating themselves.
Release binaries are the exception: chezmoi owns them and replaces them with the pinned
version.

## Hosts

A release with `"hosts": [...]` goes only to those hosts (herdr: NUC only); otherwise to
every Linux host. apt, uv, npm and installer lists have `common` and per-host keys.

The NUC's npm tools are also what its homelab agent containers run: Paseo, Omnigent's host,
Orca and Agent Canvas are host containers on its home (`~/homelab/host-home`), so they use
these `pi`, `codex` and `opencode`. `pi-acp` is there for Agent Canvas, which runs a
`pi-acp` it finds on PATH, and that adapter drives the `pi` on PATH, instead of fetching
its own older pi.

## Bumping a release binary

```sh
python3 lib/linux_releases.py list            # current pins
python3 lib/linux_releases.py pin ttt         # newest release at least 7 days old
python3 lib/linux_releases.py pin             # all of them
python3 lib/linux_releases.py pin --keep ttt  # re-verify the current tag
```

`pin` uses `gh api`, downloads every architecture's asset, and records the tag, sha256
and archive member paths. The seven-day minimum matches the npm/uv cooldown; entries with `"cooldown": false`
(herdr) pin the newest release. To add a
tool, add an entry with `repo`, `asset` (`{version}`/`{arch}` placeholders) and the `arch`
map, then `pin` it.

## Applying on the NUC

An apt change needs a sudo password. `chezmoi update --no-tty` (the remote sync) then
stops at `10-packages` with the list to install; run `chezmoi apply` in an interactive ssh
session once. Everything else needs no sudo.

## Not covered

- chezmoi itself: the bootstrap installs it (`docs/agentbox.md`, README).
- The agentbox CLI: pinned to the hub's version with a native module (`docs/agentbox.md`).
- cc-clip: deployed to the NUC by the Mac's `cc-clip` over ssh.
- Packages installed before the manifest and not listed in it stay installed.
