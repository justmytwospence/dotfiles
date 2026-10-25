---
name: agent-access
description: "Get a login, password, API key or TOTP code from the user's Bitwarden vault with Bitwarden Agent Access (`aac`), one approved credential at a time. Use when a command, script or sign-in needs a credential the user keeps in Bitwarden. Prefer `aac run`, which injects the secret into a child process's environment so it never enters the conversation."
---

# Bitwarden Agent Access

`aac` asks the user's Mac for one vault item over an end-to-end encrypted tunnel. On the Mac,
`aac-touchid` runs in the background and shows each request as a system Touch ID sheet naming
you, your machine, the item, the fields being released and your reason; the user approves with
a fingerprint (or Apple Watch) or cancels. You never get the vault, only the item they
approve, and nothing you can type or click approves a request.

First run `command -v aac`. If it is missing, agent access is not set up where you are running
(for example inside a container); tell the user and do not look for credentials another way.
Never run `bw` yourself, and never read `~/Library/Application Support/aac-touchid`.

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
- Always pass `--domain "<item> | <agent> | <reason>"` (or `--id` the same way). The Mac's
  Touch ID sheet shows exactly these three, one per line:
  - `<agent>`: who you are, `<harness> · <project>`, e.g. `pi · homelab` or `claude · uplft`
    (project = the herdr space or repo name). No device name; the sheet adds it.
  - `<item>`: the host the login is for, e.g. `github.com` (see Finding the item).
  - `<reason>`: a few words, under 80 characters, e.g. `check that gh is logged in`.
  Also say the same line in the session.
- The command waits while the user decides (Touch ID times out after 60 s). The first request
  after the Mac restarts or idles 8 h also shows a master-password dialog there; use
  `--timeout 240` on such a first request. Never ask the user to type the master password
  into this conversation.

In Claude Code, `aac` runs outside the sandbox, so Claude Code asks the user before it runs;
that prompt and the Touch ID sheet are both expected.

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
aac run --domain "db.example.com | pi · homelab | open psql" --env PGUSER=username --env PGPASSWORD=password -- psql -h db.example.com

# Every field as AAC_USERNAME, AAC_PASSWORD, AAC_TOTP, AAC_URI, AAC_NOTES, ...
aac run --domain example.com --env-all -- ./deploy.sh

# A program that wants the secret on stdin, without putting it in argv
aac run --domain registry.example.com --env U=username --env P=password -- \
  sh -c 'printf %s "$P" | docker login registry.example.com -u "$U" --password-stdin'

# A specific item when several share a domain (ask the user for its item id)
aac run --id <vault-item-id> --env TOKEN=password -- ./script.sh
```

Fields: `username`, `password`, `totp`, `uri`, `notes`, `domain`, `credential_id`. API keys are
usually stored as the item's password, sometimes in notes.

## Finding the item

A host is matched on the hosts of login URIs, deterministically; never by part of a name or URI:

1. Logins with a URI on exactly that host, or named exactly that host (`www.` ignored).
2. Only if there are none, logins with a URI on a subdomain of it (`google.com` finds
   `accounts.google.com`). A subdomain never finds its parent: `api.openai.com` does not find
   a login saved for `openai.com`.

So ask for the host the user signs in on, usually the service's main domain (`openai.com`,
`github.com`), not the API host your command talks to. A URL also works (reduced to its host),
but a bare host is clearer on the sheet. Something that is not a host (`GitHub`) falls back to
`bw`'s name search; prefer the host.

If the matching tier holds several logins, the request is denied as ambiguous (exit 4); ask the
user for the item id and use `--id`. If nothing matches (exit 4, not found), do not guess other
spellings in a loop: try the main domain once, then ask the user.

## Create a login or add 2FA

For a service the user asked you to sign up for, the Mac can create the login and generate its
password, then store its 2FA seed. Each write is its own Touch ID sheet. Both go in the item
part of `--domain`, before `| <agent> | <reason>`:

```bash
# Create a login with a generated passphrase and use it. Options: user=, url=<full url>.
# A host-like name sets the URI to https://<name>.
aac run --domain "new:status.example.com user=admin | pi · homelab | create Uptime Kuma admin" \
  --env U=username --env P=password -- ./signup.sh

# Store the TOTP seed the service shows at enrollment and get the current code to confirm it
aac run --domain "totp:status.example.com secret=<BASE32> | pi · homelab | enroll 2FA" \
  --env CODE=totp -- ./confirm-2fa.sh
# or: totp:<item> uri=otpauth://totp/...?secret=...
```

- Password format: leave it to the default, a passphrase like
  `Violet-Shrug0-Broken-Lantern-Mosaic-Thirsty` (6 capitalized words, `-`, one digit), unless the user says otherwise or the site rejects it.
  Then use `words=3-20` for a longer passphrase, or `length=12-128` (default 24) and/or
  `symbols=no` for a random password. `words=` cannot be combined with the other two.
- `new:` is refused if an item with that name or a login for that host already exists. The
  login goes in the vault folder `Agent-created`. Later, read it normally (`--domain <item>`).
- `totp:` works only on a login in `Agent-created` without a seed, and never overwrites one.
  `<item>` is one word (domain, name without spaces, or item id). It returns the username and
  current code only. HOTP is not supported.
- The seed sits in `aac`'s argv while it runs: pass it straight from where you read it, and
  never print, store or repeat it. If a sheet is refused, do not retry within 60 s.

## Errors

| Exit | Meaning | Do |
|---|---|---|
| 1 | General error | Read stderr |
| 2 | Connection failed | The relay is unreachable or the Mac is asleep or offline; tell the user |
| 3 | Handshake failed, bad pairing code, or no answer in time | Ask the user whether they saw a sheet. If the pairing is stale, clear with `aac connections clear sessions` and ask for a new `aac-touchid pair` code |
| 4 | Denied, not found, ambiguous, or vault locked | Ask the user; do not repeat it. A repeat within 60 s is refused without a prompt. They can check `aac-touchid status` on the Mac |
| 5 | Fingerprint mismatch | Stop and tell the user; do not retry |
