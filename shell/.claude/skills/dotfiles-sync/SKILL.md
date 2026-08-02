---
name: dotfiles-sync
description: "Propagate dotfiles changes to the NUC. Use whenever you commit, push, or stow in ~/dotfiles -- after the local commit/push/stow, pull and restow on spencer@nuc so both machines match. Trigger on 'commit and push', 'stow', 'restow', or any change to ~/dotfiles that lands on main. Do not use for repos other than ~/dotfiles."
---

# Dotfiles sync

`~/dotfiles` is stowed on two machines. Every commit/push/stow on the Mac must be
followed by a pull/restow on the NUC, or the two drift.

| | Mac (primary) | NUC |
|---|---|---|
| Host | local | `spencer@nuc` (Debian, x86_64) |
| Repo | `~/dotfiles` | `~/dotfiles` |
| Branch | `main` | `main` |
| Remote | `ssh://git@github.com/justmytwospence/dotfiles.git` | same, `git@` form |
| Stowed packages | `shell`, `osx` | `shell` |
| GNU Stow | 2.4.1 | 2.3.1 |

## Sequence

Do the local half first, then the remote half. Never push from the NUC.

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
  ~/dotfiles/shell/.local/bin/dotfiles-restow shell
'
```

Invoke the script by its repo path on the NUC. `~/.local/bin/dotfiles-restow` is
itself a stowed symlink, so the repo path is the one that always works — including
on a host where stow has never successfully run.

Then verify the change actually landed: `git log -1 --oneline`, plus a `grep` of
whichever file you changed through its **stowed** path (`~/.claude/settings.json`,
not `~/dotfiles/shell/...`), so you confirm the symlink resolves.

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
| 1 | stowed except the reported conflicts | relay the conflict list to the user |
| 2 | stow failed for some other reason | stop and show the raw stow output |

Exit 1 is not a failure of the sync — everything except the listed targets is
linked, and new files did propagate. Do not treat it as a reason to retry, and do
not report the sync as broken. Do surface the list; those files are silently
diverging between hosts.

## Resolving a conflict

Only when the user asks. Each conflict is a real file on that host whose contents
differ from the repo, so resolving it means deciding which copy wins:

- **Repo wins:** `mv ~/PATH ~/PATH.local && dotfiles-restow <pkg>`. The backup keeps
  the host's version recoverable. Show the diff first.
- **Host wins:** the file is genuinely machine-specific. Leave it, or dotfilize it
  properly under a host-specific path.

Never use `stow --adopt`. It resolves the conflict backwards — overwriting the repo
with that host's copy, committing the drift, and reporting success.

Current conflicts, for orientation only; the script rediscovers them each run:

- NUC / `shell`: `.zshrc`, `.config/git/ignore`, `.config/herdr/config.toml`
- Mac / `osx`: `Library/Application Support/Claude/claude_desktop_config.json`

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
