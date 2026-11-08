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
