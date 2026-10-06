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
  every other server and setting alone. Edit mcp.json, `chezmoi apply`. Signing in
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
- **Claude subscription billing**: pi and opencode reach Claude through the
  Pro/Max subscription (pi-anthropic-auth, @ex-machina/opencode-anthropic-auth),
  but a request not shaped as Claude Code is billed per token to extra usage.
  Every subscription response names the pool that paid
  (`anthropic-ratelimit-unified-representative-claim`), so anthropic-billing-guard,
  loaded by pi and opencode, warns the moment one lands on `overage` and appends it
  to `~/.local/state/anthropic-extra-usage.log`. Claude Code's workflow cost
  warning stays on (its "Allow once" writes `skipWorkflowUsageWarning: true` into
  the live settings; delete it there).
- **Worktrees**: `~/.local/bin/worktree` is the one way checkouts get made, in
  `<project>/.worktrees/<branch>` (ignored by the global git ignore), opened as a
  grouped herdr child space or a tmux window with pi started in it. pi's and
  opencode's `/worktree`, Claude Code's WorktreeCreate/WorktreeRemove hooks
  (`claude -w`, `EnterWorktree`, `isolation: "worktree"`), herdr's `prefix+G` and
  pi-subagents' `worktree: true` all route through it, and a SubagentStop hook
  removes finished subagent checkouts that hold no work (`worktree clean` sweeps
  leftovers). Codex's managed worktrees are switched off (`codex features disable
  worktrees`, once per host). herdr's sidebar "New worktree" item still uses its
  global directory, and the `AGENTS.md` rule is the only guard against a bare
  `git worktree add`.
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

## Planning

Plan in a strong model, implement in a cheaper one, optionally with two models
planning the same task in parallel.

- **pi**: [pi-plan-mode](https://github.com/justmytwospence/pi-plan-mode). `/plan
  [task]` (or `shift+tab`) opens one full-screen planner: Settings (planners A and
  B, effort, scout models, time limit; saved to `~/.pi/agent/pi-plan-mode.json`,
  whose source is `private_dot_pi/private_agent/pi-plan-mode.json`), Tools (Jev
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
