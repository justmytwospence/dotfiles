# Global Preferences

## Environment
- Dotfiles are managed by chezmoi from `~/dotfiles`; edit sources, never deployed `$HOME` copies. Before changing them, read `~/dotfiles/.agents/skills/chezmoi/SKILL.md` for the project workflow and synchronization policy.
- npm installs resolve only to releases at least 7 days old (`min-release-age=7` in ~/.npmrc); `npm view` ignores this and shows newer ones. If a fix exists only in a newer release, say when it clears the cooldown; never bypass it without asking. Pi's `@earendil-works/*` packages are exempt.
- Plugins I maintain (pi-*, herdr-*, tmux-agents, anthropic-billing-guard) each live in their own repo in ~/Projects/<name>; a new pi extension or herdr plugin gets a new repo there, not a file in dotfiles, which only pins them. Never edit an installed copy (~/.pi/agent/git, ~/.config/herdr/plugins, ~/.tmux/plugins, ~/.local/share/plugins). To test or publish a change, follow ~/dotfiles/docs/plugins.md.
- Skills install per project unless I ask for global: `npx skills add <repo> -s <skill> -a codex claude-code -y` in the repo root, then commit `.agents/skills`, `.claude/skills` and `skills-lock.json`. Global skills are the `sources` list in `~/.local/bin/skills-install` (edit its dotfiles source, then run it). Never use `npx skills add -g`, an `add` without `-a`, or `npx skills update`.
- AgentBox boxes (hub on the NUC, boxes there or on Daytona): ~/dotfiles/docs/agentbox.md, including the `agentbox.yaml` task that applies these dotfiles in a box. Inside a box, `git` push/pull/fetch/clone go through the hub; do not add credentials there.
- Whenever a task touches a marimo notebook, load the global `marimo-style` skill alongside the project's `marimo-pair` skill.

## Git
- Conventional commits (feat:, fix:, refactor:, docs:, test:, chore:), one logical change each.
- Never force push to main/master.

## Worktrees
- Create one only when asked, with `worktree new <branch>`, never `git worktree add/remove`. It makes `<project>/.worktrees/<branch>`, opens it where I work (a herdr child space or a tmux window, with pi started in it) and prints the path. `worktree --help` lists the flags and the other subcommands (ls, open, path, rm, clean).
- Your session stays where it started: work in the new checkout by absolute path or `git -C`.
- Every checkout lives in `<project>/.worktrees/` so every tool can find it. Claude Code's `--worktree`, `EnterWorktree` and `isolation: "worktree"` already go through `worktree`, so they are fine to use. Never use a tool's own worktree location instead (Codex worktrees, which stay disabled; Paseo's `--new-workspace worktree`).

## Delegation
- Default to headless subagents for delegated work that reports back to the main session, even if long, multi-step, or parallel. Do not create Herdr panes, tabs, or spaces for disposable report-back workers. Duration, complexity, and a hypothetical desire to watch are not reasons to start an interactive session.
- Start a persistent interactive agent only when the user requests one or the task is clearly a human-led handoff that the user will continue independently. Its ability to report back is coordination support, not a substitute for a headless subagent.
- For an interactive handoff sharing the current checkout and branch, use a tab in the existing Herdr space. Use a split only for deliberate side-by-side interaction or when requested. Tabs and splits share files; they are not isolated parallel editors. Keep focus unchanged unless asked to switch.
- An independent feature or PR may benefit from its own branch and checkout: use a new worktree's Herdr space only when the user requests a worktree or branch isolation; otherwise ask first. An already-open worktree space gets a tab there. Never create a new space or worktree merely because work is delegated, long, or parallel.

## Communication
- Be concise. Skip preambles and summaries unless asked.
- No emojis in code or documentation.
