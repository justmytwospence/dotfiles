---
name: commit-hygiene
description: "How commits are shaped before they are published, in every repo: a commit is a draft until it is on the published branch (main, or git config publish.branch), drafts are changed with fixups, and git tidy folds them before publishing. Use when tidying, splitting, rewording or reordering commits, when deciding between a fixup and a new commit, before promoting a branch to main, and whenever the commit-msg-style or publish-guard hook rejects or warns."
---

# Commit hygiene

What reaches the published branch should read as a short list of logical changes, each one a unit a reviewer can understand, revert and bisect. Everything before that is a draft and may be messy.

## Drafts and the published branch

- The published branch is `git config publish.branch`, else `main`/`master`, on the remote you push to (a fork's `fork/main` included). Deployment and preview branches (`dev`, PR branches) hold drafts: pushing there for a preview publishes nothing.
- A commit is published when `git merge-base --is-ancestor <sha> origin/main` exits 0; otherwise it is a draft.
- Forks follow the `fork-patch-stack` skill, and its commits follow these rules too.

## While working

- Checkpoint commits are fine.
- A change that belongs to a draft commit: `git add <paths>`, then `git absorb --base origin/main` (it writes the fixup commits itself; check them with `git log --oneline origin/main..`). When absorb is missing or unsure, `git commit --fixup=<sha> -- <paths>`.
- A message-only change: `git commit --fixup=reword:<sha> -m "<new full message>"`. Check on first use that no editor opens; if one does, use `git commit --allow-empty --fixup=amend:<sha> -m "<new full message>"`.
- A change to a commit that is already published is a new commit (`fix: ...`), never a fixup.
- Push fixups to draft branches freely; the preview deploys the same code either way.

## Tidying with `git tidy [base]`

- It folds fixups with `rebase -i --autosquash --keep-base` onto `origin/<published branch>` (or the base you pass), so it never pulls in other people's work. It refuses a dirty tree and a range with merge commits (rebase instead of merging), warns if the tip tree changed, and prints `git log --stat` of the range.
- Then read every commit against these points: one logical change; tests and docs with the code they cover; no WIP or "address review" commits; an imperative subject of about 60 characters; a body when the why is not obvious.
- Fix what fails with the moves below. Run the checks on the tip afterwards.

## Moves without an editor

- **Reorder, drop, squash or stop at a commit:** write the todo list to a temp file (`pick <sha> <subject>` lines, with `fixup`, `squash`, `edit` or `drop` as needed), then `GIT_SEQUENCE_EDITOR="cp <file>" git rebase -i --keep-base origin/main`.
- **Split a commit:** mark it `edit`; at the stop, `git reset HEAD~`, commit the parts by path, then `git rebase --continue`.
- After a rewrite, `git diff ORIG_HEAD HEAD` is empty unless you meant to change content.

## After rewriting a pushed draft branch

- `git push --force-with-lease origin <branch>`, on your own branch or on a shared draft branch (`dev`) when promoting at the user's request.
- Branches started from its old tip: `git rebase --onto <branch> <branch>@{1} <other-branch>`.
- Bring the published branch into a branch you will tidy by rebasing (`git rebase origin/main`), not by merging.

## Hook messages

Both hooks are global (`~/.gitconfig`, sources in dotfiles `home/dot_config/git/hooks/`) and run before a repo's own hooks. `--no-verify` only when the user says so.

- `commit-msg-style: start the subject with a conventional type`: rewrite the subject as `type(scope): summary` (types are listed in the message).
- `commit-msg-style: the subject is N characters (limit 100)`: shorten it and move the detail into the body. Over 72 only warns.
- `publish-guard: refusing to push N fixup commit(s)`: you are pushing to the published branch; run `git tidy`, then push again.
- `publish-guard: ... changes files from ... in the same push`: a warning; if the commit finishes that feature, make it a fixup (`git commit --fixup=<sha>`, or `git absorb`) and `git tidy`.
- `publish-guard: ... targets a commit already on origin/main`: the fixup cannot fold into published history; reword it as a new `fix:` commit.
- `git tidy: merge commits since <base>`: rebase the branch onto the base and tidy again.

## Examples

Four commits for one change:

```
feat: weather conditions icon in the drill-down
fix: drill-down header spacing and the sky icon on the Weather link
fix: sky icon after the drill-down date, links right-aligned
test: drill-down header links sit right-aligned before the buttons
```

become one: `feat: show weather conditions in the drill-down`.

One commit hiding three changes:

```
feat(spencer): measurement_monitor.py fit, consumer and next-batch sections as cards and Altair charts; no matplotlib; placeholder checks before the refit
```

becomes `feat(monitor): show fit, consumer and next-batch sections as cards`, `refactor(monitor): replace matplotlib with Altair` and `feat(monitor): check placeholders before the refit`.

Wording: `fix: segments respect the current sport` becomes `fix: respect the current sport in segments`. A visual change is not `style:`: `style: a hue only for a metric's bands` becomes `feat: color only a metric's bands`.
