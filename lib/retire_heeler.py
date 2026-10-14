"""Retire Heeler using Herdr's native registry API; never edit its checkouts.

Only the app's exact device-key comments and its identifiable bootstrap command
are revoked. Unmarked/manual keys and other tools' herdr-pairing keys stay.
"""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile


class RetirementError(RuntimeError):
    pass


def herdr_command(arguments):
    result = subprocess.run(["herdr", *arguments], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True)
    if result.returncode:
        # Native uninstall reports an absent registration as exit 1. Do not
        # confuse a broken server/registry/permission error with that no-op.
        if (arguments[-3:] == ["plugin", "uninstall", "heeler"]
                and result.returncode == 1
                and result.stderr.strip() == "plugin not installed: heeler"):
            return ""
        raise RetirementError(f"herdr {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout


def uninstall(config_dir):
    if shutil.which("herdr") is None:
        # Fresh boxes have no Herdr. An installed registration without its CLI
        # is a blocker, not permission to delete the registry ourselves.
        registry = config_dir / "plugins.json"
        if registry.exists():
            entries = json.loads(registry.read_text())
            if not isinstance(entries, list) or any(not isinstance(p, dict) for p in entries):
                raise RetirementError(f"invalid Herdr registry: {registry}")
            if any(p.get("plugin_id") == "heeler" for p in entries):
                raise RetirementError("Herdr is missing; restore it to uninstall Heeler natively")
        return

    sessions = json.loads(herdr_command(["session", "list", "--json"]))
    if not isinstance(sessions, dict) or not isinstance(sessions.get("sessions"), list):
        raise RetirementError("invalid Herdr session list")
    names = {"default"}  # Also removes the global registration with no server running.
    for session in sessions["sessions"]:
        if not isinstance(session, dict) or not isinstance(session.get("name"), str):
            raise RetirementError("invalid Herdr session entry")
        if session.get("running"):
            names.add(session["name"])
    # Registrations are global, but each running server caches them. Repeating
    # the native unlink refreshes each session without stopping it or its panes.
    for name in sorted(names):
        herdr_command(["--session", name, "plugin", "uninstall", "heeler"])


# An options field may contain quoted whitespace (command=, from=, etc.).
TOKEN = re.compile(rb'(?:[^\s"]|"[^"\r\n]*")+')
KEY_TYPE = re.compile(rb'(?:ssh-|ecdsa-|sk-)[A-Za-z0-9@._+-]+')
BOOTSTRAP = re.compile(rb'herdr-pairing:[A-Za-z0-9-]+:exp:[0-9]+')


def heeler_key(line, home):
    if line.lstrip().startswith(b"#"):
        return False
    words = list(TOKEN.finditer(line))
    if len(words) < 2:
        return False
    start = 0 if KEY_TYPE.fullmatch(words[0].group()) else 1
    if len(words) <= start + 1 or not KEY_TYPE.fullmatch(words[start].group()):
        return False
    if not re.fullmatch(rb'[A-Za-z0-9+/]+={0,2}', words[start + 1].group()):
        return False
    comment = line[words[start + 1].end():].strip()
    if comment in (b"heeler", b"heeler rsa"):
        return True
    if start == 0 or not BOOTSTRAP.fullmatch(comment):
        return False
    command = re.search(rb'(?:^|,)command="([^"]*)"(?:,|$)', words[0].group())
    if command is None:
        return False
    # The generic herdr-pairing marker alone is NOT proof of Heeler ownership.
    # Require the plugin's real enrollment entrypoint in its known native or
    # retired compatibility path, not merely "heeler" somewhere in a command.
    root = re.escape(os.fsencode(home))
    entrypoint = (root + rb'/(?:\.config/herdr/plugins/github(?:-installations)?/'
                  rb'heeler-[0-9a-f]+/(?:[^\s\'"]+/)?|\.local/share/plugins/Heeler/)'
                  rb'plugin/src/pair-accept\.js(?:\'|[ \t]|$)')
    return re.search(entrypoint, command[1]) is not None


def signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_mode, info.st_uid, info.st_gid)


def revoke_keys(home):
    path = home / ".ssh/authorized_keys"
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RetirementError(f"refusing non-regular, symlinked or hard-linked {path}")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as handle:
        before = handle.read()
        if signature(os.fstat(handle.fileno())) != signature(info):
            raise RetirementError(f"{path} changed while reading; retry")
    after = b"".join(line for line in before.splitlines(keepends=True)
                     if not heeler_key(line, home))
    if after == before:
        return  # Preserve inode, timestamps and mode when no marked keys exist.

    # Use Heeler's own lock protocol; never steal a live or stale-looking lock.
    lock = path.with_name(path.name + ".herdr-pairing.lock")
    lock_fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    temporary = None
    try:
        os.close(lock_fd)
        fd, name = tempfile.mkstemp(prefix=".authorized_keys.heeler-", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(fd, "wb") as handle:
            if (os.fstat(fd).st_uid, os.fstat(fd).st_gid) != (info.st_uid, info.st_gid):
                os.fchown(fd, info.st_uid, info.st_gid)
            os.fchmod(fd, stat.S_IMODE(info.st_mode))
            handle.write(after)
            handle.flush()
            os.fsync(fd)
        if signature(path.lstat()) != signature(info) or path.read_bytes() != before:
            raise RetirementError(f"{path} changed during cleanup; retry")
        os.replace(temporary, path)  # Same-directory atomic replacement, even if empty.
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.unlink()


def remove(path):
    if path.is_symlink():
        path.unlink()  # Never follow a config/state/helper symlink.
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def retire(home):
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))) / "herdr"
    state = Path(os.environ.get("XDG_STATE_HOME", str(home / ".local/state"))) / "herdr"
    uninstall(config)
    revoke_keys(home)
    # Keep state on any native-uninstall or SSH rewrite failure for safe retry.
    for path in (config / "plugins/config/heeler", state / "plugins/heeler",
                 home / ".local/bin/heeler-setup"):
        remove(path)


if __name__ == "__main__":
    try:
        retire(Path.home())
    except (OSError, ValueError, RetirementError) as error:
        print(f"retired: Heeler cleanup failed: {error}", file=sys.stderr)
        sys.exit(1)
