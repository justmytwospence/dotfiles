# Rex

Rex runs alongside Herdr; this setup does not migrate or retire Herdr or other tools.
The NUC runs a personal user service as `spencer`, listening only on the private Unix
socket `/run/user/1000/rex/server.sock`. Each Mac connects through its own launchd-supervised
SSH tunnel (`rex-nuc`) over the existing WireGuard network. There is no new network listener.
WireGuard, the existing SSH key and a trusted NUC host key are prerequisites. If the network
is down, launchd retries; the NUC sessions continue independently.

Local Mac sessions run on that Mac; NUC sessions run on the NUC. Sessions and their
processes stay on their originating host, not replicated between machines.

## Mac setup and connection

Install the Rex beta app manually from the vendor on each Mac. No public Homebrew Rex app
cask was found; the app and its native updater own the Mac server and CLI. Do not put beta
invitation links or credentials in Git. The managed PATH points to the app-owned CLI.

The managed CLI host is `nuc`. Once the tunnel and NUC service are available, test with:

```sh
rex -S nuc whoami --json
rex -S nuc ls --json
```

Check the returned server identity and location. For the GUI, use **Add Remote Host…**
once on each Mac and enter the absolute local socket path
`/Users/<your-user>/.local/state/rex/ssh/nuc.sock` (substitute your actual home directory).
CLI and GUI host synchronization is described differently in Rex's documentation, so do
not rely on the CLI declaration registering the GUI host. Verify a new remote session
with `hostname` and `whoami`.

For troubleshooting, check `launchctl print "gui/$(id -u)/com.spencerboucher.rex-nuc-tunnel"`
and `~/Library/Logs/rex-nuc-tunnel.log` on the Mac; on the NUC, check
`systemctl --user status rex.service` and `journalctl --user -u rex.service`. The NUC user
needs linger enabled (`loginctl enable-linger spencer`) for the service to survive logout.

## Typography

Rex uses JetBrains Mono at 14 pt with improved text contrast, matching Ghostty's font
family and base size. Rendering weight can still differ; per-pane manual zoom can also
change the apparent size. Check **Settings → Terminal → Typography** when comparing.

## Notifications

Pi 1.5 reports working, blocked, done and error states to Rex using OSC 7501.
The managed program-activity policy is:

| State | Tab indicator | macOS notification | Dock badge | Sound |
| --- | --- | --- | --- | --- |
| Working | Yes | No | No | No |
| Blocked | Yes | Yes | Yes | Yes |
| Error | Yes | Yes | Yes | Yes |
| Done | Yes | Yes | Yes | No |

Sound selections remain Rex's defaults or local choices. In Rex, inspect **Settings →
Notifications → Program Activity**. Rex documents system notifications as firing while
Rex is in the background; clicking one opens the program's tab. In macOS **System
Settings → Notifications → Rex Beta**, allow notifications, badges and sounds and choose
an alert style. These permissions are machine-local and may require consent; check Focus
if notifications are suppressed.

The readable matrix in `home/.chezmoidata/rex.json` becomes JSON-encoded Data in Rex's
native preferences. The helper preserves existing sound selections, unknown fields and
statuses, and unrelated preferences; it refuses malformed activity data rather than
replacing it. A successful managed-preferences check proves persisted settings, not that
the running app has refreshed or delivered a notification.

After landing, verify the settings panel and notification permissions. Test a background
local Pi question and completed turn, observing indicators, notifications, sounds and
click-to-tab behavior; then repeat with a NUC Pi session. Also test a NUC event while
viewing the local host. Whether Rex monitors an unselected host and routes notification
clicks across hosts is not yet verified; record those outcomes separately from storage
convergence.

## Keybindings

Press `Ctrl+B`, release it, then press the listed key. Uppercase letters mean Shift.
Herdr spaces correspond to Rex sessions; tabs and panes remain tabs and panes.

| Key after prefix | Action |
| --- | --- |
| `c` / `,` / `&` | New / rename / close session |
| `s` or `f` / `w` | Go to Anything / session switcher |
| `n` or `Ctrl+J` / `p` or `Ctrl+K` | Next / previous session |
| `Enter` / `Ctrl+Enter` | Priority program cycle / next attention needed |
| `:` / `S` / `R` / `b` | Command palette / settings / reload config / sidebar |
| `C` / `T` / `X` | New / rename / close tab |
| `Ctrl+N`, Shift+Right, Alt+L / `Ctrl+P`, Shift+Left, Alt+H | Next / previous tab |
| `"` / `%` | Split right / down |
| `h/j/k/l` / `H/J/K/L` | Focus / move pane left, down, up, right |
| `Ctrl+O` or `Ctrl+L` / `Ctrl+H` or Shift+Tab | Next / previous pane |
| `P` / `x` | Rename / close pane |
| `Ctrl+B` | Send a literal Ctrl+B to the terminal |

`Ctrl+B, Enter` visits unacknowledged blocked programs first, then unacknowledged
errors and completions, then other status-reporting programs in least-recently sampled
order. `Ctrl+B, Ctrl+Enter` visits only those unacknowledged attention states; it does
nothing when none remain. Both exclude the current pane and only include programs
reporting activity through OSC 7501.

Visit tracking is sampled when either shortcut runs: the current pane's attention
reports are acknowledged, but manual visits between shortcut presses can be missed.
A new status report re-arms attention, including a repeated report of the same state.
History is held in memory and resets when Rex reloads its configuration or restarts.
Local and NUC panes participate; empty shells without program status are excluded.

Each shortcut uses a short-lived Rex CLI bridge for inventory and pane focus, with
bounded connection and execution timeouts. The bridge selects the app through the
destination server so a remote session is never looked up on the local server.
Enable **Settings → Rex Server → Remote Control** in Rex; this permission stays
machine-local. Cross-host jumps require exactly one connected app with the same
device label, platform and app name as the originating app. Missing or ambiguous
matches fail rather than choosing another device.

App selection waits at most one second for a reply and is never automatically
retried. A failed or timed-out selection can leave the destination pane's server
focus changed, and a timed-out request may still complete later.

`Cmd+Enter` toggles fullscreen without a prefix. Pane movement is Rex's directional
move, which is not necessarily identical to Herdr's swap behavior.

`Ctrl+B, Ctrl+R` enters **navigation repeat mode**. No further prefix is needed:

| Key in repeat mode | Action |
| --- | --- |
| `n` or `Ctrl+J` / `p` or `Ctrl+K` | Next / previous session |
| `Ctrl+N`, Shift+Right, Alt+L / `Ctrl+P`, Shift+Left, Alt+H | Next / previous tab |
| `Ctrl+O` or `Ctrl+L` / `Ctrl+H` or Shift+Tab | Next / previous pane |
| `h/j/k/l` | Focus pane left / down / up / right |

`Ctrl+B, r` enters **resize mode**:

| Key in resize mode | Action |
| --- | --- |
| Arrow keys or `h/j/k/l` | Resize left / down / up / right by one cell |
| `Ctrl+H/J/K/L` | Resize left / down / up / right by five cells |

Both modes are exclusive: unrelated keys are suppressed instead of typed into the
terminal. Press Enter or Escape to exit. Navigation repeat preserves Herdr's
Ctrl+H/L pane cycling and Ctrl+J/K session navigation; those chords resize only in
resize mode. Modes persist explicitly until exited, unlike tmux's 700 ms repeat window.

Herdr-specific notification jump, worktree creation, file viewer, undo, copy mode,
last-pane, detach, help and numbered session selection remain
unmapped rather than being assigned unrelated actions. Remote sessions need the
same managed Rex config on the server where they run.

## Ownership and upgrades

Chezmoi owns the shared Lua bindings, the Mac CLI host declaration, the SSH tunnel and
launchd definition, the NUC service and pinned Linux binary. `home/.chezmoidata/rex.json`
contains the connection settings and the explicit Mac preference allowlist; the helper
writes only those typed keys, preserving other preferences. Preference changes take effect
on Rex's normal refresh or next launch. Identities, GUI host records, sessions, credentials
and app runtime state stay local and must not be captured in Git.

Apply does not restart a running Rex server or the Mac app. Changed Lua is validated and
reloaded locally when a server is already running; a changed tunnel definition reloads only
the tunnel job. A new NUC binary or service definition can therefore be installed while
the old server continues running: check the installed binary with `rex version` and the
running server separately with `rex --autostart=false server status --json`. At an
explicitly chosen safe time, after accounting for active sessions, restart the user service
with `systemctl --user restart rex.service` on the NUC and verify its status and version.
See [linux-packages.md](linux-packages.md) for pinning.

If a personal server was started outside systemd, apply refuses to take it over while
its socket exists. At a safe stopping point, stop that server with `rex server stop`,
then start `systemctl --user start rex.service`. Stopping a server ends its running
processes; a saved layout is not process migration. Do not remove a socket while its
server is running.

If Rex is retired later, remove its managed files and add idempotent cleanup for the user
service, tunnel job, installed binary and managed preferences as appropriate. Review local
sessions and app state separately; never delete them blindly.
