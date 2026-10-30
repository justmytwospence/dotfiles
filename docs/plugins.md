# Plugins

The 33 active, pi-prefixed extensions are developed together in
`~/Projects/pi-plugins/packages/<plugin>`, published as one Git package:
[Pi Plugins](https://github.com/justmytwospence/pi-plugins), with
[public documentation](https://pi-plugins.vercel.app). Each component has its own
entry point, tests, settings, and license; `pi config` selects which ones load.
One commit versions the suite. Never enable a component's original package
alongside its suite copy. Three third-party npm packages stay separate
dependencies (below).

Other maintained plugins (pi-marimo, herdr and anthropic-billing-guard)
still live in their own public repos under
`~/Projects/<plugin>`. Dotfiles vendors no
plugin implementation. On a new Mac, clone `pi-plugins` and any separate repos you
work on. Root loader checks: `npm ci && npm test`; component checks: install each
component's lockfile dependencies, then root `npm run check`. Documentation:
`cd site && npm ci && npm run check && npm run build`.

## Pins

Dotfiles holds pins, not plugin implementations. Chezmoi deploys standalone
archives; tools with native package management own their installations.

- **Pi:** Git specs in `home/private_dot_pi/private_agent/settings.managed.json`.
  On every apply the converge script's `pi-packages` section calls
  `pi update <source>` for any package that is missing or whose checkout is not at
  its pinned commit, and uninstalls npm packages dropped from the settings. It
  never upgrades Pi or unpinned npm packages.
- **OpenCode:** Authentication plugin specs in
  `home/dot_config/opencode/opencode.jsonc.tmpl`; the separate native Herdr
  integration remains in `cli.json.tmpl`. The OpenCode plugin ports are retired.
- **Herdr:** Specs, refs and hosts in `home/.chezmoidata/herdr_plugins.json`. The
  converge script's `herdr-plugins` section runs `herdr plugin install <spec> --ref
  <commit> --yes` for each one `herdr plugin list` does not show at its ref. Herdr
  builds and registers each plugin; chezmoi does not manipulate its installation
  directory. Each install lands in a new directory (herdr 0.9.4+); herdr deletes
  unused ones when a server starts. `herdr plugin update` refetches the recorded
  ref, so it does nothing for these commit pins: bump the pin instead.
- **Standalone hooks and Claude mods:** Commit-specific archives with SHA256
  checksums in `home/.chezmoiexternal.toml.tmpl`, under
  `~/.local/share/plugins/<repo>`. Chezmoi owns the consumer links.

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
the installed package. For Claude mods, test with a separate configuration
loading the development path, not by editing the deployed archive.

After testing, commit and push the plugin first. Confirm the chosen commit is
published, then edit its pin in dotfiles: the Pi settings spec, its entry in
`home/.chezmoidata/herdr_plugins.json`, or its external archive URL **and checksum**. Download the new immutable archive and compute its checksum, for example:

```sh
curl -fL https://github.com/<owner>/<repo>/archive/<commit>.tar.gz -o /tmp/plugin.tar.gz
shasum -a 256 /tmp/plugin.tar.gz
```

Review scoped file diffs and `chezmoi diff --include scripts --exclude encrypted`
before applying. A scoped apply of a settings file does not install anything:
the converge script does. Run a reviewed full `chezmoi apply`, or apply the
changed files first and then `chezmoi apply --include scripts` (`pi update`
resolves a package against the deployed `~/.pi/agent/settings.json`, so the
settings must be deployed before the converge runs). Publish/synchronize dotfiles only when authorized (see
`AGENTS.md`). Verify archives with `chezmoi verify --exclude scripts <target>`,
Pi packages with `pi list` and their checkout HEADs, and Herdr with
`herdr plugin list`.

When the converge installs a new Pi package or pin, it writes `~/.pi/agent/reload-request`, and
every running session with pi-reload-all reloads itself once its turn ends and its editor is
empty; `/reload-all` does the same by hand on every Herdr machine. Otherwise reload Pi with
`/reload`, tmux with `tmux source ~/.tmux.conf`. A Herdr install
does not run its startup hook: invoke its reapply action or restart Herdr.
To leave a Herdr development link, unlink it and reinstall its configured ref
using the native commands.

## The plugins

Pi suite components (the **suite** is pinned in `settings.managed.json`; develop
under `~/Projects/pi-plugins/packages/`, test with native local loading and
publish by updating the suite spec; sessions then reload themselves). Reference: [Pi Plugins](https://pi-plugins.vercel.app).
`anthropic-billing-guard` remains a separate package:

- [pi-status-footer](https://github.com/justmytwospence/pi-status-footer): the footer, with model, context, cost and plan limits (`/status`). Its Git summary shares the minimal `* ↑N ↓N !` suffix with the other prompts (see [Git status](#git-status)).
- [pi-rewind](https://github.com/justmytwospence/pi-rewind): restores files alongside `/tree` and `/fork`.
- [pi-clear-screen](https://github.com/justmytwospence/pi-clear-screen): `ctrl+l` clears the fullscreen transcript. The model selector is `alt+p` or `alt+m` in `keybindings.json`, where model cycling (`app.model.cycleForward`/`cycleBackward`, pi's `ctrl+p`/`shift+ctrl+p`) is off, `ctrl+p`/`ctrl+n` walk prompt history, and `ctrl+u`/`ctrl+d` stay pi's editor keys: no global half-page scroll binding on them. As in Claude Code, PageUp/PageDown scroll the transcript half a page, `ctrl+shift+-` also undoes, Ctrl+C stops a running turn, and thinking starts collapsed (`hideThinkingBlock` in `settings.managed.json`) until Ctrl+O opens it with the tool output.
- [pi-select-nav](https://github.com/justmytwospence/pi-select-nav): `ctrl+j`/`ctrl+k` (and `j`/`k`) in every picker.
- [pi-herdr-scrollbar-width](https://github.com/justmytwospence/pi-herdr-scrollbar-width): no wrapped exit transcript in herdr panes.
- [pi-herdr](https://github.com/justmytwospence/pi-herdr): pi's own herdr integration, beside the one herdr installs (state and resume), active only in an interactive pi inside herdr. The pane token `bg` names background work that will wake the agent (async subagents, plan-mode planners, awaited herdr children; `herdr:background` / `herdr:working` holds on pi's event bus), since herdr may show the pane done meanwhile. The pane's title and the token `task` are the session name or first prompt; the displayed agent name is `pi opus-5-5:xhigh`. The space token `pr` is the branch's pull request from `gh` (`#123 ✓ approved`). The `herdr` tool lists, messages, reads and waits on any agent (here or on a saved herdr machine): a pi with pi-herdr takes messages through its inbox, a marked paste consumed before the editor, so a draft is never touched, and a draft guard keeps prompts other programs type (herdr-web-ui, other agent kinds) out of an idle draft. It also starts an interactive pi in a new tab, a split or a new worktree's space (herdr's `worktree.create` into `<repo>/.worktrees/<branch>`), sends it a task, and delivers each reply as a message: only for explicit interactive-session requests or persistent human-led handoffs (report-back tasks use headless subagents, even when long or multi-step). An interactive session sharing the checkout gets a tab in the existing space; a deliberate side-by-side session gets a split; a user-requested independent branch/checkout gets its worktree's space. Ask before creating a worktree unless the user requested one or branch isolation. Other extensions reach herdr only through its event-bus bridge (`herdr:token`, `herdr:notify`, `herdr:zoom`, `herdr:split`, `herdr:probe`): pi-cache-guard, pi-marimo and pi-diff-review do, so without pi-herdr their herdr features are off. `herdr:blocked` stays herdr's own pi integration's. All tokens are in `[ui.sidebar.agents]` / `[ui.sidebar.spaces]` rows.
- [anthropic-billing-guard](https://github.com/justmytwospence/anthropic-billing-guard): warns when a subscription request bills to extra usage (pi, and opencode through a link); see [agents.md](agents.md).
- [pi-marimo](https://github.com/justmytwospence/pi-marimo): its own repo and npm package (`pi-marimo`), pinned as a Git spec beside the suite in `settings.managed.json`; develop in `~/Projects/pi-marimo` (its AGENTS.md has checks, rollout and releases). It follows the marimo notebooks a session uses: kernel state in context, rows under the prompt, and a terminal notebook view (outline and detail, docked beside the chat with `ctrl+'`).
- [pi-subagents](https://github.com/justmytwospence/pi-subagents): the `subagent` tool (single, parallel, chain; Jev picks agent, tier and effort), with Claude Code's subagent panel under the prompt (FleetView: `↓` at an empty prompt, Enter opens a run's conversation, `x` stops or dismisses) and the conversation viewer; the widget above the prompt is off by default.
- [pi-ask-user-question](https://github.com/justmytwospence/pi-ask-user-question): the `ask_user_question` tool (Claude Code-style dialog, reports blocked to herdr).
- [pi-plan-mode](https://github.com/justmytwospence/pi-plan-mode): `/plan`; see [agents.md](agents.md#planning).
- Jev plugins, each calling TypeSafe's Jev through pi's classifier models with `TYPESAFE_API_KEY`:
  [pi-tool-gate](https://github.com/justmytwospence/pi-tool-gate) (auto-approves tool calls),
  [pi-auto-effort](https://github.com/justmytwospence/pi-auto-effort) (thinking level per message),
  [pi-copy](https://github.com/justmytwospence/pi-copy) (`/yank`), and pi-cache-guard's trimming and compaction (below).
- [pi-cache-guard](https://github.com/justmytwospence/pi-cache-guard): asks before a prompt would re-cache a large conversation (an expired prompt cache or a model switch, from $0.50 at API prices), puts the cache's time left on pi-status-footer's context row (`/cache-guard`), and prints the cache-miss, keep-warm and compaction-cost lines in the transcript (pi's `showCacheMissNotices` stays off: it also prints "Anthropic dropped N thinking blocks"). Keeping the cache warm is pi's own `cacheWarming: "idle"`. With Jev (any provider pi serves it from; `/cache-guard jev` checks, switches or turns it off, or puts `/login typesafe` in the editor) it also keeps the context lean, replacing pi-lean-context: large tool output is trimmed to what the agent needs (full output under `~/.pi/agent/cache-guard/tool-output/`), the cold-cache menu and `/cache-guard compact [focus]` compact in about a second with a summary written in code, and `/compact` summarizes only what Jev did not drop. Settings live in `~/.config/agents/cache-guard.json`. Inside herdr, pi sets the pane token `cache` through pi-herdr (`❄ 664k` while the next prompt would re-cache at least $0.50 of history), which herdr's agents sidebar shows (`$cache` in `[ui.sidebar.agents]`).
- [pi-next-prompt](https://github.com/justmytwospence/pi-next-prompt): Claude Code-style next-prompt suggestions: when one next step is obvious, the model ends its answer with a `<next>` line (asked for by a short prompt section), which is stripped before the message is stored, vetted by Jev, and shown dim below the editor; `Tab`/`Right` on an empty editor fills it in, typing dismisses it (`/next-prompt`). Settings in `~/.config/agents/next-prompt.json`.
- [pi-diff-review](https://github.com/justmytwospence/pi-diff-review): `/diff`, a full-screen review of what the agent changed: everything unreviewed since your last review (default), one turn (from pi-rewind's checkpoints), the session, HEAD, the index or a branch. Vim keys; `c` comments and `s` suggests edits on lines, `:w` sends them to the agent as one message, and its tagged per-comment replies show under each comment. Zooms the herdr pane while open; `o` opens the file in `$EDITOR` in a herdr split (both through pi-herdr) (beside pi when the pane is wide, else below). No footer status of its own: pi-status-footer's `*` already says the checkout changed. Settings in `~/.pi/agent/diff-review.json`. The file tree itself is herdr-file-viewer (`prefix+t`, below).
- [pi-prose-width](https://github.com/justmytwospence/pi-prose-width): prose in the transcript (paragraphs, headings, lists, quotes) wraps at a readable measure while code blocks and tables keep the full width (`/prose-width`). The measure is `PROSE_WIDTH`, else `width` in `~/.config/agents/prose-width.json`, else 80. Tool rows are pi-cc-render's own: 80% of the pane, commands clipped at its `inputClip` (500 in `pi-cc-render.json`).
- [pi-bg](https://github.com/justmytwospence/pi-bg): background work, laid out like Claude Code. `bg_run` starts a job (wakes the agent when it exits) or a service (wakes it once when its `ready` pattern matches); `bg_wait` waits inside the turn, so herdr and tmux show the agent working until the job ends (typing a message stops the wait); `bg_logs`, `bg_kill`. A pill under the prompt (`2 shells`, `· 1 failed`) opens the background-tasks dialog (`↓` then Enter, or `/tasks`, also `/bashes`, `/ps`, `/bg`): live logs, stop, dismiss, rerun, follow in a herdr split; `/stop` stops every task. Logs in `~/.pi/agent/bg/`, never in the project. pi-tool-gate judges `bg_run` commands by the bash rules, and inside herdr it holds `herdr:background` for jobs that will wake the agent, which pi-herdr shows as `$bg`. Replaced pi-background-tasks. With pi-subagents it works as one (an `activity:*` event-bus protocol, `src/activity.ts` in both repos): the subagent panel ends with the pill, `/tasks` lists the subagents too, and `bg_wait subagent:<id>` waits on an async run; each also works alone.
- pi-cc-render: Claude Code-style transcript rendering (tool cards and groups, rich edit/write diffs, the codemode tree, compact thinking, the per-turn tool summary, the startup header, `/ccstyle`), ported from the npm package pi-cc-extensions and configured in `pi-cc-render.json`. `excludeRenderers` names every tool the suite registers (`ask_user_question`, `bg_run`/`bg_wait`/`bg_logs`/`bg_kill`, `herdr`, pi-plan-mode's `plan_*`, `subagent`) and pi-todo's `todo`, so each keeps its own renderer; `inputClip: 500`. `home/lib/test_agent_settings.py` checks the list against the suite checkout.
- pi-markdown-extras: Mermaid dialects, `> [!NOTE]` callouts, circled numbers and multi-line link labels in rendered Markdown, from pi-cc-extensions minus its bare-URL linker (it broke bolded links).
- pi-context: `/context`, the context usage breakdown with previews, from pi-cc-extensions. pi-cc-extensions' working-row token/elapsed stats and MCP chip are now pi-status-footer's (`/status working`, `/status mcp`), and its `@` references to earlier subagent runs are pi-subagents' `@run:<label-or-id>`.
- `~/.pi/agent/extensions/worktree.ts`, `mtplx-session.ts` and `eval.ts` stay in this repo:
  `/worktree` (git or herdr's worktree API, into `<repo>/.worktrees`), request
  tagging for the local MTPLX server, and `/eval` (the paid Jev evals of
  `~/Projects/pi-plugins`, through its unified runner `npm run -s eval`: the picker
  is built from the runner's target list, so new targets appear without a change
  here; a free dry run, a confirmation naming the estimated spend on
  the TypeSafe account, the live run in the background, then the change against the
  previous recorded run; `/eval last` shows stored results, `/eval <id|package|all>`
  skips the picker; inert where the checkout is
  absent, such as the NUC).

pi packages from npm, also in `settings.managed.json` (pi installs them through
`npm-cooldown`, so the seven-day hold applies; the suite never vendors them). pi
identifies a package by npm name or git URL, not by what it contains, so an npm copy
beside a suite copy of the same extension loads twice. Three stay dependencies:

- `@gotgenes/pi-anthropic-auth`: Claude through the Pro/Max subscription ([agents.md](agents.md)).
- `pi-web-access`: web search and fetch; pi-plan-mode's planners also reach it by path (`pi-plan-mode.managed.json`).
- `pi-autoresearch`: the `/autoresearch` extension only, `"skills": []`. Its three skills (create, finalize, hooks) would otherwise be discoverable in every session, and the loop they start runs the agent unattended against a metric, keeping what improves it; that is something to start deliberately, so the entry drops the skills and keeps the command.

### Suite components

`pi-vim`, `pi-stash`, `pi-sticky-last-prompt`, `pi-cc-render` and `pi-todo` are suite
components, not npm packages. pi-todo reads `~/.pi/agent/pi-todo.json`
(`collapseKey: "ctrl+t"`) and falls back to an rpiv-todo configuration.

The settings merge removes retired npm entries while preserving Pi's own state
and local-path packages. Tests: `(cd home && python3 -B -m unittest lib/test_agent_settings.py)`.

The OpenCode plugin suite and its standalone ports are retired. Herdr's separate
native OpenCode integration (`./herdr-opencode` in `cli.json.tmpl`) remains;
it is not the retired opencode-herdr port.

Others (archive pins in `home/.chezmoiexternal.toml.tmpl`; Herdr refs in `home/.chezmoidata/herdr_plugins.json`):

- Anthropic's [token-weather](https://github.com/anthropics/claude-code-playground/tree/main/claude-code/mods/token-weather) (`git`, every host): a Claude Code mod loaded through `CLAUDE_CODE_PLUGIN_DIRS` in `.zshenv`. Third-party; bump it by hand. The five maintained Claude Code plugin ports are retired.
- [codex-cache-guard](https://github.com/justmytwospence/codex-cache-guard) (`git`, every host): Codex `UserPromptSubmit` and `SessionStart` hooks in `home/private_dot_codex/hooks.managed.json` that hold a prompt once (send it again to go ahead) after 3 hours idle or a model switch on a large thread. No keep-warm: ChatGPT-plan caching has no write charge and no published TTL. No Jev either: Codex hooks cannot replace a tool result cleanly in code mode or supply a compaction. `codex-cache-guard status --cwd <dir> --tmux` prints a status for tmux.
- [agent-scrub](https://github.com/justmytwospence/agent-scrub) (`git`, every host): `agent-scrub done` (linked into `~/.local/bin`) masks the credentials in the calling session's log, in place, for Claude Code, Codex, pi and opencode. The agent decides when: the global `scrub-credentials` skill (`home/dot_agents/skills/`) tells it to run the command once it no longer needs a credential that appeared in the conversation. Nothing runs on a timer and nothing is masked without the agent's call. Needs `gitleaks` (Brewfile; a release binary on boxes and, by hand, on the NUC).
- [herdr-agentbox](https://github.com/justmytwospence/herdr-agentbox) (`herdr`, the NUC): one herdr space per AgentBox box; see [agentbox.md](agentbox.md).
- [herdr-file-viewer](https://github.com/smarzban/herdr-file-viewer) (`herdr`, hosts running a herdr server): a git-aware, read-only file tree in a split (`prefix+t`), rendering through `delta`, `bat` and `glow`; settings in `home/dot_config/herdr/plugins/config/herdr-file-viewer/config.toml`. Third-party; bump it by hand.
- [herdr-plugins](https://github.com/justmytwospence/herdr-plugins) (`herdr`, hosts running a herdr server): the small Python Herdr plugins, one per directory, sharing `lib/herdr_rpc.py`. Each is pinned separately in `home/.chezmoidata/herdr_plugins.json` as `justmytwospence/herdr-plugins/<plugin>`, all at the same commit; plugin ids (and so key bindings and plugin config/state) are unchanged from the retired standalone repos.
  - `undo` (id `herdr-undo`): `prefix+z` reopens the last closed pane, tab or space with its split tree, directories and labels, in place, resuming pi, Claude Code, Codex and opencode sessions; repeat to go further back (20 entries, 24 hours). A daemon started by its startup hook keeps the pre-close shadow, since close events carry only IDs. Processes and scrollback do not come back. After installing, restart Herdr or run `python3 -B undo.py daemon --ensure` from its plugin root.
  - `git-status`: polls every space, including grouped worktree children, independently of agents. Reports the shared minimal `* ↑N ↓N !` suffix: uncommitted work, upstream commit counts, and conflicts/unreadable Git. Clean spaces without divergence have no suffix. Normal spaces keep name on row 1 and branch plus one `$git_summary` token on row 2; grouped children append the suffix to their native branch label on row 1, without adding rows. The native Herdr installer applies the pin; invoke `git-status.enable` on an existing server. Startup restores the session-scoped reporter. The combined suffix is red for `!` or `↓`, otherwise yellow for `*`, otherwise green for `↑`.
  - `cycle` (id `agent-cycle`): orders the Agents list for `next_agent` (`C-b Enter`): the current agent, blocked agents not visited since they blocked, unseen finished agents, then everyone else least recently visited first, so one key visits what needs you first and otherwise round-robins, across machines. Hidden `cycle_rank`/`cycle_seen` pane tokens plus a per-host `cycle_cur_<host>` flag (each server's view sorts by its own, so a stale flag on the other machine is ignored); replaces `ui.agent_panel_sort` via `agent.view.set`.
  - `sort-spaces`: an action that sorts spaces alphabetically; not pinned (link the checkout to use it).
- [terminal-browser](https://github.com/zenbu-labs/terminal-browser) (`herdr`, hosts running a herdr server): the `herdr-plugin/` subdirectory adds an `open-split` action for terminal-browser, Chromium drawn in a herdr pane through Kitty graphics. Agents open pages with `terminal-browser open <url|file.html> --split right` and drive them with `terminal-browser action -- <agent-browser command>`. Macs get the app from the Brewfile cask; the plugin's build step runs the upstream installer (`~/.local/share/terminal-browser`, wrapper in `~/.local/bin`), which is the NUC's install and a redundant copy behind the cask on Macs. The NUC needs `libgbm1` (`home/.chezmoidata/linux.json`); there `action` fails because its bundled agent-browser needs glibc 2.34 and Debian 11 has 2.31, so viewing works but agents cannot drive pages. On Macs, where there is no `XDG_RUNTIME_DIR`, `action` puts agent-browser's sockets under `~/.local/state/terminal-browser-<id>/agent-browser/`, and the path overflows macOS's 103-byte socket limit once the browser's pid has five digits ("could not connect agent-browser", upstream #121). `home/dot_zshenv.tmpl` therefore points `TERMINAL_BROWSER_AGENT` at `~/.local/bin/terminal-browser-agent`, which runs the calling install's agent-browser with its sockets in `/tmp/tb-agent-<uid>`. Agent processes started before that variable existed need a restart. Drop the wrapper once upstream shortens the path. Its official skill is generated per app version inside the installer's copy, so chezmoi declares upstream's two links into that version-independent directory instead of an archive: `~/.agents/skills/terminal-browser` (default variant; Claude Code through its `skills` symlink) and `~/.codex/skills/terminal-browser` (the Codex variant, which tells Codex to escalate out of its sandbox and to prefer itself over the shared one). On Macs that makes the plugin-installed copy, not the cask, the skill's source. Upstream's own linking stays off: its pin in `home/.chezmoidata/herdr_plugins.json` sets `TERMINAL_BROWSER_SKIP_SETUP=1` and `home/dot_local/state/terminal-browser/skills-choice` is `no`, so neither the installer nor first-run setup writes its own links (it also adds Cursor and Gemini ones); herdr's `[terminal] kitty_graphics = true` is stated so `open` does not append it to the deployed config; `home/dot_config/terminal-browser/settings.managed.json` keeps telemetry and crash reports off and caps `render.fps` at 30 (managed keys win). The default, `display`, streams frames at the display rate; inside herdr on macOS each frame goes to Ghostty as inline base64 (herdrdev/herdr#3877), which stalls the whole herdr client, so the cap stays until that is fixed. Third-party; bump it by hand.
- [herdr-native-notify](https://github.com/justmytwospence/herdr-native-notify) (`herdr`, Macs): native blocked/finished alerts that click through to the exact pane, on any attached machine; see [herdr.md](herdr.md). Its `[[build]]` steps compile, ad-hoc sign and install `~/Applications/Herdr Native Notify` (updating in place, so notification permission survives); the asset-catalog icon needs full Xcode. Dotfiles owns its LaunchAgent, `~/.local/bin` wrapper and config.
- [herdr-menu](https://github.com/pierre-charles/herdr-menu) (`git` archive, Macs): a menu bar app listing herdr agents with a blocked/done badge, with saved SSH machines (`herdr --machine`) and menu settings (Show, Actions, Machines; stored in `defaults` under `dev.pierre-charles.herdr-menu`). `home/.chezmoiexternal.toml.tmpl` unpacks the commit pinned in `home/.chezmoidata/herdr_menu.json` into `~/.local/share/herdr-menu`, and the converge script's `herdr-menu` section builds it into `~/Applications/HerdrMenu.app` (needs the Xcode command line tools) and restarts a running copy. Bump commit and checksum together. Tick **Launch at login** in its menu once per Mac.

Claude Code marketplace plugins (`extraKnownMarketplaces` and `enabledPlugins` in `home/private_dot_claude/settings.managed.json`; Claude Code installs them on first start):

- [show-your-work](https://github.com/iamumeransari/claude-show-your-work) (`releases` branch, third-party): `show_image` / `show_video` tools that draw pictures and recordings inline, Ghostty, kitty, or herdr (`.zshenv` sets `CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1` in herdr panes, since Claude Code does not recognise herdr's `libghostty` XTVERSION reply). Videos need `ffmpeg`, which the Brewfile gets through `mpv`. It updates itself from its repository and sends anonymous usage counts; `/show-your-work` changes both.

Built into Claude Code and enabled in `settings.managed.json`:
`cc-plugin-you-should-know`; `cc-plugin-agents-md` (on by default) loads a
project's `AGENTS.md` when it has no `CLAUDE.md`; prompt suggestions
(`promptSuggestionEnabled`, the grey next prompt that `Tab` accepts), which
pi-next-prompt reproduces in pi.

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
reference for zsh, Claude Code, tmux and native editor summary adapters, which color each suffix mark individually. Pi renders the same contract in
maintained plugin sources. Herdr reports custom workspace tokens, including
synchronization on grouped worktree children. Codex retains native `git-branch`
(`CODEX_PINS` in `home/lib/agent_settings.py`); no supported custom status renderer is
configured there. This native Codex exception reports branch identity, not the
custom suffix; native committed branch comparisons are not uncommitted work.
Readers use `--no-optional-locks`, so a prompt never takes
`index.lock` from under an agent. Research, exact semantics, tests and native
surface limitations: [git-status.md](git-status.md).
