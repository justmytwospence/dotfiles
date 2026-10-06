# Global Preferences

## Environment
- Dotfiles are managed by chezmoi from `~/dotfiles` (`chezmoi source-path <file>` finds the source of any file). Edit the source, then run `chezmoi apply`; never edit the copies in `$HOME`. Settings a harness rewrites (`~/.claude/settings.json`, `~/.pi/agent/settings.json`, ...) come from the `*.managed.json` next to their source.
- npm installs resolve only to releases at least 7 days old (`min-release-age=7` in ~/.npmrc); `npm view` ignores this and shows newer ones. If a fix exists only in a newer release, say when it clears the cooldown; never bypass it without asking. Pi's `@earendil-works/*` packages are exempt.
- Plugins I maintain (pi-*, herdr-*, tmux-agents, anthropic-billing-guard, paseo-machine0) each live in their own repo in ~/Projects/<name>; a new pi extension or herdr plugin gets a new repo there, not a file in dotfiles, which only pins them. Never edit an installed copy (~/.pi/agent/git, ~/.config/herdr/plugins, ~/.tmux/plugins, ~/.local/share/plugins). To test or publish a change, follow ~/dotfiles/docs/plugins.md.

## Git
- Conventional commits (feat:, fix:, refactor:, docs:, test:, chore:), one logical change each.
- Never force push to main/master.

## Worktrees
- Create one only when asked, with `worktree new <branch>`, never `git worktree add/remove`. It makes `<project>/.worktrees/<branch>`, opens it where I work (a herdr child space or a tmux window, with pi started in it) and prints the path. `worktree --help` lists the flags and the other subcommands (ls, open, path, rm, clean).
- Your session stays where it started: work in the new checkout by absolute path or `git -C`.
- Every checkout lives in `<project>/.worktrees/` so every tool can find it. Claude Code's `--worktree`, `EnterWorktree` and `isolation: "worktree"` already go through `worktree`, so they are fine to use. Never use a tool's own worktree location instead (Codex worktrees, which stay disabled; Paseo's `--new-workspace worktree`).

## Communication
- Be concise. Skip preambles and summaries unless asked.
- No emojis in code or documentation.
