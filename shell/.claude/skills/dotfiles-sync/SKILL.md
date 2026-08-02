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
stow -R shell        # and osx, if the change touched osx/
```

```sh
# NUC
ssh -o BatchMode=yes -o ConnectTimeout=10 spencer@nuc '
  set -e
  cd ~/dotfiles
  git pull --rebase --autostash
  stow -R shell
'
```

Then verify the change actually landed on the NUC -- `git log -1 --oneline`, plus a
`grep` of whichever file you changed through its stowed path (`~/.claude/settings.json`,
not `~/dotfiles/shell/...`), so you confirm the symlink resolves.

If the NUC is unreachable, say so explicitly. Do not report the sync as done.

## Why `--rebase --autostash`

The NUC accumulates machine-local uncommitted drift in tracked files, because tools
write through the symlinks into the repo. `shell/.claude/settings.json` in particular
picks up host-specific keys (`fastMode`, and anything else Claude Code persists).

Autostash preserves that drift across the pull. Do not commit it from the NUC, and do
not `git checkout --` it away -- it is that machine's real state.

## Stow conflicts on the NUC (known, unresolved)

Three targets on the NUC are regular files rather than symlinks, and their contents
differ from the repo:

- `~/.zshrc`
- `~/.config/git/ignore`
- `~/.config/herdr/config.toml`

Stow 2.3.1 aborts the **entire** operation on conflict ("All operations aborted"), so
`stow -R shell` on the NUC currently applies nothing and exits non-zero. Existing
symlinks are left intact -- stow plans, then bails before executing -- so this is noisy
but not destructive.

Consequences:

- **Content edits to already-stowed files still propagate.** The targets are symlinks
  into the repo, so `git pull` alone is sufficient. Stow is irrelevant to them.
- **Added or removed files do not propagate.** A new file in `shell/` needs a new
  symlink, and the aborted stow never creates it. After adding files, link them
  individually on the NUC rather than forcing stow:

  ```sh
  ssh spencer@nuc 'mkdir -p ~/.claude/skills/<name> && \
    ln -sfn ../../../dotfiles/shell/.claude/skills/<name>/SKILL.md \
            ~/.claude/skills/<name>/SKILL.md'
  ```

  Get the `../` depth right: it is relative to the directory holding the link.

Never resolve these conflicts with `stow --adopt` (it overwrites the repo with the
NUC's copies) or by deleting the NUC's files. Both destroy machine-local config. If
the conflicts are worth fixing, ask first and back the files up.

## SSH noise

The connection prints a post-quantum key-exchange warning and `remote port forwarding
failed` lines on stderr. Both are expected. Filter them so they do not read as errors:

```sh
... 2>&1 | grep -v '^\*\*\|^Warning:'
```
