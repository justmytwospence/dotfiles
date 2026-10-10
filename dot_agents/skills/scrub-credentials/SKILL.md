---
name: scrub-credentials
description: "Mask credentials in this session's on-disk chat log once you are done with them. Use when an API key, token, password or private key has appeared in the conversation (pasted by the user, printed by a command, read from a file) and the work that needed its value is finished: run `agent-scrub done`."
---

# Scrub credentials

Every harness writes the whole conversation to disk in plain text (Claude Code
`~/.claude/projects`, Codex `~/.codex/sessions`, pi `~/.pi/agent/sessions`, opencode
`opencode.db`), so a credential that passed through the session stays there. You decide when
it can go.

## When

Run it once you no longer need the value of any credential in this conversation: the key is
saved where it belongs (a secrets file, a keychain, an env file the user keeps), the command
that needed it has run, the user has rotated it, or the task moved on. Not while a step still
needs the value, and not for credentials you never saw. If several appeared, wait until you
are done with all of them, or run it again later.

## How

```sh
agent-scrub done
```

It finds this session from the environment (`CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID`,
`OPENCODE`, `PI_SESSION_FILE`), finds the credentials in its log with gitleaks and the values
of the credentials this machine holds, and masks each one in place with `*` (vendor prefixes
such as `ghp_` stay). It prints counts and rule names, never values. `--dry-run` reports
without changing anything.

Afterwards:

- Do not repeat a value: anything written after the scrub is back on disk. If you must write
  one again, run `agent-scrub done` again when finished.
- The scrub changes the log on disk, not your context. A resumed or forked session sees the
  masks; you still see the values for the rest of this session (opencode re-reads its database,
  so there they are gone at once). Say so if the user expects otherwise.
- Tell the user in one line what was masked (the counts the command printed).
