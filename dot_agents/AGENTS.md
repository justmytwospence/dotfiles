# Global Preferences

## Environment
- Dotfiles are managed with chezmoi; config lives in `~/dotfiles` (the chezmoi source: `dot_zshrc.tmpl` is `~/.zshrc`, `chezmoi source-path <file>` finds any). After editing, run `chezmoi apply`; never edit the copies in `$HOME`, which the next apply replaces. Other hosts pick changes up with `chezmoi update` (the dotfiles-sync skill). Settings a harness rewrites (`~/.claude/settings.json`, `~/.pi/agent/settings.json`, ...) are merged from `*.managed.json`: change the managed file, not the live one.
- npm has a supply-chain cooldown: ~/.npmrc sets `min-release-age=7`, so installs (including `@latest`) silently resolve to the newest version published 7+ days ago. `npm view` ignores it and shows newer versions. If a fix exists only in a newer release, say when it clears the cooldown; never bypass it (e.g. `--min-release-age=0`) without asking. Pi's own packages (`@earendil-works/*`) are exempt via `min-release-age-exclude[]` in ~/.npmrc. pi's `npmCommand` routes through `npm-cooldown` so its update checks respect the cooldown.
- Self-maintained plugins (pi-*, herdr-*, tmux-agents, anthropic-billing-guard, paseo-machine0) are developed in ~/Projects/<name>, each its own repo; a new pi extension or herdr plugin gets its own repo there rather than a loose file in dotfiles. Dotfiles holds only pins: pi packages in private_dot_pi/private_agent/settings.managed.json (`git:github.com/justmytwospence/<name>@<commit>`) and `<kind> <owner>/<repo> <commit>` lines in dot_config/plugins/pins.tmpl; each host program installs the plugin itself and `plugins sync` makes the installs match the pins. Test a local commit with `plugins try <name>`; publish by pushing the plugin, then `plugins pin <name>` and committing the pin files (~/dotfiles docs/plugins.md). Never edit an installed copy (~/.pi/agent/git, ~/.config/herdr/plugins, ~/.tmux/plugins, ~/.local/share/plugins).

## Git
- Conventional commit messages (feat:, fix:, refactor:, docs:, test:, chore:)
- Keep commits atomic — one logical change per commit
- Never force push to main/master

## Worktrees
- Use the `worktree` command for git worktrees, never `git worktree add/remove` directly. Checkouts live in `<project>/.worktrees/<branch>` (globally gitignored). Only create one when asked.
- `worktree new <branch>` creates the checkout and opens it where the user works: a grouped child space inside herdr, a new window inside tmux (either way with pi started in it), otherwise nowhere. It prints the path on stdout. Add `--no-open` for just the checkout, `--no-agent` for a plain shell (e.g. before `herdr agent start`), `--base REF` to fork from something other than the current HEAD.
- Your own session stays where it started; work in a new checkout by path (`git -C`, absolute paths), not by assuming you moved.
- Also: `worktree ls`, `worktree open <branch>`, `worktree path <branch>`, `worktree rm <branch> [--force] [--delete-branch]` (closes its herdr space; keeps the branch unless asked), `worktree clean` (drops finished Claude subagent checkouts).
- Claude Code's `--worktree`, `EnterWorktree` and `isolation: "worktree"` go through the same script via its WorktreeCreate/WorktreeRemove hooks, so they are fine to use. Codex's own worktrees are disabled; do not re-enable them.

## Communication
- Be concise. Skip preambles and summaries unless asked.
- No emojis in code or documentation.
