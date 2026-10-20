---
name: agent-access
description: "Get a login, password, API key or TOTP code from the user's Bitwarden vault with Bitwarden Agent Access (`aac`), one approved credential at a time. Use when a command, script or sign-in needs a credential the user keeps in Bitwarden. Prefer `aac run`, which injects the secret into a child process's environment so it never enters the conversation."
---

# Bitwarden Agent Access

`aac` asks the user's Mac for one vault item over an end-to-end encrypted tunnel. On the Mac,
`aac-touchid` runs in the background and shows each request as a system Touch ID sheet naming
your device, the domain and the username; the user approves with a fingerprint (or Apple
Watch) or cancels. You never get the vault, only the item they approve, and nothing you can
type or click approves a request.

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
- Before or as you run the request, tell the user in one line what you requested and why,
  for example: "Requested the github.com login for `gh auth`; approve with Touch ID on your
  Mac." The sheet cannot show your purpose, so this line is how they decide.
- The command waits while the user decides (Touch ID times out after 60 s). The first request
  after the Mac restarts or idles 8 h also shows a master-password dialog there; use
  `--timeout 240` on such a first request. Never ask the user to type the master password
  into this conversation.

## Check for a connection

```bash
aac connections list
```

If there is no cached connection, ask the user to run `aac-touchid pair <name-of-this-machine>`
on their Mac and give you the code it prints (`ABC-DEF-GHI`, valid 5 minutes). Pair while
making the first request; the Mac shows a Touch ID sheet to accept the pairing, then one for
the request. The connection is cached in `~/.access-protocol/` afterwards:

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

# A specific item when several share a domain (ask the user for its item id)
aac run --id <vault-item-id> --env TOKEN=password -- ./script.sh
```

If several logins match a domain, the request is denied as ambiguous; ask the user for the
item id.

Fields: `username`, `password`, `totp`, `uri`, `notes`, `domain`, `credential_id`. API keys are
usually stored as the item's password, sometimes in notes. Use the bare domain (`github.com`,
not `https://github.com/login`).

## Errors

| Exit | Meaning | Do |
|---|---|---|
| 1 | General error | Read stderr |
| 2 | Connection failed | The relay is unreachable or the Mac is asleep or offline; tell the user |
| 3 | Handshake failed, bad pairing code, or no answer in time | Ask the user whether they saw a sheet. If the pairing is stale, clear with `aac connections clear sessions` and ask for a new `aac-touchid pair` code |
| 4 | Denied, not found, ambiguous, or vault locked | Ask the user; do not repeat it. A repeat within 60 s is refused without a prompt. They can check `aac-touchid status` on the Mac |
| 5 | Fingerprint mismatch | Stop and tell the user; do not retry |
