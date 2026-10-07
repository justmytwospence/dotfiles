# Phone access

Two iOS apps, for different jobs. `.chezmoiscripts/run_once_after_60-phone.sh.tmpl`
sets up the host side once per host; every script it runs is idempotent and safe
to re-run by hand.

| | Heeler | Paseo |
|---|---|---|
| For | the agents running in herdr, on every host at once | starting and steering agents in a chat UI |
| Shows | an agent console sorted by who needs you, live terminals, a composer | a chat with tool cards and approvals |
| Reaches a host by | SSH (WireGuard for the Mac and NUC) | Paseo's end-to-end encrypted relay |
| Pushes | Blocked and Done, end-to-end encrypted | agent finished or needs input |
| Host side | a herdr plugin pinned in `pins.tmpl`; `heeler-setup` prints pairing | `paseo-setup` (Macs, exe, Paseo fleet) |

Agents started in Paseo live in Paseo's daemon, so only Paseo sees them (its
Import session can continue a Claude, Codex or OpenCode conversation; quit it in
herdr first). Claude Code's Remote Control, on for every session, also puts any
`claude` in the Claude iOS app. Check a host with `herdr plugin list`
and `paseo daemon status`.

## Heeler

[Heeler](https://github.com/ZingerLittleBee/Heeler) is a native iOS app for herdr,
open source (AGPL) and early. Its herdr plugin shows the Pairing Code and sends the
pushes through the developer's relay, which only sees ciphertext. It is pinned
like any other plugin ([plugins.md](plugins.md)); bump the commit by hand.

Once per host, with the phone: in the herdr window attached to that host, run
`herdr plugin action invoke heeler.pair` (NUC: `herdr --session homelab plugin
action invoke heeler.pair`), check the addresses the phone can reach, and scan the
QR. The NUC's herdr runs as the `homelab` session, which the code does not carry:
set the host's herdr Session to `homelab` in the app. An exe.dev VM cannot pair by
QR (its sshd uses its own host key and an `authorized_keys` exe.dev manages): add
it by hand (`<vm>.exe.xyz`, port 22, user `exedev`, Device Key) and authorize the
Device Key from the Mac with `ssh exe.dev ssh-key add '<key line>'`.

## Paseo

[Paseo](https://paseo.sh) runs Claude Code, Codex, OpenCode and pi behind a daemon
and drives them from its iOS, desktop, web and CLI clients. `paseo-setup` gives
every host the same shape:

- **An always-on daemon**: a launchd agent on the Mac (the desktop app attaches to
  it), a systemd user service on Linux, installed from npm. It runs through
  `zsh -c`, which reads `.zshenv`, so the agents it spawns get PATH and the `PI_*`
  settings. It restarts only when its version, service or a restart-only setting
  changes, since a restart interrupts running agents.
- **Localhost only, no password.** The phone comes in through the relay; the
  desktop app reaches other hosts over SSH (Settings, Add host, Remote SSH,
  `ssh://nuc`), which expects a daemon on the remote's `127.0.0.1:6767`.
- **Models.** It owns `agents.providers` in `~/.paseo/config.json`, adding
  `claude-sonnet-5-5` where Paseo's built-in Claude list lacks it.

Once per host, with the phone: scan the QR from `paseo daemon pair --relay` in the
app's Add host. The QR is a standing grant to drive that host's agents. Each agent
CLI must be signed in on the host first.
