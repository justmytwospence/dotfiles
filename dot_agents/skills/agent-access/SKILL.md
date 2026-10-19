---
name: agent-access
description: "Get a login, password, API key or TOTP code from the user's Bitwarden vault with Bitwarden Agent Access (`aac`), one approved credential at a time. Use when a command, script or sign-in needs a credential the user keeps in Bitwarden. Prefer `aac run`, which injects the secret into a child process's environment so it never enters the conversation."
---

# Bitwarden Agent Access

`aac` asks the user's trusted device for one vault item over an end-to-end encrypted tunnel.
The trusted device (a Mac running `aac listen` with the vault unlocked) shows each request, and
the user approves or denies it there. You never get the vault, only the item they approve.

Adapted from Bitwarden's example skill (`bitwarden/agent-access`,
`examples/skills/agent-access`), corrected for aac 0.11 and changed to keep secrets out of
context.

## Rules

- Prefer `aac run`. It passes the secret to a child process through environment variables,
  and nothing is written to stdout, disk or this conversation.
- Never print, echo, log or write a credential to a file, and never put one in a command line
  (`ps` shows argv). Reference the variable inside the child (`sh -c '... "$PGPASSWORD"'`).
- Fetch a credential into context (`aac --domain ... --output json`) only when nothing else
  works, for example typing it into a browser form. Tell the user first. Afterwards load the
  `scrub-credentials` skill and run `agent-scrub done` once the value is no longer needed.
- Ask for exactly what the task needs: one domain or item ID, the fields the command uses.
- A request waits up to 120 s (`--timeout`) for the user to approve. Tell the user what you
  requested and why, so they know what they are approving.

## Check for a connection

```bash
aac connections list
```

If there is no cached connection, ask the user to run `aac listen` on their Mac and give you
the pairing code it shows (`ABC-DEF-GHI`, valid 5 minutes) or a PSK token. Pair while making
the first request; the connection is cached in `~/.access-protocol/` afterwards:

```bash
aac run --token <CODE> --domain example.com --env API_TOKEN=password -- ./script.sh
```

Do not keep a pairing token anywhere after use. With several cached connections, pick one with
`--session <fingerprint-prefix>` from `connections list`.

## Run a command with a credential

```bash
# Map fields to the variables the program reads
aac run --domain db.example.com --env PGUSER=username --env PGPASSWORD=password -- psql -h db.example.com

# Every field as AAC_USERNAME, AAC_PASSWORD, AAC_TOTP, AAC_URI, AAC_NOTES, ...
aac run --domain example.com --env-all -- ./deploy.sh

# A program that wants the secret on stdin, without putting it in argv
aac run --domain registry.example.com --env U=username --env P=password -- \
  sh -c 'printf %s "$P" | docker login registry.example.com -u "$U" --password-stdin'

# A specific item when several share a domain
aac run --id <vault-item-id> --env TOKEN=password -- ./script.sh
```

Fields: `username`, `password`, `totp`, `uri`, `notes`, `domain`, `credential_id`. API keys are
usually stored as the item's password, sometimes in notes. Use the bare domain (`github.com`,
not `https://github.com/login`).

## Errors

| Exit | Meaning | Do |
|---|---|---|
| 1 | General error | Read stderr |
| 2 | Connection failed | The listener is not running or the relay is down; ask the user to start `aac listen` |
| 3 | Handshake failed, bad pairing code, or timed out waiting for approval | Ask the user whether they saw the request. Only if they did not, and the listener is running, clear with `aac connections clear sessions` and ask for a new pairing code |
| 4 | Not found, or denied | Ask the user; do not repeat a denied request |
| 5 | Fingerprint mismatch | Stop and tell the user; do not retry |
