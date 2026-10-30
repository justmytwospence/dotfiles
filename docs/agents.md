# Coding agents

Four harnesses run side by side, each in its own herdr pane: **Claude Code**,
**Codex**, and the multi-model **pi** and **opencode**. A skill, an instruction or
an MCP server is written once here and reaches all four.

- **Skills** live in `~/.agents/skills`, the cross-vendor directory Codex, pi
  and opencode read with no configuration. Claude Code reads only
  `~/.claude/skills`, which is a symlink to it (`home/private_dot_claude/symlink_skills`).
  Personal skills are authored in `home/dot_agents/skills/<name>/` and written there by
  chezmoi; third-party ones are commit-pinned archives with checksums in
  `home/.chezmoiexternal.toml.tmpl`. Update their URL and checksum, review the scoped
  diff, then apply the skill target. There is no separate global skill installer. A reusable chezmoi skill is installed locally
  at `.agents/skills/chezmoi`, with a Claude Code bridge at
  `.claude/skills/chezmoi`. Project-specific dotfiles policy and machine synchronization
  live in the repo's `AGENTS.md` (`CLAUDE.md` links to it); together these replace
  the former global `dotfiles-sync` skill.
- **Instructions**: `home/dot_agents/AGENTS.md` is the single source. Codex
  (`~/.codex/AGENTS.md`), Claude Code (`~/.claude/CLAUDE.md`), pi
  (`~/.pi/agent/AGENTS.md`) and opencode (`~/.config/opencode/AGENTS.md`) read it
  through symlinks to `~/.agents/AGENTS.md`. Each tool loads only its own global
  path, so edit the one file. Nothing else may write instructions or skills:
  Codex desktop's "import from other agents" sync and the Claude Cowork plugins are
  pinned off (`CODEX_PINS` in `home/lib/agent_settings.py`).
- **MCP**: `home/dot_config/mcp/mcp.managed.json` declares the set; `mcp.json.tmpl` renders it to
  `~/.config/mcp/mcp.json`, which pi reads through the `~/.pi/agent/mcp.json` symlink; `opencode.jsonc.tmpl` renders opencode's `mcp`
  block from it; `home/modify_private_dot_claude.json` and
  `home/private_dot_codex/modify_private_config.toml` merge it into `~/.claude.json` (minus
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
  merges the neighboring `connections.managed.json` through `home/lib/hermes_settings.py`.
  The repo owns the Homelab URL (`https://hermes.spencerboucher.com`), name, OAuth
  mode, and primary launch default. Other connections, last-used state, and
  machine-local authentication survive. Tokens and browser sessions are never
  tracked; sign in to Homelab once on each Mac. Quit Hermes before applying and
  reopen afterward. Unsupported registry versions and endpoint/id collisions fail
  closed rather than replacing app state. Tests: `(cd home && python3 -B -m unittest lib/test_hermes_settings.py)`.
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
  (`promptSuggestionEnabled`); pi-next-prompt reproduces
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
  SessionStart install check. `home/dot_config/coral/agents.yaml` binds one runtime
  per harness (`claude` default, `codex`, `opencode`, `pi`) on that harness's
  default model; `coral agents doctor` pings each to check auth.
- **opencode comes from npm** (`npm install -g --allow-scripts=opencode-ai
  opencode-ai`), not Homebrew, whose bottle has crashed at startup; the
  `--allow-scripts` lets the postinstall fetch the real binary.
- **Local models** (pro Mac): MTPLX and LM Studio behind llama-swap on `:8000`
  (`home/dot_config/llama-swap`, the LaunchAgent), providers `mtplx` and `lmstudio` in
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

Agents get vault items one at a time through Bitwarden Agent Access (`aac`, skill `agent-access`). Each Mac runs `aac-touchid` under launchd (`com.justmytwospence.aac-touchid`, pinned in `home/.chezmoidata/aac_touchid.json`); it shows every request as a Touch ID sheet naming the agent, the item and the reason, so no agent can approve its own. The NUC runs only the `aac` client and asks a Mac.

There is no setup step. Each Mac's listener keeps its own `aac` paired, plus the ssh hosts listed for it under `pairSsh` in `home/.chezmoidata/aac_touchid.json` (the NUC, under both Macs); it checks on start and every 30 minutes and re-pairs anything stale. On the NUC, `aac` asks whichever Mac had keyboard or pointer input most recently, since that is where you can touch the sensor; `aac` is a wrapper around the real `aac-bin`. If `bw` is not logged in, the first request's dialog asks for the API key, then the master password. The first request after a restart or 8 idle hours asks for the master password in a native dialog. Only type it into a dialog that follows a request you expected.

## Directory grants

One policy, in `home/.chezmoidata/agent_dirs.json`, defines each project's directory grants. It applies only on the hosts in `hosts`, currently `mac-pro`; enforcement differs by harness as described below.

- By default an agent reads and writes its own checkout.
- Private roots (`~/Projects`, `~/Documents`, ...) are off limits outside the checkout.
- Other paths can be read. They can be written only in temp and cache directories.
- A project can grant more under `projects`: `read` (`"*"` reads anywhere) and `write` (writable and readable). Paths take `~` and globs.
- `derived.paths` are where chezmoi deploys config (`~/.config`, `~/.pi/agent`, `~/.claude`, ...). pi-tool-gate holds a direct write there and hands the agent `derived.hint`: edit the source in `~/Projects/dotfiles`, then `chezmoi apply`. `exemptCommands` (`chezmoi apply`, `chezmoi update`) name no paths, so deploying does not ask. The plugin knows nothing of chezmoi; both settings are generic, and only this data names it. Only pi-tool-gate enforces these two, not the harnesses' native sandboxes.

Claude Code, Codex and opencode get native configuration derived from the policy. Only pi retains a tool-gate plugin; the retired Claude Code and OpenCode ports no longer cover gaps in native enforcement.

| Harness | Native configuration | Plugin |
|---|---|---|
| Codex | `~/.codex/config.toml`: a `self` permission profile replaces `sandbox_mode`, denies the private roots and lets caches be written. Each project's `.codex/config.toml` extends it with a `project` profile: write grants as workspace roots, read grants as `read` entries. Its repo is trusted so the file applies. | none; its sandbox enforces both reads and writes |
| Claude Code | `~/.claude/settings.json`: Bash runs in the sandbox, writing only the checkout, temp and caches. Each project's `.claude/settings.local.json` adds write grants (`additionalDirectories`, `sandbox.filesystem.allowWrite`) and `Read` allow rules. | none; native sandbox and permission rules remain, without the retired port's file-tool or Bash-path guard |
| opencode | `opencode.jsonc`: `external_directory` asks for the private roots. Each project's `.opencode/opencode.jsonc` allows its grants and makes read grants ask on `edit`. | none; no plugin checks paths in shell commands |
| pi | none; pi has no directory boundary | pi-tool-gate enforces the whole policy |

pi-tool-gate reads `directories` from `~/.config/agents/tool-gate.json` (private roots and writable caches, rendered from the data) and from each project's `.agents/tool-gate.json` (its grants).

- The per-project files are chezmoi targets under `~/Projects/<repo>/`, this checkout included (sources in `home/Projects/`). They exist only for checkouts that exist on the host.
- The global git ignore keeps them out of each repo's status.
- Claude, Codex and opencode files are `modify_` merges (`home/lib/agent_dirs.py`), so a harness's own entries in them survive: Claude's "always allow" rules, the project-MCP `vercel` switch.
- Grants are only added. Removing one from the data leaves its entry in the Claude and opencode files until it is cleaned up by hand.
- To grant a new project, add it under `projects` and copy another project's four source files with its name. `home/lib/test_agent_dirs.py` checks that they exist.

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
  seeded from `home/private_dot_pi/private_agent/pi-plan-mode.managed.json`, which
  only fills keys the file lacks, so a change made in Settings stays), Tools (Jev
  preselects per task), Planning and Review (each planner in its own lane;
  implement, merge, export), Implement (model, effort, keep or fresh context).
  `planCompleteCommand` runs `~/.claude/hooks/save-plan-to-obsidian.sh`.
- **opencode** (`home/dot_config/opencode/`): `agent.plan` (Opus, xhigh) and
  `agent.build` (Sonnet, high), switched with Tab; `/multiplan <task>` runs the
  `planner-claude` and `planner-gpt` subagents in parallel (each with a read-only
  scout; `websearch` needs `OPENCODE_ENABLE_EXA=1`, set in `.zshenv`) and asks
  which plan to use or synthesize; `/implement-fresh` hands only the plan to a
  fresh `implementer`. The planner-to-implementer model mapping is kept by hand in
  both pi-plan-mode's config and these agent files.

## Defenestrator

The defenestrator throws spent 5-hour usage windows out and starts fresh ones, so heavy hours
split across as many windows as possible (weekly caps are unaffected). It lives in its own repo,
[justmytwospence/defenestrator](https://github.com/justmytwospence/defenestrator), and runs on
the NUC as the homelab stack `~/Projects/homelab/defenestrator` (a private ghcr image), not from
dotfiles. It replaced the systemd `defenestrator.timer` and the two scripts here on 2026-10-29;
`converge/retired.sh` removes the old units and scripts.

- The container uses the NUC user's subscription logins (`~/.claude`, `~/.codex`, mounted
  read-write so the CLIs can refresh tokens); both CLIs must stay logged in on the NUC
  (`claude` then `/login`; `codex login --device-auth`). Official CLIs only, never pi or another
  harness with the Anthropic subscription.
- State: `~/Projects/homelab/defenestrator/data/state` (`usage.jsonl`, `events.jsonl`, `history.jsonl`).
  `~/.local/state/defenestrator` is the pre-cutover copy and can be deleted.
- Board: Grafana `/d/defenestrator` (provisioned from homelab, source in the repo's
  `deploy/grafana`). Logs: `docker logs defenestrator`. Options (quiet hours, models, dry run)
  are environment variables in the homelab compose file; see the repo README.
