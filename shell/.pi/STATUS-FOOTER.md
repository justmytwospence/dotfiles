# Personal Pi footer

`agent/extensions/agent-status.ts` replaces only Pi's footer using its public API.
It leaves the editor, Vim mode, working indicator, task widgets and tool rendering
alone. It uses Pi's current theme, without background color blocks or animation.
The MCP status uses a flat Nerd Font plug (U+F1E6), inheriting the status text color;
it needs Nerd Font symbol support in the terminal. Other status text is preserved.

## Activation and controls

Restart Pi once after replacing the old `agent-status.ts`: the old version did
not clean up its refresh timer on reload. Subsequent edits support `/reload`.
The `~/.pi/agent/extensions/agent-status.ts` symlink points here.
`agent/pi-cc-extensions.json` disables only the CC-style package's competing footer;
its tool rendering and other features remain enabled. That config is also linked
at `~/.pi/agent/pi-cc-extensions.json`. Without it, CC-style can replace this footer
after startup or reload.

- `/status on`: custom footer, limits for the active provider only (default).
- `/status all`: also keep the other subscription account's limits visible
  (Claude acct on Codex, Codex acct on Claude, both on other providers).
- `/status native`: restore Pi's built-in footer immediately.
- `/status` or `/status details`: show detailed measurements and explain sources.

The selection persists in the session without entering model context. New sessions
start with the custom footer. Native mode still maintains the existing terminal
state integrations and cached account refresher.

## Layout

1. Project and branch, with words such as `modified` and `2 ahead`; model and
   labeled reasoning level on the right. Waiting/errors take priority.
2. `Context 32% used` with a gauge, and `Est. session cost $35.73`.
3. Provider/account limits explicitly labeled as percent **used**, with reset
   countdowns when supported.
4. Other extensions' status notices, only when present. Notices wrap rather than
   disappearing at the right edge. Existing task widgets are not duplicated.

Cache reuse, raw token counts, Git line counts, OAuth details, age and compaction
counts are available through `/status details`, not crowded into the footer.

Rows shorten and drop lower-priority segments to fit actual terminal cell width.
Model/context and the most-used quota win over secondary statistics. At extremely
small widths any remaining text is safely truncated. Colors come from the active
Pi theme; warnings start at 70% used, errors at 90%. No fresh-looking gauge is drawn
for stale account data.

## What the numbers mean

- **Context:** Pi's `getContextUsage()` estimate, including its actual model window.
  `unknown` is not zero; this can occur immediately after compaction.
- **Cache reuse (details):** the last measured assistant prompt on the current branch/model:
  `cacheRead / (input + cacheRead + cacheWrite)`. It does not promise that the next
  request will hit a cache. Switching models clears the reading until measured.
- **Est. session cost:** reported token-price estimate, not a subscription charge or invoice.
  Whole-session totals include assistant, tool, compaction, branch-summary and
  standalone usage records (including warming). Like Pi's native footer, the
  totals include recorded abandoned branches. Unreported external-agent usage
  cannot be counted. OAuth describes authentication, not billing.
- **Tracked Git changes (details):** all uncommitted tracked changes against HEAD, not edits attributed to
  this agent. Untracked files affect the dirty mark but not line counts.
- **Claude acct:** reads the shared Claude Code OAuth usage cache at
  `${CLAUDE_STATUSLINE_CACHE_DIR:-${XDG_CACHE_HOME:-~/.cache}/claude-statusline}/oauth-usage.json`.
  The Claude Code account may differ from Pi's account. Model-scoped weekly limits
  use their API labels, not a hardcoded model list. Percentages are percentage
  points; 0.5 is 0.5%, not 50%.
- **Codex acct:** ChatGPT-plan limits from `GET https://chatgpt.com/backend-api/wham/usage`,
  the endpoint Codex CLI's `/status` uses. Authenticated with Pi's own `openai-codex`
  OAuth login (via `modelRegistry.getApiKeyForProvider`, so Pi handles refresh) and
  the account id in that token, so it always describes the account Pi bills.
  The URL is fixed; the token is never sent anywhere else. Named pools in
  `additional_rate_limits` (for example a reserve model) keep their API names.
  Polled at most every 5 minutes, and at most every minute after a turn or model
  switch; only while a Codex model is active (or `/status all`). `x-codex-*`
  response headers, exposed only on the SSE transport (Pi defaults to WebSocket),
  update the main windows in between. No model call is made. Failures keep the
  last reading, which then shows as stale.
- **stale:** cache/header snapshot is at least ten minutes old or its reset time
  has passed. Never assume the provider reset a quota to zero without fresh data.
- **extra:** shared Claude account extra usage enabled/disabled state. An old spent
  pool is not an active warning when extra usage is off.

Other providers get the common session rows, without invented quota information.

## Performance and lifecycle

Rendering performs no filesystem, subprocess or network operations. Git is fetched
asynchronously on startup, settlement and branch changes, with a three-second
minimum ordinary refresh interval. A 15-second clock refreshes idle state; shared
quota reads/refreshes run at most once per minute ordinarily. The existing
`~/.local/bin/agent-status` script owns background Claude-cache refresh and its
cross-process lock; the footer never reads Claude credentials. The Codex usage
request is an in-process `fetch` with a five-second timeout, aborted on shutdown
or reload.

Timers, Git subscriptions and direct child processes are cleaned up on shutdown,
reload and session replacement. Generation checks reject late asynchronous work.
Print, JSON and RPC modes do not start footer work. The old tmux state bridge and
conditional Herdr usage update remain in place.

## Verification

Requires an installed Pi and `tsc` on PATH, without installing new dependencies:

```sh
node shell/.pi/tests/check-status-footer.mjs
```

The runner locates an npm or Homebrew Pi installation, or accepts `PI_PACKAGE_DIR`.
It typechecks against that Pi's real types and runs Node tests. Tests cover usage
accounting, provider switches, unknown/stale data, the Codex usage response and
header merging (with `fetch` and credentials stubbed), Git porcelain, ANSI/CJK display
widths 1–240 in both built-in themes, status preservation, native fallback,
reload/resume, cleanup, and loading with Pi's actual extension loader. They do not
make model or network requests or access real credentials. The lifecycle fixture uses a temporary
home and non-Anthropic model to avoid invoking the real account refresher.

Set `STATUS_PREVIEW=1` for sample layouts at 40, 60, 80, 120 and 160 columns.

For the real fullscreen TUI smoke test on macOS/Linux:

```sh
python3 shell/.pi/tests/status-footer-pty.py
```

This starts Pi inside a disposable home with no credentials or model tools. It
loads this footer together with the installed `pi-cc-extensions`, using the real
footer-ownership config, plus a fake MCP status (no server connection). Set
`PI_CC_PACKAGE_DIR` if CC-style is installed outside Pi's default npm directory.
The test verifies that CC-style is active while this footer and its monochrome MCP
plug survive startup and reload. Only slash commands are sent. It checks light/dark startup, native fallback,
120-to-40-column resizing, reload without duplicate rows, and clean exit, and
asserts that the agent conversation stays empty. The harness supplies a controlling
terminal and records lifecycle traces for failures. A deterministic regression
check covers successful exit between consecutive process polls. Set
`STATUS_FOOTER_BASELINE=1` to run startup, resize, reload and exit checks with only
the native footer as a control.
