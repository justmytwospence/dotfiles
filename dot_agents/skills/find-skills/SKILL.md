---
name: find-skills
description: Find and install agent skills from the open skills ecosystem (skills.sh, the `npx skills` CLI). Use when the user asks "is there a skill for X", "find a skill for X", wants to extend what agents can do in some domain, or asks to install, list or remove a skill.
---

# Find skills

Forked from vercel-labs/skills' find-skills so that installs follow this machine's layout.
`npx skills` (vercel-labs/skills, catalog at https://skills.sh) is the package manager: it
installs one copy to `.agents/skills` (read by pi, Codex, opencode) and links it for agents
that read elsewhere (Claude Code: `.claude/skills`).

## Search

1. Check https://skills.sh (ranked by installs) for the domain.
2. `npx skills find <keywords> [--owner <github-owner>]`.
3. `npx skills add <owner/repo> -l` lists the skills a repo carries without installing.
4. `npx skills use <owner/repo>@<skill>` prints a one-off prompt for a skill without
   installing anything: use it to try one, or for a single task.

Vet before recommending: install count (prefer 1K+), source (official vendors such as
anthropics, vercel-labs, microsoft, or the tool's own org beat unknown authors), and the
repo itself. Read the SKILL.md: skills run with full agent permissions. Present the name,
what it does, installs and source, and the install command; install only when asked.

## Install

Default to the project, not the user: skills that matter only for some work (a library,
a file format, a framework) belong in the repos that use them, so they do not cost
context in every session. From the repo root:

```bash
npx skills add <owner/repo> -s <skill> -a codex claude-code -y
```

This writes `.agents/skills/<skill>`, a `.claude/skills/<skill>` link, and
`skills-lock.json`; commit all three. `npx skills experimental_install` restores them
from the lock on another checkout.

Global (every session, every project) only when the user asks for it. Then do not run
`npx skills add -g` yourself: add the repo and skill to the `sources` list in
`~/dotfiles/dot_local/bin/executable_skills-install`, `chezmoi apply`, and run
`skills-install`, so every machine gets it. Personal skills go in
`~/dotfiles/dot_agents/skills/<name>/`.

Always pass `-a`: without it the CLI links the skill into every agent directory it
detects. Never run `npx skills update`: it reinstalls without `-a`. Re-running `add`
(or `skills-install`) is the update.

## Remove

Project: `npx skills remove <skill> -y`, then commit. Global: drop it from
`skills-install`'s `sources` and add it to the retired-skills loop in
`~/dotfiles/.chezmoiscripts/run_onchange_after_85-retired.sh.tmpl`.
