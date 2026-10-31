"""Native global directory defaults and moved-root cleanup (docs/agents.md).

The host policy lives in `.chezmoidata/agent_dirs.json`. Project grants and rules
are repository-owned; this module does not generate project configuration.
"""
import glob
import importlib
import json
import os
import re
import subprocess
import sys

import agent_settings as a

DATA = ".chezmoidata/agent_dirs.json"
# The global profile that repository-owned profiles can extend on every host.
CODEX_SELF = "self"


def data():
    return a.load_managed(DATA)["agentDirs"]


def enabled_here(d=None, host=None):
    d = d or data()
    return (host if host is not None else a.current_host()) in d.get("hosts", [])


def expand(pattern, home=None, existing=True):
    """Absolute paths for a `~` path or glob; globs keep only directories that exist."""
    home = home or a.HOME
    p = pattern.replace("$HOME", home, 1)
    if p == "~" or p.startswith("~/"):
        p = home + p[1:]
    if any(c in p for c in "*?["):
        return sorted(x for x in glob.glob(p) if os.path.isdir(x))
    if existing and not os.path.exists(p):
        return []
    return [os.path.normpath(p)]


def tilde(path, home=None):
    home = home or a.HOME
    return "~" + path[len(home):] if path == home or path.startswith(home + "/") else path


def _json_out(text, live, merged):
    if text.strip() and merged == live:
        return text
    return json.dumps(merged, indent=2, ensure_ascii=False) + "\n"


# ---- Codex: permission profiles -------------------------------------------------------------

def _blocks(text):
    blocks, current = [], (None, [])
    for line in text.splitlines():
        match = a._HEADER.match(line)
        if match and not line.lstrip().startswith("#"):
            blocks.append(current)
            current = (match.group(1).strip(), [line])
        else:
            current[1].append(line)
    blocks.append(current)
    return blocks


def _next_comments(body):
    """The comment lines that end a table's block. They precede the next table's header (another
    tool's marker, such as Sphinx's `# >>> ... managed` line), so they belong to that table and must
    survive when this one is replaced or dropped."""
    end = len(body)
    while end > 1 and (not body[end - 1].strip() or body[end - 1].lstrip().startswith("#")):
        end -= 1
    tail = body[end:]
    first = next((i for i, l in enumerate(tail) if l.strip()), len(tail))
    return tail[first:]


def _replace_tables(text, prefix, tables, drop=(), top=None):
    """Replace the tables named `prefix` or under it with `tables` ([(name, [lines])]), where the
    first of them was (else at the end); drop those in `drop`; set or remove top-level keys
    (`top`: {key: TOML value or None})."""
    rendered = []
    for name, body in tables:
        rendered.append((name, ["[%s]" % name] + body + [""]))
    keep, placed = [], False
    for name, body in _blocks(text):
        if name is not None and (name == prefix or name.startswith(prefix + ".")):
            if not placed:
                keep.extend(rendered)
                placed = True
            keep.append(("#", _next_comments(body)))
            continue
        if name is not None and name in drop:
            keep.append(("#", _next_comments(body)))
            continue
        if name is None and top:
            body = [l for l in body if not any(re.match(r"^\s*%s\s*=" % re.escape(k), l) for k in top)]
            while body and not body[0].strip():
                body = body[1:]
            body = ["%s = %s" % (k, v) for k, v in top.items() if v is not None] + [""] + body
        keep.append((name, body))
    if not placed:
        last = keep[-1][1] if keep else []
        if last and last[-1].strip():
            last.append("")
        keep.extend(rendered)
    lines = [l for _, body in keep for l in body]
    return "\n".join(lines).strip("\n") + "\n"


def _q(s):
    return json.dumps(s)


def _toml_parser():
    """Load a real TOML parser only when Codex configuration needs one."""
    for name in ("tomllib", "tomli"):
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError as exc:
            if exc.name != name:
                raise
    raise RuntimeError("codex_global: requires tomllib (Python >=3.11) or tomli; refusing rewrite")


def codex_global(text, d=None, home=None, host=None):
    """Define `self` everywhere so repository-owned profiles can extend it.
    Outside the native-policy hosts it only extends :workspace, leaving sandbox
    settings and default selection alone. Native-policy hosts retain their full
    default profile: private-root denies, writable caches and network access.
    """
    tomllib = _toml_parser()
    d = d or data()
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError("codex_global: malformed TOML; refusing rewrite") from exc
    permissions = parsed.get("permissions", {})
    if not isinstance(permissions, dict) or (
            CODEX_SELF in permissions and not isinstance(permissions[CODEX_SELF], dict)):
        raise ValueError("codex_global: incompatible permissions.self; refusing rewrite")
    profile = permissions.get(CODEX_SELF, {})
    if (any(key in profile and not isinstance(profile[key], dict)
            for key in ("filesystem", "network", "workspace_roots")) or
            ("extends" in profile and not isinstance(profile["extends"], str))):
        raise ValueError("codex_global: incompatible permissions.self; refusing rewrite")
    if not enabled_here(d, host):
        if CODEX_SELF in permissions:
            return text
        new = text + ("\n" if text and not text.endswith("\n") else "")
        new += '\n[permissions.self]\nextends = ":workspace"\n'
        try:
            candidate = tomllib.loads(new)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError("codex_global: unsupported permissions layout; refusing rewrite") from exc
        expected = dict(parsed, permissions=dict(permissions, self={"extends": ":workspace"}))
        if candidate != expected:
            raise ValueError("codex_global: unexpected candidate; refusing rewrite")
        return new
    # Only canonical table blocks are safely replaceable by the text editor.
    # Semantic comparison detects inline, quoted and dotted definitions elsewhere.
    canonical = "\n".join("\n".join(body) for name, body in _blocks(text)
                          if name == "permissions.self" or
                          (name and name.startswith("permissions.self.")))
    try:
        replaceable = tomllib.loads(canonical).get("permissions", {}).get("self")
    except tomllib.TOMLDecodeError as exc:
        raise ValueError("codex_global: unsupported self layout; refusing rewrite") from exc
    if CODEX_SELF in permissions and replaceable != permissions[CODEX_SELF]:
        raise ValueError("codex_global: unsupported self layout; refusing rewrite")
    deny = [p for r in d["private"] for p in expand(r, home)]
    write = [p for w in d["alwaysWrite"] if not w.startswith(("/tmp", "/private/tmp", "/dev", "$TMPDIR")) for p in expand(w, home)]
    fs = ["%s = \"deny\"" % _q(p) for p in deny] + ["%s = \"write\"" % _q(p) for p in write]
    tables = [
        ("permissions.%s" % CODEX_SELF, ['description = "This checkout, temp and caches; other private folders denied (dotfiles: .chezmoidata/agent_dirs.json)."', 'extends = ":workspace"']),
        ("permissions.%s.filesystem" % CODEX_SELF, fs),
        ("permissions.%s.network" % CODEX_SELF, ["enabled = true"]),
    ]
    new = _replace_tables(text, "permissions.%s" % CODEX_SELF, tables, drop=("sandbox_workspace_write",),
                          top={"sandbox_mode": None, "default_permissions": _q(CODEX_SELF)})
    try:
        candidate = tomllib.loads(new)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError("codex_global: invalid candidate TOML; refusing rewrite") from exc
    expected = dict(parsed)
    expected.pop("sandbox_mode", None)
    expected.pop("sandbox_workspace_write", None)
    expected["default_permissions"] = CODEX_SELF
    managed = tomllib.loads("\n".join("[%s]\n%s" % (name, "\n".join(body))
                                      for name, body in tables))["permissions"][CODEX_SELF]
    expected["permissions"] = dict(permissions, self=managed)
    if candidate != expected:
        raise ValueError("codex_global: unsupported layout; refusing rewrite")
    return text if new == text else new


def _load_jsonc(text):
    return json.loads(re.sub(r"^\s*//.*$", "", text, flags=re.M)) if text.strip() else {}


# ---- Retiring a moved root -----------------------------------------------------------------

def drop_root(old, home=None):
    """Remove grants for a project root that no longer exists. Claude's and opencode's
    per-project files and Codex's global trust may contain historical grants, so a moved root
    leaves its old path behind in them. Returns the files changed."""
    home = home or os.path.expanduser("~")
    old = old.rstrip("/")
    tilded = tilde(old, home)
    changed = []

    def warn(path, reason):
        print("drop_root: skipping %s: %s" % (path, reason), file=sys.stderr)

    def machine_local(path):
        component = path
        while component != home and component != os.path.dirname(component):
            if os.path.islink(component):
                warn(path, "symlink path")
                return False
            component = os.path.dirname(component)
        project = os.path.dirname(os.path.dirname(path))
        try:
            relative = os.path.relpath(path, project)
            # The index alone misses staged deletions/untracking with a retained
            # working copy. Either Git-owned version prevents local cleanup.
            for probe in (("ls-files", "--", relative),
                          ("ls-tree", "--name-only", "HEAD", "--", relative)):
                result = subprocess.run(
                    ["git", "-C", project, *probe], capture_output=True, check=True)
                if result.stdout:
                    return False
        except (OSError, subprocess.CalledProcessError):
            warn(path, "Git ownership check failed")
            return False
        return True

    def load(path, jsonc=False):
        try:
            text = read(path)
            live = _load_jsonc(text) if jsonc else json.loads(text)
            if not isinstance(live, dict):
                raise ValueError("expected object")
            shapes = (("permission",),) if jsonc else (
                ("permissions",), ("sandbox",), ("sandbox", "filesystem"))
            for keys in shapes:
                value = live
                for key in keys:
                    value = value.get(key, {})
                if not isinstance(value, dict):
                    raise ValueError("expected object at " + ".".join(keys))
            if jsonc:
                for key in ("external_directory", "edit"):
                    value = live.get("permission", {}).get(key, {})
                    if not isinstance(value, (dict, str)):
                        raise ValueError("expected permission object or action at " + key)
            else:
                for table, key in ((live.get("permissions", {}), "additionalDirectories"),
                                   (live.get("permissions", {}), "allow"),
                                   (live.get("sandbox", {}).get("filesystem", {}), "allowWrite")):
                    if key in table and (not isinstance(table[key], list) or
                                         any(not isinstance(item, str) for item in table[key])):
                        raise ValueError("expected string list at " + key)
            return text, live
        except (OSError, ValueError, AttributeError) as exc:
            warn(path, "invalid input (%s)" % type(exc).__name__)
            return None

    def read(path):
        with open(path) as f:
            return f.read()

    def write(path, text):
        with open(path, "w") as f:
            f.write(text)
        changed.append(path)

    codex = os.path.join(home, ".codex", "config.toml")
    if os.path.isfile(codex):
        text = read(codex)
        new = _replace_tables(text, "projects.%s" % _q(old), []) if old in text else text
        if new != text:
            write(codex, new)
    for path in sorted(glob.glob(os.path.join(home, "Projects", "*", ".claude", "settings.local.json"))):
        if not machine_local(path):
            continue
        loaded = load(path)
        if loaded is None:
            continue
        text, live = loaded
        if old not in text:
            continue
        merged = json.loads(json.dumps(live))
        stale = {old, "Read(/%s/**)" % old}
        perms = merged.get("permissions", {})
        fs = merged.get("sandbox", {}).get("filesystem", {})
        for table, key in ((perms, "additionalDirectories"), (perms, "allow"), (fs, "allowWrite")):
            if isinstance(table.get(key), list):
                table[key] = [x for x in table[key] if x not in stale]
                if not table[key]:
                    del table[key]
        sandbox = merged.get("sandbox")
        if isinstance(sandbox, dict) and sandbox.get("filesystem") == {}:
            del sandbox["filesystem"]
        for key in ("sandbox", "permissions"):
            if merged.get(key) == {}:
                del merged[key]
        new = _json_out(text, live, merged)
        if new != text:
            write(path, new)
    for path in sorted(glob.glob(os.path.join(home, "Projects", "*", ".opencode", "opencode.jsonc"))):
        if not machine_local(path):
            continue
        loaded = load(path, jsonc=True)
        if loaded is None:
            continue
        text, live = loaded
        if tilded not in text and old not in text:
            continue
        merged = json.loads(json.dumps(live))
        for key in ("external_directory", "edit"):
            table = merged.get("permission", {}).get(key)
            if isinstance(table, dict):
                for k in ("%s/**" % tilded, "%s/**" % old):
                    table.pop(k, None)
        new = _json_out(text, live, merged)
        if new != text:
            write(path, new)
    return changed


# ---- Claude Code: ~/.claude/settings.json --------------------------------------------------

# Commands that cannot work in Claude Code's sandbox (sockets, $HOME-wide writes) and run
# outside it, under the permission mode like any unsandboxed command.
# aac (Bitwarden Agent Access) ignores the sandbox proxy, so it cannot reach the relay
# inside the sandbox; outside it, Claude Code asks before it runs, then Touch ID gates it.
CLAUDE_UNSANDBOXED = ["docker *", "chezmoi *", "brew *", "herdr *", "ssh *", "tmux *", "aac *"]


def claude_global(settings, d=None, host=None):
    """On the policy's hosts: Bash runs in Claude Code's sandbox, writing only the working
    directory, temp, the cache directories and repository-owned write grants.
    A sandboxed command runs without asking; one the sandbox blocks may be
    retried outside it, which the permission mode decides. Reads use Claude's
    native permissions; no tool-gate plugin adds a read boundary."""
    d = d or data()
    if not enabled_here(d, host):
        return settings
    write = [w for w in d["alwaysWrite"] if w.startswith("~/")]
    managed = {"sandbox": {
        "enabled": True,
        "autoAllowBashIfSandboxed": True,
        "allowUnsandboxedCommands": True,
        "excludedCommands": CLAUDE_UNSANDBOXED,
        "filesystem": {"allowWrite": write},
    }}
    return a.deep_merge(settings, managed)
