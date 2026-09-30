# Global Preferences

## Environment
- Dotfiles managed with GNU stow at ~/dotfiles
- Self-maintained plugins (pi-plan-mode, herdr-attention-queue, tmux-agents) are developed in ~/Projects/<name>. ~/dotfiles/plugins/<name> are pinned submodules that pi and herdr load; never edit or commit there. Publish by pushing the plugin, then bumping the submodule (~/dotfiles README "Plugins").

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

## Beads
- If a project has a `.beads/` directory, use the `bd` CLI for task tracking (graph-based issue tracker that persists across sessions). Run `bd prime` to load workflow context.
