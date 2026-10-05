---
name: dotfiles-sync
description: "Propagate dotfiles changes to the other machines. Use whenever you commit, push, or stow in ~/dotfiles -- after the local commit/push/stow, pull and restow on spencer@nuc, the exe.dev VM, the m0 hub and the Paseo hub (each of which syncs its running machine0 spokes) so every machine matches. Trigger on 'commit and push', 'stow', 'restow', or any change to ~/dotfiles that lands on main. Do not use for repos other than ~/dotfiles."
---

# Dotfiles sync

`~/dotfiles` is stowed on the Mac, the NUC, the exe.dev VM, the herdr-machine0
hub (`herdr-hub.exe.xyz`) and the Paseo hub (`paseo-hub.exe.xyz`).
Every commit/push/stow on the Mac must be followed by a pull/restow on the others,
or they drift. machine0 spokes follow their hub: once a hub is synced,
`spoke sync --running` (herdr) or `paseo-machine0 sync --running` (Paseo) there
updates every running spoke (suspended ones pick it up on wake, `new` or the next
image build).

| | Mac (primary) | NUC | exe.dev VM | m0 hub | Paseo hub |
|---|---|---|---|---|---|
| Host | local | `spencer@nuc` (Debian, x86_64) | `<vm>.exe.xyz` (Ubuntu 24.04, x86_64, user `exedev`) | `herdr-hub.exe.xyz` (exe.dev, user `exedev`) | `paseo-hub.exe.xyz` (exe.dev, user `exedev`) |
| Repo | `~/dotfiles` | `~/dotfiles` | `~/dotfiles` | `~/dotfiles` | `~/dotfiles` |
| Branch | `main` | `main` | `main` | `main` | `main` |
| Remote | `ssh://git@github.com/justmytwospence/dotfiles.git` | same, `git@` form | same `git@` form, rewritten to the exe.dev GitHub proxy by `~/.gitconfig.local` | same as the exe.dev VM | same as the exe.dev VM |
| Stowed packages | `shell`, `osx` | `shell`, `nuc` | `shell`, `exe` | `shell`, `m0` | `shell`, `paseo-machine0` |
| GNU Stow | 2.4.1 | 2.3.1 | 2.3.1 | 2.3.1 | 2.3.1 |

`ssh exe.dev ls` names the current VM. It is disposable: if it is gone, do not
repair the sync, re-provision it with `exe/bin/bootstrap-exe` (see README "exe.dev").

## Sequence

Do the local half first, then the remote halves. Never push from the NUC or the VM.

```sh
# Mac
cd ~/dotfiles
git add <only the files for this change>   # atomic; leave unrelated drift alone
git commit
git push origin main
dotfiles-restow shell        # add osx if the change touched osx/
```

```sh
# NUC
ssh -o BatchMode=yes -o ConnectTimeout=10 spencer@nuc '
  cd ~/dotfiles &&
  git pull --rebase --autostash &&
  git submodule sync --recursive &&
  git submodule update --init --recursive &&
  ~/dotfiles/shell/.local/bin/dotfiles-restow shell nuc &&
  ~/dotfiles/shell/.local/bin/pi-plugin sync
'
```

```sh
# exe.dev VM -- same shape, different package set. <vm> comes from `ssh exe.dev ls`.
ssh -o BatchMode=yes -o ConnectTimeout=20 <vm>.exe.xyz '
  cd ~/dotfiles &&
  git pull --rebase --autostash &&
  git submodule sync --recursive &&
  git submodule update --init --recursive &&
  ~/dotfiles/shell/.local/bin/dotfiles-restow shell exe &&
  ~/dotfiles/shell/.local/bin/pi-plugin sync
'
```

```sh
# herdr-machine0 hub -- same shape as the exe.dev VM, package set `shell m0`,
# then fan out to the running spokes.
ssh -o BatchMode=yes -o ConnectTimeout=20 herdr-hub.exe.xyz '
  cd ~/dotfiles &&
  git pull --rebase --autostash &&
  git submodule sync --recursive &&
  git submodule update --init --recursive &&
  ~/dotfiles/shell/.local/bin/dotfiles-restow shell m0 &&
  ~/dotfiles/shell/.local/bin/pi-plugin sync &&
  ~/.local/bin/spoke sync --running
'
```

Skip the hub (and say so) when `ssh exe.dev ls` does not list `herdr-hub`.

```sh
# paseo-machine0 hub -- package set `shell paseo-machine0`; reload the Spokes
# plugin (a directory plugin in the pin), then fan out to the running spokes.
ssh -o BatchMode=yes -o ConnectTimeout=20 paseo-hub.exe.xyz '
  cd ~/dotfiles &&
  git pull --rebase --autostash &&
  git submodule sync --recursive &&
  git submodule update --init --recursive &&
  ~/dotfiles/shell/.local/bin/dotfiles-restow shell paseo-machine0 &&
  ~/dotfiles/shell/.local/bin/pi-plugin sync &&
  zsh -c "paseo plugin reload machine0 >/dev/null; systemctl --user restart paseo-machine0-hubd.service; paseo-machine0 sync --running"
'
```

Skip it (and say so) when `ssh exe.dev ls` does not list `paseo-hub`.

Invoke the script by its repo path on both remote hosts. `~/.local/bin/dotfiles-restow`
is itself a stowed symlink, so the repo path is the one that always works — including
on a host where stow has never successfully run.

Skills are not stowed — `shell/.stow-local-ignore` skips `.agents`. When a change
adds or renames a skill under `shell/.agents/skills/`, or edits
`shell/.local/bin/skills-install`, run `~/dotfiles/shell/.local/bin/skills-install`
on each host after its restow: it links the personal skills, installs the
third-party ones, and maintains the `~/.claude/skills` bridge. Editing an existing
skill's body needs nothing — the link points into the repo.

MCP servers work the same way: when a change edits `shell/.config/mcp/mcp.json`,
run `~/dotfiles/shell/.local/bin/mcp-install` on each host after its restow. pi and
opencode read tracked files, but Claude Code and Codex keep servers in machine-local
configs that only `mcp-install` updates. It never signs in.

The VM's git traffic goes through the exe.dev GitHub proxy rather than SSH, so a
pull failing with an auth or 404 error usually means the `dotfiles` integration was
detached, not that the repo is broken: check `ssh exe.dev integrations list`.

Then verify the change actually landed: `git log -1 --oneline`, plus a `grep` of
whichever file you changed through its **stowed** path (`~/.claude/settings.json`,
not `~/dotfiles/shell/...`), so you confirm the symlink resolves.

## Plugins

**pi plugins** (pi-plan-mode, pi-tool-gate, …) are pinned git packages in
`shell/.pi/agent/settings.json` (`git:github.com/justmytwospence/<name>@<commit>`). pi clones
each under `~/.pi/agent/git/github.com/justmytwospence/<name>`, but only when it is missing: a
changed pin is applied by `pi-plugin sync` (the step in the blocks above). Verify with
`pi-plugin list` (every row "at pin"). A plugin change reaches dotfiles as a pin bump: push the
plugin, then `pi-plugin pin <name>` and commit only the packages lines of settings.json.

**herdr plugins, tmux-agents and anthropic-billing-guard** are still git submodules under
`plugins/` (see README "Plugins"). `plugins/` is never stowed. `git pull` neither checks out nor
updates submodules, which is why every block runs `git submodule update --init`.

- Plugins are developed in `~/Projects/<name>` on the Mac, never inside `plugins/`
  (the submodules sit on a detached commit). A plugin change reaches dotfiles as a
  submodule bump: push the plugin repo first, then `git submodule update --remote
  plugins/<name>` and commit the bump (README "Plugins"). Pushing dotfiles with a
  pinned commit that is not on the plugin's remote breaks the other machines' pulls, so
  check `git -C plugins/<name> branch -r --contains HEAD` before pushing.
- A herdr plugin is linked once per host with `herdr plugin link ~/dotfiles/plugins/<name>`.
  The registry is per user and survives restarts.
- Hooks re-run python on every event, so a submodule bump takes effect without
  relinking. If the bump changed the plugin's view, run its `reapply` action. On the
  NUC that targets the session: `herdr --session homelab plugin action invoke ...`.
- Verify with `git submodule status` (no leading `-` or `+`) and `herdr plugin list`.
- A dirty submodule is drift like any other: report it, never reset it over SSH.
- A submodule removed upstream leaves its directory behind on the other machines; once
  `git submodule status` no longer lists it, delete `plugins/<name>` there.

## Always restow through `dotfiles-restow`

Never call `stow -R` directly. GNU Stow aborts the **entire** operation when any
target is a file it does not own — one unmanaged `.zshrc` blocks every other link in
the package. That failure is quiet in the worst way: targets that are already
symlinks keep tracking the repo, so content edits still land and the host looks
synced, while added and removed files silently do not propagate.

`shell/.local/bin/dotfiles-restow` retries with the conflicting paths excluded, so
everything else stows, and reports what it skipped. Its exit codes:

| Exit | Meaning | What to do |
|---|---|---|
| 0 | fully stowed | nothing |
| 1 | stowed except the reported conflicts or copies | relay the list to the user |
| 2 | stow failed for some other reason | stop and show the raw stow output |

Exit 1 is not a failure of the sync — everything except the listed targets is
linked, and new files did propagate. Do not treat it as a reason to retry, and do
not report the sync as broken. Do surface the list; those files are silently
diverging between hosts.

Files can be installed as real copies instead of links when the program reading
them refuses symlinks. They are listed in `shell/.stow-copy` (currently none:
`pi-plan-mode.json` is a normal link since the plan plugin became a local fork). `dotfiles-restow` copies one into place when it is missing or
is still a stow link, and reports (exit 1) a copy that differs from the repo --
usually a setting changed through that program's own UI. It never overwrites a
copy. To take the repo's version, delete the host copy and restow; to keep the
host's, copy it into the repo and commit it from the Mac.

## Resolving a conflict

Only when the user asks. Each conflict is a real file on that host whose contents
differ from the repo, so resolving it means deciding which copy wins:

- **Repo wins:** `mv ~/PATH ~/PATH.local && dotfiles-restow <pkg>`. The backup keeps
  the host's version recoverable. Show the diff first.
- **Host wins:** the file is genuinely machine-specific. Leave it, or dotfilize it
  properly under a host-specific path.

Never use `stow --adopt`. It resolves the conflict backwards — overwriting the repo
with that host's copy, committing the drift, and reporting success.

No conflicts are outstanding on either host. Both packages restow at exit 0, so a
non-zero exit is new information, not the known baseline. Three of the four that used
to exist were resolved in ways worth not undoing:

- **`~/.config/herdr/config.toml` is host-specific by design.** The two machines need
  genuinely different herdr configs, so it lives in `osx/` and `nuc/` rather than
  `shell/`. Do not merge them back into one.
- **`Library/Application Support/Claude/claude_desktop_config.json` is deliberately
  not stowed** — see `osx/.stow-local-ignore`. Claude Desktop rewrites it with
  account and paired-device UUIDs and local work paths, and this repo is public.
  The tracked copy is a reference snapshot; the live file stays a real file.
- `~/.zshrc` on the NUC had a redundant `cc-clip` PATH block prepended, backed up to
  `~/.zshrc.pre-stow`. If cc-clip re-adds it, it will be editing the symlink and so
  writing into the repo -- move the block to `~/.zshrc.local`, which `.zshrc` already
  sources, rather than letting it sit in the stowed file.

## Pull failures on the NUC

`--rebase --autostash` is deliberate. The NUC accumulates machine-local uncommitted
drift in tracked files, because tools write through the symlinks into the repo —
Claude Code parks host-specific keys like `fastMode` in `shell/.claude/settings.json`
there. Autostash carries that across the pull. Do not commit it from the NUC and do
not `git checkout --` it away; it is that machine's real state.

If the rebase or the autostash-reapply hits a conflict, the NUC is left mid-operation
with a dirty tree. Do not try to resolve it blind over SSH. Back out and hand it to
the user:

```sh
ssh spencer@nuc 'cd ~/dotfiles && git rebase --abort 2>/dev/null; git status --short'
```

If the autostash was already applied and conflicted, the stash still exists —
`git stash list` — so nothing is lost. Report the state and stop.

If the NUC is unreachable, say so explicitly and report the sync as incomplete.
Never let a failed SSH read as success.

## SSH noise

The connection prints a post-quantum key-exchange warning and `remote port forwarding
failed` lines on stderr. Both are expected. Filter them so they do not read as errors:

```sh
... 2>&1 | grep -v '^\*\*\|^Warning: remote'
```
