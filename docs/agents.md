# Coding agents

Four harnesses run side by side, each in its own herdr pane: **Claude Code**,
**Codex**, and the multi-model **pi** and **opencode**. A skill, an instruction or
an MCP server is written once here and reaches all four.

- **Skills** live in `~/.agents/skills`, the cross-vendor directory Codex, pi
  and opencode read with no configuration. Claude Code reads only
  `~/.claude/skills`, which is a symlink to it (`private_dot_claude/symlink_skills`).
  Personal skills are authored in `dot_agents/skills/<name>/` and written there by
  chezmoi; third-party ones are commit-pinned archives with checksums in
  `.chezmoiexternal.toml.tmpl`. Update their URL and checksum, review the scoped
  diff, then apply the skill target. There is no separate global skill installer. A reusable chezmoi skill is installed locally
  at `.agents/skills/chezmoi`, with a Claude Code bridge at
  `.claude/skills/chezmoi`. Project-specific dotfiles policy and machine synchronization
  live in the repo's `AGENTS.md` (`CLAUDE.md` links to it); together these replace
  the former global `dotfiles-sync` skill.
- **Instructions**: `dot_agents/AGENTS.md` is the single source. Codex
  (`~/.codex/AGENTS.md`), Claude Code (`~/.claude/CLAUDE.md`), pi
  (`~/.pi/agent/AGENTS.md`) and opencode (`~/.config/opencode/AGENTS.md`) read it
  through symlinks to `~/.agents/AGENTS.md`. Each tool loads only its own global
  path, so edit the one file. Nothing else may write instructions or skills:
  Codex desktop's "import from other agents" sync is pinned off (`CODEX_PINS` in
  `lib/agent_settings.py`), along with the Claude Cowork plugins it enabled, and
  `85-retired` removes what it had already copied in.
- **MCP**: `dot_config/mcp/mcp.managed.json` declares the set; `mcp.json.tmpl` renders it to
  `~/.config/mcp/mcp.json`, which pi reads through the `~/.pi/agent/mcp.json` symlink; `opencode.jsonc.tmpl` renders opencode's `mcp`
  block from it; `modify_private_dot_claude.json` and
  `private_dot_codex/modify_private_config.toml` merge it into `~/.claude.json` (minus
  context7, which the context7 plugin provides) and `~/.codex/config.toml`, leaving
  every other server and setting alone. Edit mcp.managed.json, `chezmoi apply`. A server
  with `"hosts": ["nuc"]` exists only on those machines (chezmoi `.host`): everywhere else
  every harness gets it disabled (Claude Code: removed), so a server that needs a local
  service or command does not fail on the other machines. A server
  with `"enabled": false` and `"projects": "<marker>"` is project-only: off at
  user level everywhere, and switched on in each repo under `~/Projects` that
  contains the marker (vercel: `.vercel`, which `vercel link` writes) on every
  apply. Claude Code gets it at local scope in `~/.claude.json`; pi, Codex and
  opencode get an `enabled` override in the repo's `.pi/mcp.json`,
  `.codex/config.toml` and `.opencode/opencode.jsonc` (listed in
  `.git/info/exclude` when untracked), and Codex gets the repo trusted, without
  which it ignores project config. Checkouts in `.worktrees/` don't get it. Signing in
  stays interactive: `/mcp` in Claude Code and pi, `codex mcp login <name>`,
  `opencode mcp auth <name>`. Claude Desktop gets remote servers from claude.ai's
  connectors (Settings > Connectors), not from this repo: the homelab servers need a
  pre-registered OAuth client, which no stdio bridge (mcp-proxy, mcp-remote) can use.
- **Settings the harnesses rewrite**: `~/.claude/settings.json`,
  `~/.codex/hooks.json` and `~/.pi/agent/settings.json` are merges of the repo's
  `*.managed.json` with the live file (README "Files programs rewrite"). So
  `pi install <pkg>` or a new Claude setting shows up in `chezmoi diff`, not in
  git: to keep it everywhere, put it in the managed file. Local-path pi packages
  (a checkout under test) are left in place.
- **Hermes Desktop (Macs)**: `~/Library/Application Support/Hermes/connections.json`
  merges the neighboring `connections.managed.json` through `lib/hermes_settings.py`.
  The repo owns the Homelab URL (`https://hermes.spencerboucher.com`), name, OAuth
  mode, and primary launch default. Other connections, last-used state, and
  machine-local authentication survive. Tokens and browser sessions are never
  tracked; sign in to Homelab once on each Mac. Quit Hermes before applying and
  reopen afterward. Unsupported registry versions and endpoint/id collisions fail
  closed rather than replacing app state. Tests: `python3 -B -m unittest lib/test_hermes_settings.py`.
- **herdr**: `herdr integration install <harness>` lets herdr report each agent's
  state ([herdr.md](herdr.md)).
- **Claude subscription billing**: pi and opencode reach Claude through the
  Pro/Max subscription (pi-anthropic-auth, @ex-machina/opencode-anthropic-auth),
  but a request not shaped as Claude Code is billed per token to extra usage.
  Every subscription response names the pool that paid
  (`anthropic-ratelimit-unified-representative-claim`), so anthropic-billing-guard,
  loaded by pi and opencode, warns the moment one lands on `overage` and appends it
  to `~/.local/state/anthropic-extra-usage.log`. Claude Code's workflow cost
  warning stays on (its "Allow once" writes `skipWorkflowUsageWarning: true` into
  the live settings; delete it there).
- **Next-prompt suggestions**: Claude Code's prompt suggestions are pinned on
  (`promptSuggestionEnabled`); pi-next-prompt and opencode-next-prompt reproduce
  them ([plugins.md](plugins.md)), shown only when one next step is obvious.
  Codex has none: its hooks can add model context, block, or start a new turn,
  but nothing can put text in the composer (its grey composer text is a fixed
  placeholder, [openai/codex#10562](https://github.com/openai/codex/issues/10562)).
  Revisit when [#17341](https://github.com/openai/codex/issues/17341) (a composer
  suggestion API for plugins) lands; the native version,
  [#14041](https://github.com/openai/codex/issues/14041), was closed unplanned.
- **Worktrees**: every checkout, whoever makes it, lives in
  `<project>/.worktrees/` (see "Worktrees" below).
- **CORAL** (`coral`, autonomous multi-agent runs against a grader): the CLI is a
  `uv` entry in the Brewfile, pinned to a release tag (not on PyPI); its four
  skills are project-local, not part of the global chezmoi externals. In a project's root, run
  `npx skills add Human-Agent-Society/CORAL -s coral-quickstart setting-up-coral creating-a-coral-task running-coral-experiments -a codex claude-code -y`
  and commit `.agents/skills`, `.claude/skills`, and `skills-lock.json`. Its Claude Code
  and Codex plugins go unused: they ship the same skills again plus a
  SessionStart install check. `dot_config/coral/agents.yaml` binds one runtime
  per harness (`claude` default, `codex`, `opencode`, `pi`) on that harness's
  default model; `coral agents doctor` pings each to check auth.
- **opencode comes from npm** (`npm install -g --allow-scripts=opencode-ai
  opencode-ai`), not Homebrew, whose bottle has crashed at startup; the
  `--allow-scripts` lets the postinstall fetch the real binary.
- **Local models** (pro Mac): MTPLX and LM Studio behind llama-swap on `:8000`
  (`dot_config/llama-swap`, the LaunchAgent), providers `mtplx` and `lmstudio` in
  pi's `models.json` and `opencode.jsonc`. Never let `mtplx start pi|opencode`
  write those configs: chezmoi owns them.
- **Credentials are never tracked.** Each harness keeps its own
  (`~/.claude/.credentials.json`, `~/.codex/auth.json`,
  `~/.local/share/opencode/auth.json`, `~/.pi/agent/auth.json`); this repo is
  public. Sign in per machine: `claude` then `/login`, `codex`, `pi` then
  `/login`, `opencode auth login`. API keys: README "Secrets".
- **Which subscription works where.** OpenAI: pi and opencode sign in with the
  ChatGPT subscription, which OpenAI permits in third-party harnesses. Anthropic:
  Claude Code uses the Max plan directly; pi and opencode reach it through
  community auth plugins that present the session as first-party. Anthropic's
  terms reserve OAuth for "ordinary use of Claude Code and other native Anthropic
  applications", and unmasked third-party traffic bills to extra usage at API rates,
  which is what you see if a plugin stops working after an upstream change.

## Bitwarden credentials

Agents get vault items one at a time through Bitwarden Agent Access (`aac`, skill `agent-access`). Each Mac runs `aac-touchid` under launchd (`com.justmytwospence.aac-touchid`, pinned in `.chezmoidata/aac_touchid.json`); it shows every request as a Touch ID sheet naming the agent, the item and the reason, so no agent can approve its own. The NUC runs only the `aac` client and asks a Mac.

There is no setup step. Each Mac's listener keeps its own `aac` paired, plus the ssh hosts listed for it under `pairSsh` in `.chezmoidata/aac_touchid.json` (the NUC, under both Macs); it checks on start and every 30 minutes and re-pairs anything stale. On the NUC, `aac` asks whichever Mac had keyboard or pointer input most recently, since that is where you can touch the sensor; `aac` is a wrapper around the real `aac-bin`. If `bw` is not logged in, the first request's dialog asks for the API key, then the master password. The first request after a restart or 8 idle hours asks for the master password in a native dialog. Only type it into a dialog that follows a request you expected.

## Directory grants

One policy, in `.chezmoidata/agent_dirs.json`, says what each project's agents may read and write without asking. It applies only on the hosts in `hosts`, currently `mac-pro`.

- By default an agent reads and writes its own checkout.
- Private roots (`~/Projects`, `~/dotfiles`, `~/Documents`, ...) are off limits outside the checkout.
- Other paths can be read. They can be written only in temp and cache directories.
- A project can grant more under `projects`: `read` (`"*"` reads anywhere) and `write` (writable and readable). Paths take `~` and globs.
- `derived.paths` are where chezmoi deploys config (`~/.config`, `~/.pi/agent`, `~/.claude`, ...). The tool-gates hold a direct write there and hand the agent `derived.hint`: edit the source in `~/dotfiles`, then `chezmoi apply`. `exemptCommands` (`chezmoi apply`, `chezmoi update`) name no paths, so deploying does not ask. The plugins know nothing of chezmoi; both settings are generic, and only this data names it. Only the tool-gates enforce these two, not the harnesses' native sandboxes.

Each harness gets the policy as its own configuration. A `tool-gate` plugin covers what that configuration cannot express.

| Harness | Native configuration | Plugin |
|---|---|---|
| Codex | `~/.codex/config.toml`: a `self` permission profile replaces `sandbox_mode`, denies the private roots and lets caches be written. Each project's `.codex/config.toml` extends it with a `project` profile: write grants as workspace roots, read grants as `read` entries. Its repo is trusted so the file applies. | none; its sandbox enforces both reads and writes |
| Claude Code | `~/.claude/settings.json`: Bash runs in the sandbox, writing only the checkout, temp and caches. Each project's `.claude/settings.local.json` adds write grants (`additionalDirectories`, `sandbox.filesystem.allowWrite`) and `Read` allow rules. | claude-tool-gate holds a file tool or Bash path that leaves the policy, which Claude's own rules cannot express: Claude's dialog in default mode, its own question in auto mode (where an ask would go to the classifier), denied headless |
| opencode | `opencode.jsonc`: `external_directory` asks for the private roots. Each project's `.opencode/opencode.jsonc` allows its grants and makes read grants ask on `edit`. | opencode-tool-gate checks paths in shell commands |
| pi | none; pi has no directory boundary | pi-tool-gate enforces the whole policy |

The three tool-gates read `directories` from `~/.config/agents/tool-gate.json` (private roots and writable caches, rendered from the data) and from each project's `.agents/tool-gate.json` (its grants).

- The per-project files are chezmoi targets under `Projects/<repo>/` and `dotfiles/`. They exist only for checkouts that exist on the host.
- The global git ignore keeps them out of each repo's status.
- Claude, Codex and opencode files are `modify_` merges (`lib/agent_dirs.py`), so a harness's own entries in them survive: Claude's "always allow" rules, the project-MCP `vercel` switch.
- Grants are only added. Removing one from the data leaves its entry in the Claude and opencode files until it is cleaned up by hand.
- To grant a new project, add it under `projects` and copy another project's four source files with its name. `lib/test_agent_dirs.py` checks that they exist.

## Worktrees

Every git worktree lives in `<repo>/.worktrees/<branch>` (slashes as dashes),
inside the main checkout and hidden by the global git ignore, so any harness,
herdr or a shell finds it with `git worktree list` and can open or remove
it. There is no shared script: each tool is configured, in its own config or
plugin, to put checkouts there.

| Creates worktrees | How it lands in `.worktrees/` |
|---|---|
| herdr `prefix+G` | popup in herdr's config: `herdr worktree create --path <repo>/.worktrees/<branch>`, opened as a grouped space |
| shell, agents | the `~/.agents/AGENTS.md` rule: `herdr worktree create --path ...` in herdr, else `git worktree add .worktrees/<branch>` |
| pi `/worktree` | `~/.pi/agent/extensions/worktree.ts`: herdr's worktree API in herdr, else git |
| pi-herdr `where: "worktree"`, pi-subagents `worktree: true` | the packages pass the path to herdr's `worktree.create` / `git worktree add` |
| Claude Code `-w`, `EnterWorktree`, `isolation: "worktree"`, Claude Desktop sessions | inline WorktreeCreate/WorktreeRemove hooks in `settings.managed.json` (`git worktree add` on branch `worktree-<name>`; remove deletes that branch only if merged) |
| OpenCode Desktop "New workspace" | `worktree.directory` in `opencode.jsonc`, which takes effect with opencode v2; 1.18 ignores it (`~/.local/share/opencode/worktree/<project id>/`), so don't use it until v2 |
| Codex app and CLI | off: Codex-managed worktrees go to `$CODEX_HOME/worktrees`, detached, with no setting to move them, so `features.worktrees = false` is pinned (`CODEX_PINS`) |

Not usable, because they have only one global location: herdr's sidebar "New
worktree" (`[worktrees] directory`; use `prefix+G`), Paseo's worktree isolation
(`~/.paseo/worktrees/<hash>/`), Codex's managed worktrees
([openai/codex#10599](https://github.com/openai/codex/issues/10599)) and OpenCode
Desktop before v2.

Branch names stay each tool's own (`worktree-<name>` from Claude Code,
`subagent/...` from pi-subagents).

## Planning

Plan in a strong model, implement in a cheaper one, optionally with two models
planning the same task in parallel.

- **pi**: [pi-plan-mode](https://github.com/justmytwospence/pi-plan-mode). `/plan
  [task]` (or `shift+tab`) opens one full-screen planner: Settings (planners A and
  B, effort, scout models, time limit; saved to `~/.pi/agent/pi-plan-mode.json`,
  seeded from `private_dot_pi/private_agent/pi-plan-mode.managed.json`, which
  only fills keys the file lacks, so a change made in Settings stays), Tools (Jev
  preselects per task), Planning and Review (each planner in its own lane;
  implement, merge, export), Implement (model, effort, keep or fresh context).
  `planCompleteCommand` runs `~/.claude/hooks/save-plan-to-obsidian.sh`.
- **opencode** (`dot_config/opencode/`): `agent.plan` (Opus, xhigh) and
  `agent.build` (Sonnet, high), switched with Tab; `/multiplan <task>` runs the
  `planner-claude` and `planner-gpt` subagents in parallel (each with a read-only
  scout; `websearch` needs `OPENCODE_ENABLE_EXA=1`, set in `.zshenv`) and asks
  which plan to use or synthesize; `/implement-fresh` hands only the plan to a
  fresh `implementer`. The planner-to-implementer model mapping is kept by hand in
  both pi-plan-mode's config and these agent files.

## Usage window primer

On the NUC, `llm-window-prime.timer` (boot + every 10 min) runs
`~/.local/bin/llm-window-prime`, and each run books the next at the exact window reset
+ 2 min or planned ping (transient `llm-window-prime-next.timer`). It starts 5-hour
subscription windows so heavy hours are split across as many fresh windows as
possible. Weekly caps are unaffected.

- Account-wide usage (Claude): every run, `~/.local/bin/llm-window-plan sample`
  records the 5-hour and 7-day utilization of the whole account (Macs, NUC, claude.ai)
  to `usage.jsonl` (8 weeks kept). It reuses a statusline cache under
  `~/.cache/claude-statusline/` younger than 10 min, else calls
  `GET api.anthropic.com/api/oauth/usage` with the NUC's Claude Code OAuth access token
  from `~/.claude/.credentials.json` (read only, never printed or written; an expired
  token skips the sample until Claude Code refreshes it).
- History: when `history.jsonl` is missing, `llm-window-plan seed` fills the 28 days
  before sampling from pi and Claude Code session logs on the NUC and each
  `SEED_HOSTS` ssh host (default `mac-pro mac-air`; it runs itself there as
  `python3 - costs`), at a fixed 0.58% of the 5-hour budget per API-equivalent $
  (measured Oct 2026). It ages out of the profile; delete the file to reseed.
- Policy (Claude): when no window is running, `llm-window-plan decide` replays each of
  the last 28 days (same day type when at least 3; 14-day half-life; time spent capped
  counts as typical active demand, not zero) from the current clock time for "ping now",
  "ping in 10 min ... 8 h" and "no ping" (my own use starts the window), and picks the
  lowest expected blocked demand over the next 24 h. Ties go to no ping, else the
  middle tied time. With under 7 days of data it pings at expiry.
  `llm-window-plan report` shows the profile, capped hours and tomorrow's
  planned windows.
- Detection per run: Claude via `claude auth status` (needs `authMethod: claude.ai`;
  API-key logins are skipped); Codex via `codex login status` (ChatGPT login) plus the
  app-server's `account/rateLimits/read`, skipping plans without a 300-minute window
  (Pro, re-checked every 6 hours). API-key env vars are unset so the CLIs never bill
  the API.
- Scheduling: each run acts only once the stored reset time (+2 min) has passed. The
  usage sample and Claude's ping (`claude -p hi --model haiku`, stream-json) both
  return the real `five_hour` reset, including a window started on another device. Codex reads its reset time without pinging and pings
  (`codex exec`, cheapest model) only when no window is in use. Fallback: ping + 5 h.
- Official CLIs only; never pi or another harness with the Anthropic subscription.
- State: `~/.local/state/llm-window-prime/`. Logs: `journalctl --user -u llm-window-prime`.
  Optional `~/.config/llm-window-prime.env` (untracked): `QUIET_HOURS="1-7"` (no
  pings then; sampling continues),
  `CLAUDE_MODEL`, `CODEX_MODEL`. Dry run: `llm-window-prime --dry-run`.
- After first deploy: `systemctl --user daemon-reload && systemctl --user start llm-window-prime.timer`.
  Both CLIs must be logged in on the NUC (`claude` then `/login`; `codex login --device-auth`).

## Sphinx

[Sphinx](https://github.com/parthh01/sphinx) quizzes me on a change before a `git push`
to a checked branch goes through. Macs only, Pi only: questions appear as Pi dialogs, not
in the browser.

- **Install**: `npm 'sphinx-understand'` in `dot_Brewfile.tmpl`, so the npm release-age
  cooldown applies. Upgrade on request with `cooldown-allow npm sphinx-understand`
  ([cooldown.md](cooldown.md)), commit, then apply; 55-sphinx reruns for the new version.
- **Setup**: `run_onchange_after_55-sphinx` runs `sphinx install --yes --no-launch
  --preset claude-economy --agents pi` under Homebrew's node (reviewer: Haiku on the Claude
  plan), and reruns when Node or Sphinx changes (its hooks pin Node's Cellar path). Never run
  `sphinx install` by hand with other flags: change the script.
- **Pi dialogs instead of the browser**: Pi's `shellCommandPrefix` (`settings.managed.json`)
  wraps `git` in the agent's bash tool (where `PI_SESSION_ID` is set) with `CI=1` once
  Sphinx's hooks exist. Sphinx then opens no browser tab or terminal window: the hook queues
  the check for this Pi session and stops the push, Sphinx's Pi extension asks the questions
  in native dialogs after the bash call, and the agent pushes again once I pass. My own
  terminal pushes and Pi `!` commands keep the browser questionnaire (`sphinx check` asks in
  the terminal instead).
- **Who owns what**: Sphinx writes and records (in `~/.config/sphinx/install.json`) the
  hook scripts in `~/.config/sphinx/hooks/global` and `~/.pi/agent/extensions/sphinx.js`.
  It refuses to replace files it finds edited, so neither is declared in source.
  `dot_gitconfig.tmpl` renders the `core.hooksPath` Sphinx sets, once its hooks exist.
  `config.json` is Sphinx's (set by the script's preset or `sphinx config`).
- **Opt-in per repository**: `create_private_yolo.json` starts global yolo, so no repo is
  checked by default. To check one: `sphinx init` there, then `sphinx yolo` inside it
  (a repository's own setting wins). Global preferences: `dot_config/private_sphinx/context.md`.
- **Agents**: run `/reload` in Pi after setup.
