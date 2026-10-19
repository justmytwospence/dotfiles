# Plugins

The 27 active, pi-prefixed extensions are developed together in
`~/Projects/pi-plugins/packages/<plugin>`, published as one Git package:
[Pi Plugins](https://github.com/justmytwospence/pi-plugins), with
[public documentation](https://pi-plugins.vercel.app). Each component has its own
entry point, tests, settings, and license; `pi config` selects which ones load.
One commit versions the suite. Original standalone repos and installed checkouts
are retained for history and rollback, but are not the active development source.
Do not enable original packages alongside their suite copies. Six former
third-party npm packages are suite components (see
[Suite components](#suite-components)); three others stay npm dependencies.

Other maintained plugins (opencode, herdr, tmux-agents, anthropic-billing-guard,
and Claude Code mods) still live in their own public repos under
`~/Projects/<plugin>`. No other harness has been migrated. Dotfiles vendors no
plugin implementation. On a new Mac, clone `pi-plugins` and any separate repos you
work on. Root loader checks: `npm ci && npm test`; component checks: install each
component's lockfile dependencies, then root `npm run check`. Documentation:
`cd site && npm ci && npm run check && npm run build`.

## Pins

Dotfiles holds pins, not plugin implementations. Chezmoi deploys standalone
archives; tools with native package management own their installations.

- **Pi:** Git specs in `private_dot_pi/private_agent/settings.managed.json`.
  After settings change, `.chezmoiscripts/run_onchange_after_40-plugins.sh.tmpl`
  calls `pi update <source>` for each configured Git package. This reconciles
  existing clones to the selected commits without upgrading Pi or npm packages.
- **OpenCode:** Git specs in `dot_config/opencode/opencode.jsonc.tmpl` and
  `tui.jsonc.tmpl`. OpenCode installs those pins at startup; keep server and TUI
  halves at the same commit.
- **Herdr:** Explicit `herdr plugin install owner/repo --ref <commit> --yes`
  calls in the same onchange script, with host branches. Herdr builds and
  registers each plugin; chezmoi does not manipulate its installation directory.
- **Standalone hooks, Claude mods, and tmux-agents:** Commit-specific archives
  with SHA256 checksums in `.chezmoiexternal.toml.tmpl`. tmux-agents lives at
  `~/.tmux/plugins/tmux-agents`; other archives live under
  `~/.local/share/plugins/<repo>`. Chezmoi owns the compatibility symlink for
  tmux-agents and the consumer links. Do not update this archive through TPM.

### Develop and publish

Develop only in `~/Projects/<repo>`, never an installed copy. Test using native
local loading instead of switching an installed checkout to development HEAD:

```sh
# Explicit extensions only: do not load both the installed suite and local suite.
pi --no-extensions -e ~/Projects/pi-plugins
# Build the development plugin first as its README requires.
herdr plugin link ~/Projects/<repo>
```

For OpenCode, use a temporary `OPENCODE_CONFIG` whose plugin entry is
`<name>@file:<absolute-checkout-path>`; keep the same package name so it replaces
the installed package. For tmux/Claude mods, test with a separate configuration
loading the development path, not by editing the deployed archive.

After testing, commit and push the plugin first. Confirm the chosen commit is
published, then edit its native settings/script ref, or its external archive URL
**and checksum**, in dotfiles. Keep the two tmux-agents pins (Pi and archive) in
sync. Download the new immutable archive and compute its checksum, for example:

```sh
curl -fL https://github.com/<owner>/<repo>/archive/<commit>.tar.gz -o /tmp/plugin.tar.gz
shasum -a 256 /tmp/plugin.tar.gz
```

Review scoped file diffs and `chezmoi diff --include scripts --exclude encrypted`
before applying. A scoped settings apply does not run the installer script;
use a reviewed full apply for provisioning, or run the documented native command
for that pin. Publish/synchronize dotfiles only when authorized (see
`AGENTS.md`). Verify archives with `chezmoi verify --exclude scripts <target>`,
Pi packages with `pi list` and their checkout HEADs, and Herdr with
`herdr plugin list`.

Reload Pi with `/reload`, tmux with `tmux source ~/.tmux.conf`. A Herdr install
does not run its startup hook: invoke its reapply action or restart Herdr.
To leave a Herdr development link, unlink it and reinstall its configured ref
using the native commands.

### Existing-host migration

The before script refuses to replace a legacy archive-target checkout if it has
local changes or its HEAD differs from the configured pin. Preserve that work
before migrating; do not force apply over it. Exact archives replace the old
checkout, including Git metadata; development stays in `~/Projects`. Review
runtime-generated files too before allowing their removal. Claude Code's generated
`.claude-plugin/types` paths and token-weather's generated `tsconfig.json` are
explicitly ignored and preserved, including by the preflight. Chezmoi owns the
tmux-agents compatibility link. Retirement removes the old manager commands,
pins file, and unused Herdr compatibility symlinks, not Herdr installations.

Heeler is retired separately: `85-retired` calls `lib/retire_heeler.py` to use
native `herdr plugin uninstall heeler`, refreshing all running local sessions
without stopping panes. Only after native uninstall and atomic, marker-scoped
SSH-key revocation succeed are its config, state and helper removed. Failure
fails apply for retry; unrelated registrations/keys and native-managed checkout
contents remain untouched. See [phone-access.md](phone-access.md#retired-heeler-integration)
for the exact key markers and the herdr PWA replacement. No Pi settings switch,
fork or upstream plugin change is involved.

## The plugins

Pi suite components (the **suite** is pinned in `settings.managed.json`; develop
under `~/Projects/pi-plugins/packages/`, test with native local loading and
publish by updating the suite spec, then `/reload`). Links below preserve the original repo
history; public reference is at [Pi Plugins](https://pi-plugins.vercel.app).
`tmux-agents` and `anthropic-billing-guard` remain separate packages:

- [pi-status-footer](https://github.com/justmytwospence/pi-status-footer): the footer, with model, context, cost and plan limits (`/status`). Its Git summary shares the minimal `* ↑N ↓N !` suffix with the other prompts (see [Git status](#git-status)).
- [pi-rewind](https://github.com/justmytwospence/pi-rewind): restores files alongside `/tree` and `/fork`.
- [pi-clear-screen](https://github.com/justmytwospence/pi-clear-screen): `ctrl+l` clears the fullscreen transcript. The model selector is `alt+p` or `alt+m` in `keybindings.json`, where model cycling (`app.model.cycleForward`/`cycleBackward`, pi's `ctrl+p`/`shift+ctrl+p`) is off, `ctrl+p`/`ctrl+n` walk prompt history, and `ctrl+u`/`ctrl+d` stay pi's editor keys: no global half-page scroll binding.
- [pi-select-nav](https://github.com/justmytwospence/pi-select-nav): `ctrl+j`/`ctrl+k` (and `j`/`k`) in every picker.
- [pi-herdr-scrollbar-width](https://github.com/justmytwospence/pi-herdr-scrollbar-width): no wrapped exit transcript in herdr panes.
- [pi-herdr](https://github.com/justmytwospence/pi-herdr): pi's own herdr integration, beside the one herdr installs (state and resume), active only in an interactive pi inside herdr. The pane token `bg` names background work that will wake the agent (async subagents, plan-mode planners, awaited herdr children; `herdr:background` / `herdr:working` holds on pi's event bus), since herdr may show the pane done meanwhile. The pane's title and the token `task` are the session name or first prompt; the displayed agent name is `pi opus-5-5:xhigh`. The space token `pr` is the branch's pull request from `gh` (`#123 ✓ approved`). The `herdr_child` tool starts an interactive pi in a new tab, a split or a new worktree's space (herdr's `worktree.create` into `<repo>/.worktrees/<branch>`), sends it a task, and delivers each reply as a message: only for explicit interactive-session requests or persistent human-led handoffs (report-back tasks use headless subagents, even when long or multi-step). An interactive session sharing the checkout gets a tab in the existing space; a deliberate side-by-side session gets a split; a user-requested independent branch/checkout gets its worktree's space. Ask before creating a worktree unless the user requested one or branch isolation. Other extensions reach herdr only through its event-bus bridge (`herdr:token`, `herdr:notify`, `herdr:zoom`, `herdr:split`, `herdr:probe`): pi-cache-guard, pi-marimo and pi-diff-review do, so without pi-herdr their herdr features are off. `herdr:blocked` stays herdr's own pi integration's. All tokens are in `[ui.sidebar.agents]` / `[ui.sidebar.spaces]` rows.
- [anthropic-billing-guard](https://github.com/justmytwospence/anthropic-billing-guard): warns when a subscription request bills to extra usage (pi, and opencode through a link); see [agents.md](agents.md).
- [pi-subagents](https://github.com/justmytwospence/pi-subagents): the `subagent` tool (single, parallel, chain; Jev picks agent, tier and effort), with Claude Code's subagent panel under the prompt (FleetView: `↓` at an empty prompt, Enter opens a run's conversation, `x` stops or dismisses) and the conversation viewer; the widget above the prompt is off by default.
- [pi-ask-user-question](https://github.com/justmytwospence/pi-ask-user-question): the `ask_user_question` tool (Claude Code-style dialog, reports blocked to herdr).
- [pi-plan-mode](https://github.com/justmytwospence/pi-plan-mode): `/plan`; see [agents.md](agents.md#planning).
- Jev plugins, each calling TypeSafe's Jev through pi's classifier models with `TYPESAFE_API_KEY`:
  [pi-tool-gate](https://github.com/justmytwospence/pi-tool-gate) (auto-approves tool calls),
  [pi-auto-effort](https://github.com/justmytwospence/pi-auto-effort) (thinking level per message),
  [pi-copy](https://github.com/justmytwospence/pi-copy) (`/yank`), and pi-cache-guard's trimming and compaction (below).
- [pi-marimo](https://github.com/justmytwospence/pi-marimo): follows the live marimo notebook open under the cwd: what is running in the footer (its own row in pi-status-footer), the notebook's current state appended to each model request and never stored (`/marimo`). Inside herdr every port (pi through pi-herdr, opencode, Claude Code) sets the pane token `marimo` (`fit.py: Model fit`) while a cell the agent started outlives its turn, shown in herdr's agents sidebar (`$marimo`), then sends a herdr notification with the done sound when the run finishes. The pane's state stays idle: herdr takes state only from each agent's own integration.
- [pi-cache-guard](https://github.com/justmytwospence/pi-cache-guard): asks before a prompt would re-cache a large conversation (an expired prompt cache or a model switch, from $0.50 at API prices), puts the cache's time left on pi-status-footer's context row (`/cache-guard`), and prints the cache-miss, keep-warm and compaction-cost lines in the transcript (pi's `showCacheMissNotices` stays off: it also prints "Anthropic dropped N thinking blocks"). Keeping the cache warm is pi's own `cacheWarming: "idle"`. With Jev (any provider pi serves it from; `/cache-guard jev` checks, switches or turns it off, or puts `/login typesafe` in the editor) it also keeps the context lean, replacing pi-lean-context: large tool output is trimmed to what the agent needs (full output under `~/.pi/agent/cache-guard/tool-output/`), the cold-cache menu and `/cache-guard compact [focus]` compact in about a second with a summary written in code, and `/compact` summarizes only what Jev did not drop. Its core (`src/core.ts`), Jev logic (`src/lean.ts`) and `~/.config/agents/cache-guard.json` are shared by the three ports below. Inside herdr every port (pi through pi-herdr) sets the pane token `cache` (`❄ 664k` while the next prompt would re-cache at least $0.50 of history), which herdr's agents sidebar shows (`$cache` in `[ui.sidebar.agents]`).
- [pi-next-prompt](https://github.com/justmytwospence/pi-next-prompt): Claude Code-style next-prompt suggestions: when one next step is obvious, the model ends its answer with a `<next>` line (asked for by a short prompt section), which is stripped before the message is stored, vetted by Jev, and shown dim below the editor; `Tab`/`Right` on an empty editor fills it in, typing dismisses it (`/next-prompt`). Settings in `~/.config/agents/next-prompt.json`, shared with the opencode port.
- [pi-diff-review](https://github.com/justmytwospence/pi-diff-review): `/diff`, a full-screen review of what the agent changed: everything unreviewed since your last review (default), one turn (from pi-rewind's checkpoints), the session, HEAD, the index or a branch. Vim keys; `c` comments and `s` suggests edits on lines, `:w` sends them to the agent as one message, and its tagged per-comment replies show under each comment. Zooms the herdr pane while open; `o` opens the file in `$EDITOR` in a herdr split (both through pi-herdr) (beside pi when the pane is wide, else below). No footer status of its own: pi-status-footer's `*` already says the checkout changed. Settings in `~/.pi/agent/diff-review.json`. The file tree itself is herdr-file-viewer (`prefix+t`, below).
- [pi-prose-width](https://github.com/justmytwospence/pi-prose-width): prose in the transcript (paragraphs, headings, lists, quotes) wraps at a readable measure while code blocks and tables keep the full width (`/prose-width`). The measure is `PROSE_WIDTH`, else `width` in `~/.config/agents/prose-width.json` (shared with the opencode and Claude Code ports), else 80. Tool rows are pi-cc-render's own: 80% of the pane, commands clipped at its `inputClip` (500 in `pi-cc-render.json`).
- [pi-bg](https://github.com/justmytwospence/pi-bg): background work, laid out like Claude Code. `bg_run` starts a job (wakes the agent when it exits) or a service (wakes it once when its `ready` pattern matches); `bg_wait` waits inside the turn, so herdr and tmux show the agent working until the job ends (typing a message stops the wait); `bg_logs`, `bg_kill`. A pill under the prompt (`2 shells`, `· 1 failed`) opens the background-tasks dialog (`↓` then Enter, or `/tasks`, also `/bashes`, `/ps`, `/bg`): live logs, stop, dismiss, rerun, follow in a herdr split; `/stop` stops every task. Logs in `~/.pi/agent/bg/`, never in the project. pi-tool-gate judges `bg_run` commands by the bash rules, and inside herdr it holds `herdr:background` for jobs that will wake the agent, which pi-herdr shows as `$bg`. Replaced pi-background-tasks. With pi-subagents it works as one (an `activity:*` event-bus protocol, `src/activity.ts` in both repos): the subagent panel ends with the pill, `/tasks` lists the subagents too, and `bg_wait subagent:<id>` waits on an async run; each also works alone.
- pi-cc-render: Claude Code-style transcript rendering (tool cards and groups, rich edit/write diffs, the codemode tree, compact thinking, the per-turn tool summary, the startup header, `/ccstyle`), ported from the npm package pi-cc-extensions and configured in `pi-cc-render.json`. `excludeRenderers` names every tool the suite registers (`ask_user_question`, `bg_run`/`bg_wait`/`bg_logs`/`bg_kill`, `herdr_child`, pi-plan-mode's `plan_*`, `subagent`) and pi-todo's `todo`, so each keeps its own renderer; `inputClip: 500`. `lib/test_agent_settings.py` checks the list against the suite checkout.
- pi-markdown-extras: Mermaid dialects, `> [!NOTE]` callouts, circled numbers and multi-line link labels in rendered Markdown, from pi-cc-extensions minus its bare-URL linker (it broke bolded links).
- pi-context: `/context`, the context usage breakdown with previews, from pi-cc-extensions. pi-cc-extensions' working-row token/elapsed stats and MCP chip are now pi-status-footer's (`/status working`, `/status mcp`), and its `@` references to earlier subagent runs are pi-subagents' `@run:<label-or-id>`.
- `~/.pi/agent/extensions/worktree.ts` and `mtplx-session.ts` stay in this repo:
  `/worktree` (git or herdr's worktree API, into `<repo>/.worktrees`), and request
  tagging for the local MTPLX server.

pi packages from npm, also in `settings.managed.json` (pi installs them through
`npm-cooldown`, so the seven-day hold applies; the suite never vendors them). pi
identifies a package by npm name or git URL, not by what it contains, so an npm copy
beside a suite copy of the same extension loads twice. Three stay dependencies:

- `@gotgenes/pi-anthropic-auth`: Claude through the Pro/Max subscription ([agents.md](agents.md)).
- `pi-web-access`: web search and fetch; pi-plan-mode's planners also reach it by path (`pi-plan-mode.managed.json`).
- `pi-autoresearch`: the `/autoresearch` extension only, `"skills": []`. Its three skills (create, finalize, hooks) would otherwise be discoverable in every session, and the loop they start runs the agent unattended against a metric, keeping what improves it; that is something to start deliberately, so the entry drops the skills and keeps the command.

### Suite components

`pi-btw`, `pi-vim`, `@saadjs/pi-stash` and `pi-sticky-last-prompt` have moved
into suite components `pi-btw`, `pi-vim`, `pi-stash` and
`pi-sticky-last-prompt`. `pi-cc-extensions` is now `pi-cc-render`, with its other
parts in pi-markdown-extras, pi-context, pi-status-footer and pi-subagents.
`@juicesharp/rpiv-todo` is now `pi-todo`, with its `todo` tool, `/todos`, session persistence and compact collapsed header. Personal settings live in `~/.pi/agent/pi-todo.json`; `collapseKey: "ctrl+t"` preserves the existing toggle. Legacy rpiv-todo configuration remains a fallback.
The migration is complete; do not re-enable the original npm packages alongside
their suite copies. Git history retains the earlier configuration.

The settings merge removes retired npm entries while preserving Pi's own state
and local-path packages. Tests: `python3 -B -m unittest lib/test_agent_settings.py`.

opencode plugins (git pins in `opencode.jsonc.tmpl`), ports of the pi plugins. The Jev
ones call Jev over its HTTP API with `TYPESAFE_API_KEY` and take options as the
second element of their `plugin` entry (`npm run check` in the checkout):

- [opencode-auto-effort](https://github.com/justmytwospence/opencode-auto-effort): the variant per prompt for the `build` agent.
- [opencode-tool-gate](https://github.com/justmytwospence/opencode-tool-gate): read-only calls run, dangerous ones and confident Jev holds are pushed back; project rules in `.opencode/tool-gate-rules.md`.
- [opencode-marimo](https://github.com/justmytwospence/opencode-marimo): the port of pi-marimo. Its TUI half (the status beside the prompt) is pinned in `tui.jsonc.tmpl` at the same commit; update both specs together.
- [opencode-cache-guard](https://github.com/justmytwospence/opencode-cache-guard): the port of pi-cache-guard, plus the keep-warm opencode lacks (replays the last Anthropic request with a one-token cap before the 5-minute TTL runs out). A held prompt goes back in the box; Enter again sends it. With `TYPESAFE_API_KEY` it also replaces opencode-lean-context: Jev trims large tool output in `tool.execute.after`, the cold-cache dialog offers continuing in a new session on a Jev summary written in code (~1s, ~$0), a compaction is told which items to keep verbatim, and the palette command "cache-guard: Jev" checks or toggles it. Its TUI half (`cache 4:12` beside the prompt) is in `tui.jsonc.tmpl` at the same commit.
- [opencode-git-status](https://github.com/justmytwospence/opencode-git-status): TUI-only, pinned in `tui.jsonc.tmpl`: the shared git status beside the prompt (see [Git status](#git-status)), before opencode-marimo and opencode-cache-guard in that slot.
- [opencode-next-prompt](https://github.com/justmytwospence/opencode-next-prompt): the port of pi-next-prompt. The server half adds the prompt block and strips the `<next>` line; the TUI half (in `tui.jsonc.tmpl` at the same commit) shows the suggestion as the empty prompt's ghost text by rendering the `session_prompt` slot, so no other plugin can replace that slot.

- [opencode-herdr](https://github.com/justmytwospence/opencode-herdr): the port of pi-herdr (`src/core` shared verbatim), pinned in both `opencode.jsonc.tmpl` and `tui.jsonc.tmpl` at the same commit. The server half has `herdr_child` (interactive opencode children in a tab, a split or a new worktree's space; each reply arrives in the parent session as a prompt, read from the child's session through the server's client or `opencode export`) and the pane token `bg` for children whose reply is pending; it needs `HERDR_PANE_ID`, so a shared `opencode serve` registers nothing. The TUI half sets the pane's title and `task` (the session title), the displayed agent name (`opencode opus-5-5:high`) and the space token `pr`. No event-bus bridge: opencode has none between plugins, so opencode-cache-guard and opencode-marimo keep their own herdr code.
- [opencode-prose-width](https://github.com/justmytwospence/opencode-prose-width): TUI-only, pinned in `tui.jsonc.tmpl`: the port of pi-prose-width (`/prose-width` toggles it).

Others (archive pins in `.chezmoiexternal.toml.tmpl`; Herdr refs in the onchange script):

- [tmux-agents](https://github.com/justmytwospence/tmux-agents) (`tmux`, every host): agent state on tmux window tabs and notifications outside herdr; Claude Code and Codex call it from their hooks, pi loads it as a package, opencode through a link.
- [claude-auto-effort](https://github.com/justmytwospence/claude-auto-effort), [claude-marimo](https://github.com/justmytwospence/claude-marimo) (the port of pi-marimo) and Anthropic's [token-weather](https://github.com/anthropics/claude-code-playground/tree/main/claude-code/mods/token-weather) (`git`, every host): Claude Code mods, loaded through `CLAUDE_CODE_PLUGIN_DIRS` in `.zshenv`. token-weather is third-party; bump it by hand.
- [claude-cache-guard](https://github.com/justmytwospence/claude-cache-guard) (`git`, every host): the Claude Code mod of pi-cache-guard: keeps the 1h cache warm across a break with `$.model.fork`, and asks before a prompt onto an expired cache (`/cache-guard`). The countdown is the status line's own, from Claude Code's `prompt_cache` input. With Jev (`TYPESAFE_API_KEY`, or the mod's sensitive `typesafe_api_key` option) it trims large tool output in the main conversation and compacts in about a second (`/cache-guard compact`, or the compaction question after a cold prompt); `/compact` summarizes only what Jev did not drop. `/cache-guard jev` checks or turns it off.
- [claude-prose-width](https://github.com/justmytwospence/claude-prose-width) (`git`, every host): the Claude Code mod of pi-prose-width, loaded through `CLAUDE_CODE_PLUGIN_DIRS` (`/prose-width`).
- [codex-cache-guard](https://github.com/justmytwospence/codex-cache-guard) (`git`, every host): Codex `UserPromptSubmit` and `SessionStart` hooks in `private_dot_codex/hooks.managed.json` that hold a prompt once (send it again to go ahead) after 3 hours idle or a model switch on a large thread. No keep-warm: ChatGPT-plan caching has no write charge and no published TTL. No Jev either: Codex hooks cannot replace a tool result cleanly in code mode or supply a compaction. `codex-cache-guard status --cwd <dir> --tmux` prints a status for tmux.
- [agent-scrub](https://github.com/justmytwospence/agent-scrub) (`git`, every host): `agent-scrub done` (linked into `~/.local/bin`) masks the credentials in the calling session's log, in place, for Claude Code, Codex, pi and opencode. The agent decides when: the global `scrub-credentials` skill (`dot_agents/skills/`) tells it to run the command once it no longer needs a credential that appeared in the conversation. Nothing runs on a timer and nothing is masked without the agent's call. Needs `gitleaks` (Brewfile; a release binary on boxes and, by hand, on the NUC).
- [herdr-agentbox](https://github.com/justmytwospence/herdr-agentbox) (`herdr`, the NUC): one herdr space per AgentBox box; see [agentbox.md](agentbox.md). (herdr-machine0 and paseo-machine0, the machine0 fleets it replaced, are retired; their repos stay up.)
- [herdr-file-viewer](https://github.com/smarzban/herdr-file-viewer) (`herdr`, hosts running a herdr server): a git-aware, read-only file tree in a split (`prefix+t`), rendering through `delta`, `bat` and `glow`; settings in `dot_config/herdr/plugins/config/herdr-file-viewer/config.toml`. Third-party; bump it by hand.
- [herdr-undo](https://github.com/justmytwospence/herdr-undo) (`herdr`, hosts running a herdr server): `prefix+z` reopens the last closed pane, tab or space with its split tree, directories and labels, in place, resuming pi, Claude Code, Codex and opencode sessions; repeat to go further back (20 entries, 24 hours). A daemon started by its startup hook keeps the pre-close shadow, since close events carry only IDs. Processes and scrollback do not come back. After installing, restart Herdr or run `python3 -B undo.py daemon --ensure` from its plugin root.
- [terminal-browser](https://github.com/zenbu-labs/terminal-browser) (`herdr`, hosts running a herdr server): the `herdr-plugin/` subdirectory adds an `open-split` action for terminal-browser, Chromium drawn in a herdr pane through Kitty graphics. Agents open pages with `terminal-browser open <url|file.html> --split right` and drive them with `terminal-browser action -- <agent-browser command>`. Macs get the app from the Brewfile cask; the plugin's build step runs the upstream installer (`~/.local/share/terminal-browser`, wrapper in `~/.local/bin`), which is the NUC's install and a redundant copy behind the cask on Macs. The NUC needs `libgbm1` (`.chezmoidata/linux.json`); there `action` fails because its bundled agent-browser needs glibc 2.34 and Debian 11 has 2.31, so viewing works but agents cannot drive pages. On Macs, where there is no `XDG_RUNTIME_DIR`, `action` puts agent-browser's sockets under `~/.local/state/terminal-browser-<id>/agent-browser/`, and the path overflows macOS's 103-byte socket limit once the browser's pid has five digits ("could not connect agent-browser", upstream #121). `dot_zshenv.tmpl` therefore points `TERMINAL_BROWSER_AGENT` at `~/.local/bin/terminal-browser-agent`, which runs the calling install's agent-browser with its sockets in `/tmp/tb-agent-<uid>`. Agent processes started before that variable existed need a restart. Drop the wrapper once upstream shortens the path. Its official skill is generated per app version inside the installer's copy, so chezmoi declares upstream's two links into that version-independent directory instead of an archive: `~/.agents/skills/terminal-browser` (default variant; Claude Code through its `skills` symlink) and `~/.codex/skills/terminal-browser` (the Codex variant, which tells Codex to escalate out of its sandbox and to prefer itself over the shared one). On Macs that makes the plugin-installed copy, not the cask, the skill's source. Upstream's own linking stays off: 40-plugins sets `TERMINAL_BROWSER_SKIP_SETUP=1` and `dot_local/state/terminal-browser/skills-choice` is `no`, so neither the installer nor first-run setup writes its own links (it also adds Cursor and Gemini ones); herdr's `[terminal] kitty_graphics = true` is stated so `open` does not append it to the deployed config; `dot_config/terminal-browser/settings.managed.json` keeps telemetry and crash reports off (managed keys win). Third-party; bump it by hand.
- [herdr-git-status](https://github.com/justmytwospence/herdr-git-status) (`herdr`, hosts running a herdr server): polls every space, including grouped worktree children, independently of agents. Reports the shared minimal `* ↑N ↓N !` suffix: uncommitted work, upstream commit counts, and conflicts/unreadable Git. Clean spaces without divergence have no suffix. Normal spaces keep name on row 1 and branch plus one `$git_summary` token on row 2; grouped children append the suffix to their native branch label on row 1, without adding rows. The native Herdr installer applies the pin; invoke `git-status.enable` on an existing server. Startup restores the session-scoped reporter. The combined suffix is red for `!` or `↓`, otherwise yellow for `*`, otherwise green for `↑`.

Claude Code marketplace plugins (`extraKnownMarketplaces` and `enabledPlugins` in `private_dot_claude/settings.managed.json`; Claude Code installs them on first start):

- [show-your-work](https://github.com/iamumeransari/claude-show-your-work) (`releases` branch, third-party): `show_image` / `show_video` tools that draw pictures and recordings inline, Ghostty, kitty, or herdr (`.zshenv` sets `CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1` in herdr panes, since Claude Code does not recognise herdr's `libghostty` XTVERSION reply). Videos need `ffmpeg`, which the Brewfile gets through `mpv`. It updates itself from its repository and sends anonymous usage counts; `/show-your-work` changes both.

Built into Claude Code and enabled in `settings.managed.json`:
`cc-plugin-you-should-know`; `cc-plugin-agents-md` (on by default) loads a
project's `AGENTS.md` when it has no `CLAUDE.md`; prompt suggestions
(`promptSuggestionEnabled`, the grey next prompt that `Tab` accepts), which the
next-prompt plugins reproduce in pi and opencode.

## Git status

Shared compact summary:

```text
<branch> [* ↑N ↓N !]
```

`*` means any uncommitted work (staged, unstaged, untracked or conflicted);
`↑N` / `↓N` count commits, and `!` comes last for conflicts or unreadable Git.
The helper also recognizes paused operations inside the Git admin directory.
Hide file counts, zero/clean terms, `wt`, no-upstream and missing-upstream labels.
Keep branch/detached identity; outside Git is blank. Arrows compare last-fetched
refs, never an implicit fetch or a claim of live remote freshness. Marks form
one token with spaces between marks, never dot separators. Claude's `session` totals remain session-edit
lines, not checkout file counts. Every statusbar retains its existing height.
`~/.local/bin/git-status-line` (`-f ansi|zsh|plain|tmux`, `-m` status only) is the
reference for zsh, Claude Code, tmux and native editor summary adapters, which color each suffix mark individually. Pi/OpenCode render the same contract in
maintained plugin sources. Herdr reports custom workspace tokens, including
synchronization on grouped worktree children. Codex retains native `git-branch`
(`CODEX_PINS` in `lib/agent_settings.py`); no supported custom status renderer is
configured there. This native Codex exception reports branch identity, not the
custom suffix; native committed branch comparisons are not uncommitted work.
Readers use `--no-optional-locks`, so a prompt never takes
`index.lock` from under an agent. Research, exact semantics, tests and native
surface limitations: [git-status.md](git-status.md).
