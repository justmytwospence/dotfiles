# Linux packages

The Linux counterpart of `home/dot_Brewfile.tmpl` for `nuc` and `agentbox-box`. One file,
`home/.chezmoidata/linux.json`, declares everything a Linux host's dev environment needs; the
NUC's server stack (Docker, networking, services) stays in `~/Projects/homelab`.

| Section | Installed by | When |
|---|---|---|
| `apt.common`, `apt.<host>` | `home/.chezmoiscripts/run_before_bootstrap.sh.tmpl` (sudo) | every apply; acts when a package is missing |
| `node_major` | same script: the NodeSource repository, NUC only | every apply; acts when the major changes |
| `releases` | `home/.chezmoiexternal.toml.tmpl`: pinned, checksummed externals in `~/.local/bin` | every apply (a no-op when the file matches) |
| `uv`, `npm`, `pnpm`, `installers` | converge `linux-tools` section | every apply; acts when an executable is missing |

Everything is install-only, like `brew bundle --no-upgrade`: removing an entry uninstalls
nothing, so a removal also adds its uninstall step to `home/.chezmoitemplates/converge/retired.sh`
(AGENTS.md "Converge, never accumulate"). apt, uv, npm, pnpm and installer entries are skipped when the package or executable is
already present, so tools with their own updaters (claude, pi) keep updating themselves.
Release binaries are the exception: chezmoi owns them and replaces them with the pinned
version.

## Hosts

A release with `"hosts": [...]` goes only to those hosts (herdr: NUC only); otherwise to
every Linux host. apt, uv, npm, pnpm and installer lists have `common` and per-host keys.

The NUC's npm and pnpm tools are also what its homelab agent containers run: Paseo, Omnigent's host
and Agent Canvas are host containers on its home (`~/homelab/host-home`), so they use
these `pi`, `codex` and `opencode`. `pi-acp` is there for Agent Canvas, which runs a
`pi-acp` it finds on PATH, and that adapter drives the `pi` on PATH, instead of fetching
its own older pi. pnpm installs them with its bins in `~/.local/bin` (`globalBinDir`), the
path npm used, so the containers, which captured PATH at start, find them without a restart.
pi itself and pnpm stay on npm: pi is exempt and updates itself, and pnpm cannot install
itself globally.

## Bumping a release binary

```sh
python3 home/lib/linux_releases.py list            # current pins
python3 home/lib/linux_releases.py pin ttt         # newest release at least 7 days old
python3 home/lib/linux_releases.py pin             # all of them
python3 home/lib/linux_releases.py pin --keep ttt  # re-verify the current tag
python3 home/lib/linux_releases.py pin --tag v1.2.3 ttt  # a release I asked for, even inside the cooldown
```

`pin` uses `gh api`, downloads every architecture's asset, and records the tag, sha256
and archive member paths. The seven-day minimum matches the npm/uv cooldown; entries with `"cooldown": false`
(herdr) pin the newest release, and `--tag` pins an explicitly requested release
([cooldown.md](cooldown.md)), which also covers letting one npm, pnpm or uv release through
early; the `uv-tools` section keeps uv tool receipts in line with the cooldown
(maintained-package exemptions, lapsed cutoffs). To add a tool, add an entry with `repo`, `asset` (`{version}`/`{arch}` placeholders) and the `arch`
map, then `pin` it.

## Applying on the NUC

An apt change needs a sudo password. `chezmoi update --no-tty` (the remote sync) then
stops at the bootstrap script with the list to install; run `chezmoi apply` in an interactive ssh
session once. Everything else needs no sudo.

## Not covered

- chezmoi itself: installed before the first `chezmoi init` (README; a box's `agentbox.yaml` task, `docs/agentbox.md`), so not by the bootstrap script.
- The agentbox CLI: pinned to the hub's version with a native module (`docs/agentbox.md`).
- cc-clip: deployed to the NUC by the Mac's `cc-clip` over ssh.
- Packages installed before the manifest and not listed in it stay installed.
