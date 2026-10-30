"""Per-project directory grants, as each harness's own configuration (docs/agents.md).

The policy is `.chezmoidata/agent_dirs.json`: private roots, and per project the directories it
may also read (`"*"`: anywhere) and write. pi-tool-gate reads it from each project's
`.agents/tool-gate.json` (rendered from the same data); the functions
here merge the same grants into the files Claude Code, Codex and opencode read natively. Each is
called by a modify_ script with the live file on stdin, keeps everything it does not own, and
returns the text unchanged when nothing changes. Only hosts in `hosts` get any of it.
"""
import glob
import json
import os
import re

import agent_settings as a

DATA = ".chezmoidata/agent_dirs.json"
# The profile names in Codex's config: the global default, and the one a project file defines.
CODEX_SELF = "self"
CODEX_PROJECT = "project"


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


def grants(name, d=None, home=None):
    """The project's root and its expanded grants: {root, anywhere, read, write}."""
    d = d or data()
    spec = d["projects"][name]
    root = expand(spec["root"], home, existing=False)[0]
    write = [p for w in spec.get("write", []) for p in expand(w, home) if p != root]
    read = [p for r in spec.get("read", []) if r != "*" for p in expand(r, home) if p != root and p not in write]
    return {"root": root, "anywhere": "*" in spec.get("read", []), "read": read, "write": write}


def _union(items, extra):
    return list(items) + [x for x in extra if x not in items]


def _json_out(text, live, merged):
    if text.strip() and merged == live:
        return text
    return json.dumps(merged, indent=2, ensure_ascii=False) + "\n"


# ---- Claude Code: <project>/.claude/settings.local.json ------------------------------------

def claude_local(text, name, d=None, home=None):
    """Write grants: additionalDirectories and the sandbox's allowWrite. Read grants: Read allow
    rules (`//abs/**`; `//**` for anywhere), which cover every file-reading tool; Claude ignores
    Grep and Glob path rules, so earlier ones for the same paths are dropped. Only Claude's
    native permissions and sandbox apply; there is no additional tool-gate guard.
    Entries are added, never removed: Claude's own "always allow" choices land here too."""
    g = grants(name, d, home)
    live = json.loads(text) if text.strip() else {}
    merged = json.loads(json.dumps(live))
    perms = merged.setdefault("permissions", {})
    perms["additionalDirectories"] = _union(perms.get("additionalDirectories", []), g["write"])
    readable = ["/"] if g["anywhere"] else g["read"] + g["write"]
    rules = ["Read(/%s/**)" % p.rstrip("/") if p != "/" else "Read(//**)" for p in readable]
    stale = {tool + r[len("Read"):] for r in rules for tool in ("Grep", "Glob")}
    perms["allow"] = _union([r for r in perms.get("allow", []) if r not in stale], rules)
    if g["write"]:
        fs = merged.setdefault("sandbox", {}).setdefault("filesystem", {})
        fs["allowWrite"] = _union(fs.get("allowWrite", []), g["write"])
    if not perms["additionalDirectories"]:
        del perms["additionalDirectories"]
    if not perms["allow"]:
        del perms["allow"]
    if not perms:
        del merged["permissions"]
    return _json_out(text, live, merged)


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


def codex_global(text, d=None, home=None, host=None):
    """~/.codex/config.toml: the `self` profile, made the default in place of sandbox_mode and
    [sandbox_workspace_write] (Codex ignores a project's default_permissions while sandbox_mode
    is set). It extends :workspace (the working directory, /tmp and $TMPDIR writable), denies the
    private roots (the working directory's own checkout still wins, being more specific), lets
    the cache directories be written, and keeps network access on."""
    d = d or data()
    if not enabled_here(d, host):
        return text
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
    return text if new == text else new


def codex_trusted_repos(d=None, home=None, host=None):
    """The project roots Codex must trust to read their .codex/config.toml."""
    d = d or data()
    if not enabled_here(d, host):
        return []
    return [r for spec in d["projects"].values() for r in expand(spec["root"], home)]


def codex_project(text, name, d=None, home=None):
    """<project>/.codex/config.toml: a `project` profile extending `self`, selected as the
    default. Write grants are extra workspace roots; read grants re-open denied folders read-only
    (anywhere: every private root)."""
    d = d or data()
    g = grants(name, d, home)
    readable = [p for r in d["private"] for p in expand(r, home)] if g["anywhere"] else g["read"]
    # The checkout itself is the workspace; an entry for its own path would make it read-only.
    readable = [p for p in readable if p != g["root"]]
    tables = [("permissions.%s" % CODEX_PROJECT, ['extends = %s' % _q(CODEX_SELF)])]
    if g["write"]:
        tables.append(("permissions.%s.workspace_roots" % CODEX_PROJECT, ["%s = true" % _q(p) for p in g["write"]]))
    # A write grant that is itself a private root (such as ~/Documents) must override `self`'s deny of the
    # same path, which a workspace root alone does not.
    fs = ["%s = \"write\"" % _q(p) for p in g["write"]] + ["%s = \"read\"" % _q(p) for p in readable if p not in g["write"]]
    if fs:
        tables.append(("permissions.%s.filesystem" % CODEX_PROJECT, fs))
    new = _replace_tables(text, "permissions.%s" % CODEX_PROJECT, tables, top={"default_permissions": _q(CODEX_PROJECT)})
    return text if new == text else new


# ---- opencode: <project>/.opencode/opencode.jsonc --------------------------------------------

def _load_jsonc(text):
    return json.loads(re.sub(r"^\s*//.*$", "", text, flags=re.M)) if text.strip() else {}


def opencode_project(text, name, d=None, home=None):
    """external_directory allows the grants (anywhere: the private roots too, which the global
    config asks about); `edit` asks in the private roots outside the project and its write grants,
    so a read grant stays read-only. Merged key by key over the global config."""
    d = d or data()
    g = grants(name, d, home)
    live = _load_jsonc(text)
    merged = json.loads(json.dumps(live))
    perm = merged.setdefault("permission", {})
    ext = perm.get("external_directory") if isinstance(perm.get("external_directory"), dict) else {}
    readable = [tilde(p, home) for r in d["private"] for p in expand(r, home)] if g["anywhere"] else [tilde(p, home) for p in g["read"]]
    for p in readable + [tilde(p, home) for p in g["write"]]:
        ext["%s/**" % p] = "allow"
    perm["external_directory"] = ext
    if g["anywhere"] or g["read"]:
        edit = perm.get("edit") if isinstance(perm.get("edit"), dict) else {"*": "allow"}
        for p in readable:
            edit["%s/**" % p] = "ask"
        for p in g["write"] + [g["root"]]:
            edit["%s/**" % tilde(p, home)] = "allow"
        perm["edit"] = edit
    return _json_out(text, live, merged)


def run(kind, name=None):
    """Entry point for the modify_ scripts: stdin in, stdout out."""
    import sys
    text = sys.stdin.read()
    if kind == "claude":
        out = claude_local(text, name)
    elif kind == "codex":
        out = codex_project(text, name)
    elif kind == "opencode":
        out = opencode_project(text, name)
    else:
        raise SystemExit("agent_dirs: unknown kind %r" % kind)
    sys.stdout.write(out)


# ---- Retiring a moved root -----------------------------------------------------------------

def drop_root(old, home=None):
    """Remove grants for a project root that no longer exists. Claude's and opencode's
    per-project files and Codex's global trust only ever gain entries (above), so a moved root
    leaves its old path behind in them. Returns the files changed."""
    home = home or os.path.expanduser("~")
    old = old.rstrip("/")
    tilded = tilde(old, home)
    changed = []

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
        text = read(path)
        if old not in text:
            continue
        live = json.loads(text)
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
        text = read(path)
        if tilded not in text and old not in text:
            continue
        live = _load_jsonc(text)
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
    directory, temp, the cache directories and a project's write grants (its
    settings.local.json). A sandboxed command runs without asking; one the sandbox blocks may be
    retried outside it, which the permission mode decides. Reads use Claude's native permissions,
    including the project's Read allow rules; no tool-gate plugin adds a read boundary."""
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
