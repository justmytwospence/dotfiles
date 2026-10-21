# Phone access

Several phone clients are set up side by side, to compare; each reaches agents a
different way. The NUC side of the server-backed ones lives in `~/homelab`, one stack
each. Paseo, Omnigent's NUC host and Agent Canvas are host containers
(`~/homelab/host-home`): they run as you in the NUC's real home, so their agents get this
repo's config and the NUC's own logins exactly as a shell there would. The host side of
the herdr clients and the Macs' Paseo daemons is here. The converge script's `paseo` section (`home/.chezmoitemplates/converge/paseo.sh`)
runs `paseo-setup` when it or Paseo changes; every step it takes is idempotent and safe to re-run.

| App | Drives | Reaches the NUC by | Macs | Push |
|---|---|---|---|---|
| herdr web UI (PWA) | the panes in herdr (chat view per agent, pi included, + terminal) | `https://herdr.<domain>` (homelab `herdr-web`) | added as SSH "remote PCs" from the NUC | web push |
| Paseo | its own daemon's agents (chat, pi over RPC) | our relay (`paseo-relay.<domain>`, a sidecar of the homelab `paseo` stack) over WireGuard: the NUC and every Mac pair by QR; `paseo.<domain>` direct for the NUC | yes, relay | yes |
| Omnigent | the Omnigent server's sessions (web view) | `https://omnigent.<domain>` | as hosts (`omni host enable`) | foreground only |
| OpenLens | opencode only (chat) | `https://opencode.<domain>`, user `opencode` + server password | an `opencode serve` | no |

AgentBox has no phone client: its boxes appear as spaces in the NUC's herdr, so the
herdr web UI reaches them. Claude Code's Remote Control, on for every session, also
puts any `claude` in the Claude iOS app.

Agents started in Paseo, Omnigent or OpenCode live in that tool, so only it sees
them (Paseo's Import session can continue a Claude, Codex, OpenCode or pi conversation;
quit it in herdr first). Check a host with `herdr plugin list` and `paseo daemon status`.

## herdr web UI (PWA)

The herdr web UI is the phone client for existing herdr panes, including AgentBox
spaces on the NUC. Open `https://herdr.spencerboucher.com` over WireGuard; the
server-side setup lives in the homelab `herdr-web` stack. Macs are separate SSH
remote PCs added there, not new copies of their agents.

Its NUC host reads only the NUC's default herdr session (`~/.config/herdr/herdr.sock`).
Every laptop's saved `NUC` machine targets that session (docs/herdr.md), so panes opened
on the NUC from any Mac appear there whether or not that Mac is on. Don't start a
named session on the NUC for agent work: the web UI would not see it.

### iPhone notifications

On iOS 16.4 or newer, open the HTTPS site in Safari, use **Share > Add to Home
Screen**, then launch that Home Screen app. Enable/subscribe to notifications
from inside the PWA and accept the iOS permission prompt; a Safari tab alone is
not the iPhone background-push setup. Check the PWA's blocked/done subscriptions
and iOS **Settings > Notifications**, including Focus, then test an agent event
while the PWA is backgrounded. Permission alone does not create a subscription.

The web server and host agent-state integration must remain running. Web Push can
arrive with the PWA closed, but delivery/timing is OS- and network-dependent;
WireGuard is still needed to open the private site and interact with the pane.
This replaces Heeler's relay alerts, not its native Live Activities. Platform
requirements: [WebKit's Home Screen Web Push guide](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).

### Rich dialogs and client limits

Chat is convenient for transcripts, prompts and supported native questions.
Pi's arbitrary rich `ui.custom` dialogs are terminal components, not a portable
web/RPC form schema. If a question, diff review or other custom dialog is not
usable in chat, open **Terminal** on the **same live pane** and answer it there;
do not import the conversation or start a second agent. A blocked/done alert is
not itself the dialog. Terminal input (arrows, Enter, Esc, typing) goes to that
pane's TUI, so ensure the right pane is selected.

**Resize caveat:** the phone keyboard, orientation and terminal attachment can
change the shared PTY geometry and affect an attached desktop. Chat switching
does not guarantee that the deployed terminal client propagates every resize.
If the dialog is clipped or stale, resize/reconnect the terminal view and check
its actual layout before submitting; use a desktop terminal if it still cannot
be operated. Terminal fallback is not native touch-dialog parity.

Paseo drives Pi over RPC: supported select/input/confirm questions can be mapped
to client dialogs, but arbitrary `ui.custom` components cannot. Its agents belong
to Paseo, not the herdr PWA. Claude's iOS Remote Control reaches Claude sessions,
not Pi's custom dialogs. OpenLens is OpenCode-only; Omnigent exposes
its own runtime/client capabilities, not a universal Pi extension-UI bridge.
Client support for multi-select, previews, notes and editing differs: use the
owning runtime's terminal when a required control is absent.

## Retired Heeler integration

Heeler is no longer installed or paired by dotfiles. A reviewed full apply runs
`home/.chezmoitemplates/converge/retired.sh` and `home/lib/retire_heeler.py`: native `herdr plugin uninstall heeler`
unregisters it globally and refreshes every running local session (including an
old `homelab` session) without stopping servers or panes. Cleanup then removes
its `~/.config/herdr/plugins/config/heeler`,
`~/.local/state/herdr/plugins/heeler` and `~/.local/bin/heeler-setup`
(config/state roots honor XDG overrides). Native-managed checkouts are not
deleted by glob, nor are local development repos touched.

SSH cleanup atomically removes only exact `heeler` / `heeler rsa` key comments,
plus `herdr-pairing:…:exp:…` bootstrap keys whose forced command identifies
Heeler's enrollment entrypoint. Other keys, comments, permissions and ownership
stay; manually enrolled keys without those markers need individual review.
Generic `herdr-pairing` keys are not automatically Heeler keys. Symlinked or
hard-linked `authorized_keys`, an existing pairing lock, native-uninstall
errors or rewrite failures stop cleanup with a nonzero result for retry; state
is retained on uninstall/rewrite failure. No broad SSH-key revocation is used.

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
