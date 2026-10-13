# Phone access

Several phone clients are set up side by side, to compare; each reaches agents a
different way. The NUC side of the server-backed ones lives in `~/homelab`, one stack
each. Paseo, Omnigent's NUC host, Orca and Agent Canvas are host containers
(`~/homelab/host-home`): they run as you in the NUC's real home, so their agents get this
repo's config and the NUC's own logins exactly as a shell there would. The host side of
the herdr clients and the Macs' Paseo daemons is here. `.chezmoiscripts/run_once_after_60-phone.sh.tmpl`
sets up the host side once per host; every script it runs is idempotent and safe to re-run.

| App | Drives | Reaches the NUC by | Macs | Push |
|---|---|---|---|---|
| Heeler | the panes in herdr (terminal + composer) | SSH over WireGuard | yes, SSH | Blocked/Done, via its E2EE relay |
| herdr web UI (PWA) | the panes in herdr (chat view per agent, pi included, + terminal) | `https://herdr.<domain>` (homelab `herdr-web`) | added as SSH "remote PCs" from the NUC | web push |
| Paseo | its own daemon's agents (chat, pi over RPC) | our relay (`paseo-relay.<domain>`, a sidecar of the homelab `paseo` stack) over WireGuard: the NUC and every Mac pair by QR; `paseo.<domain>` direct for the NUC | yes, relay | yes |
| Omnigent | the Omnigent server's sessions (web view) | `https://omnigent.<domain>` | as hosts (`omni host enable`) | foreground only |
| Orca IDE | an Orca runtime's worktrees (chat or terminal) | `wss://orca.<domain>` (homelab `orca`) | via the Orca desktop app | yes |
| OpenLens | opencode only (chat) | `https://opencode.<domain>`, user `opencode` + server password | an `opencode serve` | no |
| droidtty | the panes in herdr | its bridge, `@droidtty/cli` (not installed: inside the npm cooldown until 2026-10-19) | its bridge | yes |

AgentBox has no phone client: its boxes appear as spaces in the NUC's herdr, so Heeler
and the herdr web UI reach them. Claude Code's Remote Control, on for every session, also
puts any `claude` in the Claude iOS app.

Agents started in Paseo, Omnigent, Orca or OpenCode live in that tool, so only it sees
them (Paseo's Import session can continue a Claude, Codex, OpenCode or pi conversation;
quit it in herdr first). Check a host with `herdr plugin list` and `paseo daemon status`.

## Heeler

[Heeler](https://github.com/ZingerLittleBee/Heeler) is a native iOS app for herdr,
open source (AGPL) and early. Its herdr plugin shows the Pairing Code and sends the
pushes through the developer's relay, which only sees ciphertext. It is pinned
like any other plugin ([plugins.md](plugins.md)); bump the commit by hand.

Once per host, with the phone: in the herdr window attached to that host, run
`herdr plugin action invoke heeler.pair` (NUC: `herdr --session homelab plugin
action invoke heeler.pair`), check the addresses the phone can reach, and scan the
QR. The NUC's herdr runs as the `homelab` session, which the code does not carry:
set the host's herdr Session to `homelab` in the app.

## Paseo

[Paseo](https://paseo.sh) runs Claude Code, Codex, OpenCode and pi behind a daemon
and drives them from its iOS, desktop, web and CLI clients. `paseo-setup` gives
every host the same shape:

- **An always-on daemon**: a launchd agent on the Mac (the desktop app attaches to
  it). Macs only: the NUC's daemon is the homelab's `paseo` host container, on the
  same `~/.paseo`, with the NUC's `127.0.0.1:6767` published for `ssh://nuc` (that
  daemon has a password: enter it in the host's settings in the desktop app). It runs through
  `zsh -c`, which reads `.zshenv`, so the agents it spawns get PATH and the `PI_*`
  settings. It restarts only when its version, service or a restart-only setting
  changes, since a restart interrupts running agents.
- **Localhost only, no password.** The phone comes in through the relay; the
  desktop app reaches other hosts over SSH (Settings, Add host, Remote SSH,
  `ssh://nuc`), which expects a daemon on the remote's `127.0.0.1:6767`.
- **Models.** It owns `agents.providers` in `~/.paseo/config.json`, adding
  `claude-sonnet-5-5` where Paseo's built-in Claude list lacks it.

Once per host, with the phone: scan the QR from `paseo daemon pair` (it points at our relay, never relay.paseo.sh) in the
app's Add host. The QR is a standing grant to drive that host's agents. Each agent
CLI must be signed in on the host first.
