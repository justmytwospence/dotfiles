---
name: fork-patch-stack
description: "Spencer's convention for forks of upstream projects: the fork is a rebased patch stack, the fewest commits on top of upstream that give the behavior we need, one commit per would-be upstream PR, each kept upstream-ready and configurable. Use whenever you work in a fork checkout (remotes `origin` = upstream and `fork` = justmytwospence/<repo>, e.g. ~/Projects/herdr-web-ui): changing it, rebasing it onto a new release, deploying it, preparing an upstream PR from it, or auditing it. Homelab deploy mechanics (compose pins, shipshape, retiring) are in homelab's FORKS.md; this skill owns the Git side."
---

# Fork patch stack

A fork exists only to run changes upstream has not (yet) taken. It stays as close to upstream as possible: every difference is one self-contained commit that could be sent upstream as a PR as it stands. Other names for this are a *patch stack*, *patch queue* or *carry patches* (OpenShift's Kubernetes fork, Debian's `debian/patches`), under an *upstream first* policy.

## Layout

- Clone in `~/Projects/<repo>` with remote `origin` pointing at upstream and remote `fork` at `github.com/justmytwospence/<repo>`.
- **PR branches** (`fix/<topic>`, `feat/<topic>`, ... in upstream's own branch naming): each starts from upstream's default branch and holds **exactly one commit**, which is the PR. Each applies to upstream on its own. When one really needs another, say so in its commit body.
- **Deploy branch** (`homelab`): the upstream release tag we run, plus one replay of each PR branch's commit, adapted to that older base, under the same title. It holds nothing else. Order the commits so that dependencies come first.
- **`fork/main`**: a fast-forward copy of upstream's default branch, with nothing of ours on it.
- Nothing else lives on `fork`: no copies of upstream's branches, no stale experiments. The one exception is a combined preview branch that an open upstream issue links to (herdr-web-ui's `feat/notification-improvements`, from devswha/herdr-web-ui#1490). Keep it only while the issue waits for an answer.

## Making a change

1. **Fold before you add.** Read the existing stack (`git log --oneline <release-tag>..fork/homelab`). If the change finishes, fixes or extends what an existing commit is for, it belongs in that commit, on both its PR branch and `homelab`:
   - `git commit --fixup=<sha>`, then `git rebase -i --autosquash <base>`.
   - Reword the commit message if its scope grew.

   Only a change no existing commit is about gets a new PR branch and a new `homelab` commit.
2. **Make it agnostic and configurable.** Write the general capability upstream could accept: a setting, an env var or a hook, whose default (unset) keeps upstream's behavior exactly.
   - Our own values live in the deployment (homelab's compose environment, our plugins' config), not in the fork's code.
   - Never carry a hard-coded "homelab-only" tweak. Turn it into a setting and set the setting.
   - A truly fork-only commit (no upstream would want it) needs a reason in its message and in the deploy ledger.
3. **Follow upstream's rules.** That means CONTRIBUTING, AGENTS.md, commit style, tests, docs, changelog fragments, translations, and their AI-disclosure policy (no co-author trailers unless they ask). Write the commit message as the PR description: what and why, with the upstream issue as `owner/repo#N` when there is one. shipshape drops a commit once that reference ships.
4. **Build it on the PR branch first.** Base it on current upstream, run upstream's fast checks, and push the branch to `fork`. Then replay it onto `homelab`, adapting to the older base: renamed env vars, moved files. Run the checks there too. Before blaming the change, compare failures with a clean checkout.
5. **Do not open or comment on upstream PRs and issues without asking.** Pushing branches to `fork` is fine.

## Rewriting `homelab`

Folding a fixup, replacing a commit or rebasing onto a new release rewrites `homelab`. The compose file pins a full SHA, so keep every deployed SHA reachable:

```sh
git tag homelab/<version>-<short deployed sha> <deployed sha>   # unless shipshape already tagged it
git push fork homelab/<version>-<short deployed sha>
git range-diff <old homelab>...<new homelab>                    # only the intended commits differ
git push --force-with-lease=homelab:<old homelab sha> fork homelab
```

Never force-push `main`. Then move the pin, rebuild and verify per homelab's FORKS.md, and update the deploy ledger. The ledger is the comment block at the top of the stack's compose file, which lists each carried commit, its PR branch, its upstream reference, and any setting it needs.

## Taking a new upstream release

Replay `homelab` onto the new tag (shipshape does this for forks it watches; by hand otherwise, per FORKS.md). Drop commits upstream has taken (`git cherry`, or the referenced PR shipped). Fast-forward `fork/main`. Rebase a PR branch onto upstream's default branch when it goes up for review, not on every release.

## Audit

Run this when you start work on a fork, and again before you finish:

```sh
git fetch origin --tags && git fetch fork --prune
git log --oneline <release-tag>..fork/homelab                   # the stack
for b in $(git branch -r --list 'fork/*' | grep -v -e HEAD -e '/main$' -e '/homelab$'); do
  echo "$b: $(git rev-list --count origin/main..$b) commit(s) ahead of upstream"
done
git rev-list --count fork/main..origin/main                     # 0: fork/main is current
```

Check that:
- every `homelab` commit has a one-commit PR branch with the same title, or a stated fork-only reason;
- every PR branch has exactly one commit and a `homelab` counterpart;
- no fork-only behavior is hard-coded;
- no stray branches are left;
- the ledger matches the stack;
- every deployed SHA is still reachable.

Fix what you find, or report it.
