# Coding agents

Four harnesses run side by side, each in its own herdr pane: **Claude Code**,
**Codex**, and the multi-model **pi** and **opencode**. A skill, an instruction or
an MCP server is written once here and reaches all four.

- **Skills** live in `~/.agents/skills`, the cross-vendor directory Codex, pi
  and opencode read with no configuration. Claude Code reads only
  `~/.claude/skills`, which is a symlink to it (`dot_claude/symlink_skills`).
  Personal skills are authored in `dot_agents/skills/<name>/` and written there by
  chezmoi; third-party ones come from `~/.local/bin/skills-install`, which carries
  the source list and is rerun by chezmoi whenever that list changes. Re-running it
  by hand is also how they update.
- **Instructions**: `dot_agents/AGENTS.md` is the single source. Codex
  (`~/.codex/AGENTS.md`), Claude Code (`~/.claude/CLAUDE.md`), pi
  (`~/.pi/agent/AGENTS.md`) and opencode (`~/.config/opencode/AGENTS.md`) read it
  through symlinks to `~/.agents/AGENTS.md`. Each tool loads only its own global
  path, so edit the one file. Nothing else may write instructions or skills:
  Codex desktop's "import from other agents" sync is pinned off (`CODEX_PINS` in
  `lib/agent_settings.py`), along with the Claude Cowork plugins it enabled, and
  `85-retired` removes what it had already copied in.
- **MCP**: `dot_config/mcp/mcp.json` declares the set. pi reads it through the
  `~/.pi/agent/mcp.json` symlink; `opencode.jsonc.tmpl` renders opencode's `mcp`
  block from it; `modify_private_dot_claude.json` and
  `dot_codex/modify_private_config.toml` merge it into `~/.claude.json` (minus
  context7, which the context7 plugin provides) and `~/.codex/config.toml`, leaving
  every other server and setting alone. Edit mcp.json, `chezmoi apply`. A server
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
- **herdr**: `herdr integration install <harness>` lets herdr report each agent's
  state ([herdr.md](herdr.md)).
- **Orca** (`stablyai/orca/orca` cask) writes its own hooks into Claude Code's and
  Codex's live hook files and a status plugin into `~/.config/opencode/plugins`;
  the merges keep them. Its skills (`orca-cli`, `orchestration`) come from
  skills-install like any other. Don't use Orca's own skill installer
  (Settings or `orca skills install`): it adds per-agent links that duplicate
  `~/.agents/skills`.
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

## Worktrees

Every git worktree lives in `<project>/.worktrees/<name>`, inside the main
checkout and hidden by the global git ignore, so any harness, herdr, Orca or a
shell finds it with `git worktree list` and can open or remove it.
`~/.local/bin/worktree` is the canonical way to make one: it creates the checkout
(copying `.worktreeinclude` files), opens it as a grouped herdr child space or a
tmux window with pi started in it, and prints the path. Each tool that can create
worktrees is routed there:

| Creates worktrees | How it lands in `.worktrees/` |
|---|---|
| shell, agents, herdr `prefix+G` | `worktree new` (the `AGENTS.md` rule; nothing stops a bare `git worktree add`) |
| pi `/worktree`, pi-subagents `worktree: true` | call `worktree` |
| opencode `/worktree` | calls `worktree` |
| Claude Code `-w`, `EnterWorktree`, `isolation: "worktree"`, Claude Desktop sessions | WorktreeCreate/WorktreeRemove hooks run `worktree hook claude-*`; a SubagentStop hook removes finished subagent checkouts that hold no work (`worktree clean` sweeps leftovers) |
| Paseo | the paseo-machine0 skill runs `worktree new` on the spoke and starts the agent with `--cwd`. Paseo's own worktree isolation goes unused: it can only use `~/.paseo/worktrees/<hash>/`, and it refuses to manage a checkout whose real path leaves that root, so a link (below) does not work for it |
| Orca | Settings > Workspace: Workspace Directory `.worktrees` (relative paths resolve per repo), Nest Workspaces off. Orca keeps settings in its own database, so set this once per Mac by hand |
| OpenCode Desktop "New workspace" | `worktree.directory` in `opencode.jsonc`, which takes effect with opencode v2. 1.18 ignores it and uses `~/.local/share/opencode/worktree/<project id>/`; a link there works but makes Desktop list each checkout twice, so use `/worktree` until v2 |
| Codex app and CLI | off: Codex-managed worktrees go to `$CODEX_HOME/worktrees`, detached, with no setting to move them, so `features.worktrees = false` is pinned (`CODEX_PINS`) |
| herdr sidebar "New worktree" | linked: herdr has one global `[worktrees] directory` and puts a repo's checkouts in `~/.herdr/worktrees/<repo>/`, which `worktree link` makes a symlink to `<repo>/.worktrees` |

**Links.** A tool with one global worktree root that still gives each repo its
own directory under it can be pointed at `.worktrees` by making that directory a
symlink: git resolves it and records the real path, so the checkout is in
`.worktrees` for every other tool. `worktree link --all` does this for herdr for
every repo in `~/Projects` and `~/dotfiles` on each `chezmoi apply`
(`45-worktree-links`), `worktree new` links the repo it works in, and a global
git hook (`hook.worktree-link` in `~/.gitconfig`, git 2.54+) links each fresh
clone. A directory that already holds checkouts is left alone and reported.

Still outside `.worktrees`, until upstream adds a per-repo location: Codex's
managed worktrees (off; [openai/codex#10599](https://github.com/openai/codex/issues/10599)),
Paseo's worktree isolation (unused), and OpenCode Desktop before v2 (unused).

Branch names stay each tool's own (`worktree-<name>` from Claude Code,
`subagent/...` from pi-subagents, Orca's generated names); `worktree open`,
`path` and `rm` take a branch, a directory name or a path, so they work on any of
them.

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
