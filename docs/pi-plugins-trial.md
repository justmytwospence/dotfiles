# Pi Plugins consolidation

The packaging trial was accepted after a manual `/reload` with no detected regressions. The active Pi extensions now come from one commit-pinned suite, [Pi Plugins](https://github.com/justmytwospence/pi-plugins). [Public documentation](https://pi-plugins.vercel.app) covers all 19 components, requirements, configuration, recipes, integration protocols and development.

## Scope and source

- Develop components under `~/Projects/pi-plugins/packages/<name>` and the documentation under `site/`.
- Configure the suite pin in `private_dot_pi/private_agent/settings.managed.json`; `plugins try pi-plugins` / `plugins pin pi-plugins` operate on the whole suite.
- Original repos and installed checkouts are retained for provenance and rollback. They are not the active development source, and must not be enabled alongside suite copies.
- Third-party packages, local pi-quiz, tmux-agents, anthropic-billing-guard and other harnesses remain separate. The opencode collection has not been migrated.
- `source-pins.json` records the initial 19 imports. Their implementation was unchanged for the trial; the first post-trial patch fixes a Linux stdin EPIPE race in diff-review, with regression coverage.
- Root loader tests validate full-suite selection, each component independently, no duplicate registrations, and empty selection. Component checks and docs coverage/link/build checks run in GitHub Actions.

## Release and machines

One Git revision versions the suite. Each component can be independently enabled through `pi config`, not independently Git-version-pinned. Publish the suite first, update the managed pin, commit only relevant dotfiles changes, apply reviewed targets, and follow the synchronization policy in `AGENTS.md`. Running Pi sessions need `/reload` after a pin update.

The NUC receives published settings through `chezmoi update`. The other Mac requires its user-run update; boxes apply main at startup. A commit alone does not update running sessions.

## Rollback

The first trial's original settings remain at `~/Projects/pi-plugins/.trial/settings.managed.before.json`. The latest published standalone configuration, including subsequent Herdr and subagents updates, is retained at `.trial/settings.managed.rollback.json`. Both are ignored by Git. The rollback helper uses the latter and restores only the package list through chezmoi, refusing if that list has independently changed:

```sh
python3 ~/Projects/pi-plugins/.trial/rollback.py
```

Then `/reload` or restart Pi. To undo a published rollout across machines, commit and push the restored managed package list and synchronize according to `AGENTS.md`. The helper's local apply is not a global rollback. Without the local backup, reconstruct the original package entries from `source-pins.json`, preserving unrelated package entries and their order. No checkout needs to be deleted.

## Remaining maintenance

The static documentation build toolchain has npm advisories, including `http-cache-semantics <=4.2.0` (GHSA-ch52-4w7c-c8xp). There is no deployed server-side cache or private-user response caching: production is static assets. The fixed 4.3.0 clears the seven-day cooldown at 2026-10-11 02:56 UTC; update then without bypassing policy and review the moderate advisories too.
