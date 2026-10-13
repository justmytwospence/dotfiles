# Git status UX

## Shared summary

**Preserve each surface's original line count.** Never add rows to accommodate
Git detail; fit or truncate within the existing layout instead. Herdr retains
two configured rows, and grouped worktree children gain no extra status row.

All custom summaries use one minimal suffix token after the branch:

```text
main
feature/login    * ↑2 ↓1
feature/merge    * ↑2 !
local
!                (unreadable Git)
```

- `*`: any uncommitted work, including staged, unstaged, untracked and
  conflicted paths; ignored files do not count. Internally, unique paths are
  still counted with byte-safe NUL records and `--untracked-files=all`, but
  no file counts appear in compact summaries.
- `!`: conflicts or unreadable Git, always last. The helper also detects paused
  merge/rebase/cherry-pick/revert operations using known markers inside the
  checkout's Git admin directory. Broken worktree metadata is an error, not
  a quiet non-repository. Outside Git, output is blank.
- `↑N` / `↓N`: commits ahead of / behind the configured upstream. Both show
  when diverged. These compare the **last fetched** local upstream reference;
  none of the summary collectors fetch or imply live remote freshness.
- Hide zero terms, including `clean`. A clean tracked branch has only identity;
  a clean branch with outstanding commits still shows arrows.
- Hide `wt`, no-upstream and missing-upstream labels. Without an available
  upstream ref, do not invent arrows. Preserve branch identity and detached
  identity (`detached:<sha7>`).

Color each mark individually: yellow `*`, green `↑N`, red `↓N` and `!`.
Branch identity keeps its ordinary foreground. Color supplements the marks;
the same information remains readable without color.

Herdr is the approved exception: its single no-dot suffix gets one severity
color. Red wins for `!` or `↓`, otherwise yellow for `*`, otherwise green for
`↑`. This retains the existing rows and spacing without a custom Herdr build.
Staged/unstaged/new categories and line totals belong in detailed Git views.
Claude's session-edit line totals are explicitly labeled `session`, because they
are not counts of uncommitted checkout paths.

## Herdr layout

Keep exactly two configured rows: normal spaces show the name on row 1, then
branch, one `$git_summary` suffix token and PR on row 2. Spaces, not dots,
separate marks inside the suffix. Grouped children retain their native branch
label on row 1 with the suffix inline, never a new status row. All other
statusbars also retain their existing height.

## Research

Established tools separate working-tree/index changes from branch divergence:

- [Git status](https://git-scm.com/docs/git-status): `XY` separates index and
  working tree, `??` is untracked, and porcelain v2 provides branch/upstream/
  ahead-behind headers. The NUL format makes filenames and renames safe to parse.
- [Starship](https://starship.rs/config/#git-status): configurable conflict,
  staged, modified, untracked, ahead/behind symbols and counts. Defaults use
  `=`, `+`, `!`, `?`, `⇡`, `⇣`; up-to-date is empty. Its configurability is useful,
  but the default punctuation needs a learned legend.
- [Powerlevel10k](https://github.com/romkatv/powerlevel10k#what-do-different-symbols-in-git-status-mean):
  `+N` staged, `!N` unstaged, `?N` untracked, `~N` conflicts, `⇡N`/`⇣N` divergence;
  also supports operation/stash state. This is dense, but conflicts even use a
  different symbol from Starship. Do not copy a symbol alphabet for its own sake.
- [LazyGit](https://github.com/jesseduffield/lazygit/blob/master/docs/Config.md):
  separate file/staging and branch/commit panels, with optional per-file line
  totals. This supports a brief summary with detail available on demand, not
  exposing every Git category in every prompt. LazyGit can fetch; passive
  prompts/footers intentionally do not.

These sources informed the design; the exact minimal suffix is ours. Git porcelain
is a data contract, not the proposed end-user UI.

## Ownership and limits

| Surface | Implementation |
|---|---|
| zsh | `dot_zsh/prompt.zsh` calls `dot_local/bin/executable_git-status-line` |
| Claude Code | `private_dot_claude/statusline-command.sh` calls that helper for status; preserves responsive layout |
| tmux | `dot_tmux.conf` uses the helper's tmux renderer for the active pane; agent badges remain separate |
| Pi | `~/Projects/pi-plugins/packages/pi-status-footer`; maintain in the suite, not retained standalone repo |
| OpenCode | `~/Projects/opencode-git-status`; TUI prompt summary |
| Herdr | `~/Projects/herdr-git-status`; workspace metadata, independent of agents, including grouped worktrees |
| Codex | Native `git-branch` item in `lib/agent_settings.py`; no custom renderer currently configured |
| Editor summaries / Eshell | Managed Vim/Neovim/Emacs configs consume the shared helper; native file/hunk views stay intact |

Herdr uses custom synchronization metadata too: native `git_status` is hidden
on grouped worktree children, so it cannot be the sole carrier of ahead/behind.
Normal spaces put branch, Git summary and PR on the original second row;
grouped children append the suffix to their native branch label on row 1.
Metadata expires if
the reporter dies. Git reads use four bounded workers; normal small groups have
15-second metadata TTLs, with finite adaptive TTLs for larger groups so slow
collections do not erase healthy status.

Native editor/file-level Git interfaces (Magit, Fugitive, GitGutter, diff-hl,
VS Code, Ranger, LazyGit) keep their richer native details, not a replacement
summary injected into every file view. tmux's agent-state marks are not Git state.
Codex 0.162.1's [status items](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/tui/src/bottom_pane/status_line_setup.rs)
include branch and *committed* branch changes against the default branch, not
this working-tree/upstream summary or an arbitrary shell-command item. Parent
Herdr/tmux surfaces cover Codex sessions; do not label its native committed
branch comparison as uncommitted changes.

Collectors remain language-local where host integration requires it, with the
same semantic contract and regression cases. zsh and Claude share one helper.
All readers use `--no-optional-locks` and do not take the index lock.

Plugin edits do not deploy through ordinary dotfiles apply. Test maintained
sources, publish before bumping pins, and follow [plugins.md](plugins.md) and
AGENTS.md for local trials/publication/synchronization. The Herdr plugin is
published and pinned in `dot_config/plugins/pins.tmpl`; `plugins sync` installs
that revision on each host. Invoke `git-status.enable` on an existing server.

## Tests

```sh
python3 -m unittest discover -s lib -p 'test_*git*.py' -v
```

Plugin repositories own their parser, formatting, real-repository and layout
tests. Editor fixtures run with isolated HOME/config and stub helpers, never
bootstrap plugins or evaluate the production Emacs init. Claude fixtures use a
fresh empty OAuth cache so tests cannot query an account. Regression cases
include clean tracked/no-upstream, unborn,
detached, staged+unstaged same path, rename, newline filenames, individual
untracked files, distinct non-UTF-8 filename bytes, conflicts, divergence,
pruned tracking refs, broken metadata, collection failure, slow Herdr scans,
editor stdout/exit ordering, saves during scans, and narrow layouts. Filesystem
fixtures for invalid UTF-8 filenames may skip on macOS; byte-parser cases still run.
