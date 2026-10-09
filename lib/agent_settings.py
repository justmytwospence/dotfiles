"""Merge logic for the modify_ targets: files that a program rewrites and the repo owns only part of.

chezmoi runs each modify_ script with the live target on stdin and writes whatever it prints.
The repo half of each file is a *.managed.json next to the script (never a target itself).
Everything the program or a host-local installer added survives; the managed keys always win.
When the merge changes nothing, the live text is echoed byte for byte, so chezmoi sees no diff.
"""
import json
import os
import re
import sys

# Hook commands purged from the live files wherever they appear: tools that are gone.
DENY = ("SUPERSET", ".superset/", "moshi-hook")
# Interpreters, not hook identities (see _scripts).
_GENERIC = {"sh", "bash", "zsh", "env", "python", "python3", "node", "true"}
HOME = os.path.expanduser("~")


def source_dir():
    path = os.environ.get("CHEZMOI_SOURCE_DIR")
    if path:
        return path
    import subprocess
    return subprocess.run(["chezmoi", "source-path"], capture_output=True, text=True, check=True).stdout.strip()


def load_managed(rel):
    with open(os.path.join(source_dir(), rel)) as handle:
        return json.load(handle)


def run_json(rel, merge):
    """Read the live JSON target from stdin, merge the managed file into it, print the result."""
    text = sys.stdin.read()
    live = json.loads(text) if text.strip() else {}
    merged = merge(live, load_managed(rel))
    if text.strip() and merged == live:
        sys.stdout.write(text)
    else:
        sys.stdout.write(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")


def deep_merge(live, managed, replace=()):
    """Managed keys win, maps merge recursively (except keys in `replace`), live-only keys stay
    where they are."""
    out = dict(live)
    for key, value in managed.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict) and key not in replace:
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _normal(command):
    command = command.replace(HOME, "$HOME").replace("${HOME}", "$HOME")
    return " ".join(command.replace("'", " ").replace('"', " ").split())


def _scripts(command):
    """Basenames of the paths a hook command runs: herdr's installer writes the same
    herdr-agent-state.sh with an absolute path where the repo says $HOME. Either way it is
    the same hook."""
    names = set()
    for token in _normal(command).split():
        if "/" in token:
            name = token.rstrip(";").rsplit("/", 1)[-1]
            if name and name not in _GENERIC:
                names.add(name)
    return names


def merge_hooks(live, managed):
    """Per event: the managed groups, then every live hook the repo does not already have,
    minus the denylisted ones. A live hook is the repo's if its command (with $HOME and
    quoting normalized) or a script it runs matches a managed hook of the same event."""
    out = {}
    for event in list(managed) + [e for e in live if e not in managed]:
        groups = [dict(g) for g in managed.get(event, [])]
        commands = {_normal(h.get("command", "")) for g in groups for h in g.get("hooks", [])}
        scripts = set().union(*[_scripts(h.get("command", "")) for g in groups for h in g.get("hooks", [])] or [set()])
        for group in live.get(event, []):
            keep = []
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                if any(word in command for word in DENY):
                    continue
                if _normal(command) in commands or _scripts(command) & scripts:
                    continue
                commands.add(_normal(command))
                keep.append(hook)
            if keep:
                groups.append(dict(group, hooks=keep))
        if groups:
            out[event] = groups
    return out


# Maps the repo owns outright: a key dropped or renamed in the managed file goes from the live one.
REPLACE = ("hooks", "modelSettings")


def merge_agent_settings(live, managed):
    """~/.claude/settings.json, ~/.codex/hooks.json."""
    if "hooks" in managed or "hooks" in live:
        managed = dict(managed, hooks=merge_hooks(live.get("hooks", {}), managed.get("hooks", {})))
    return deep_merge(live, managed, replace=REPLACE)


def _local_package(entry):
    source = entry if isinstance(entry, str) else entry.get("source", "")
    return source.startswith((".", "/", "~"))


def merge_pi_settings(live, managed):
    """~/.pi/agent/settings.json: managed keys win; pi's own (lastChangelogVersion, deviceId,
    ...) stay. Local-path packages (a checkout under test) survive in `packages`."""
    merged = deep_merge(live, managed)
    if "packages" in managed:
        extra = [p for p in live.get("packages", []) if _local_package(p) and p not in managed["packages"]]
        merged["packages"] = list(managed["packages"]) + extra
    return merged


def mcp_servers(skip=()):
    """The shared server set, dot_config/mcp/mcp.json, minus `skip`."""
    servers = load_managed("dot_config/mcp/mcp.json")["mcpServers"]
    return {name: server for name, server in servers.items() if name not in skip}


# Project servers: a shared server with "enabled": false and "projects": "<marker>" is off at
# user level everywhere and switched on, per harness, in each repository under PROJECTS that
# contains <marker> ("vercel": ".vercel", the directory `vercel link` writes).
PROJECTS = os.path.join(HOME, "Projects")


def project_servers():
    """{name: [repo, ...]} for every server scoped to marker repositories."""
    out = {}
    for name, server in mcp_servers().items():
        marker = server.get("projects")
        if not marker:
            continue
        repos = []
        if os.path.isdir(PROJECTS):
            for entry in sorted(os.listdir(PROJECTS)):
                repo = os.path.join(PROJECTS, entry)
                if os.path.isdir(os.path.join(repo, ".git")) and os.path.exists(os.path.join(repo, marker)):
                    repos.append(os.path.realpath(repo))
        out[name] = repos
    return out


def _exclude(repo, rel):
    """Keep a generated file out of the repo's git status without touching its .gitignore."""
    import subprocess
    tracked = subprocess.run(["git", "-C", repo, "ls-files", "--error-unmatch", rel], capture_output=True).returncode == 0
    ignored = subprocess.run(["git", "-C", repo, "check-ignore", "-q", rel], capture_output=True).returncode == 0
    if tracked or ignored:
        return
    path = os.path.join(repo, ".git", "info", "exclude")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as handle:
        handle.write("/%s\n" % rel)


def _write_if_changed(path, text):
    old = open(path).read() if os.path.exists(path) else None
    if old == text:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)
    return True


def enable_project_servers():
    """Switch each project server on in its repositories for pi (.pi/mcp.json), Codex
    (.codex/config.toml) and opencode (.opencode/opencode.jsonc): an override of just
    `enabled`, since each merges a project entry over the user-level one. Claude Code gets the
    full server at local scope from modify_private_dot_claude.json instead. Generated files
    that git would otherwise show go into the repo's .git/info/exclude. Prints what changed."""
    for name, repos in project_servers().items():
        for repo in repos:
            changed = []
            # pi: project entries without command/url override enabled only.
            rel = ".pi/mcp.json"
            path = os.path.join(repo, rel)
            data = json.load(open(path)) if os.path.exists(path) else {}
            data.setdefault("mcpServers", {}).setdefault(name, {})["enabled"] = True
            if _write_if_changed(path, json.dumps(data, indent=2) + "\n"):
                changed.append(rel)
            # Codex: project config layers merge table by table.
            rel = ".codex/config.toml"
            path = os.path.join(repo, rel)
            text = open(path).read() if os.path.exists(path) else ""
            new = _set_toml_key(text, "mcp_servers.%s" % name, "enabled", "true")
            if _write_if_changed(path, new):
                changed.append(rel)
            # opencode: .opencode/ config merges over the global one, key by key.
            rel = ".opencode/opencode.jsonc"
            path = os.path.join(repo, rel)
            data = json.loads(re.sub(r"^\s*//.*$", "", open(path).read(), flags=re.M)) if os.path.exists(path) else {}
            data.setdefault("mcp", {}).setdefault(name, {})["enabled"] = True
            if _write_if_changed(path, json.dumps(data, indent=2) + "\n"):
                changed.append(rel)
            for rel in changed:
                _exclude(repo, rel)
            if changed:
                print("%s: %s on in %s" % (os.path.basename(repo), name, ", ".join(changed)))


# Fixed OAuth callback ports for pre-registered clients (mcp.json oauth.clientId): Claude Code
# redirects to `localhost`, which Authelia matches exactly; Codex listens on 127.0.0.1.
CALLBACK_PORT = {"claude": 8766, "codex": 8767}
# Codex needs two more keys for those clients. Its default redirect is /callback/<random>, which
# Authelia rejects (the path must be /callback), and it requests every scope the authorization
# server lists (email, groups, ...), where Authelia's mcp clients allow only these three.
CODEX_CALLBACK_URL = "http://127.0.0.1:%d/callback" % CALLBACK_PORT["codex"]
CODEX_SCOPES = ["openid", "profile", "offline_access"]


def _client_id(server):
    return (server.get("oauth") or {}).get("clientId") or (server.get("oauth") or {}).get("client_id")


def _spec(server):
    if "url" in server:
        spec = {"url": server["url"]}
        if _client_id(server):
            spec["clientId"] = _client_id(server)
        return spec
    return {"command": server.get("command"), "args": list(server.get("args", [])), "env": dict(server.get("env", {}))}


def _claude_entry(server):
    if "url" in server:
        entry = {"type": "http", "url": server["url"]}
        if _client_id(server):
            entry["oauth"] = {"clientId": _client_id(server), "callbackPort": CALLBACK_PORT["claude"]}
        return entry
    return dict({"type": "stdio"}, **_spec(server))


# What Claude Code writes for a project it has not opened yet (`claude mcp add -s local`).
_CLAUDE_PROJECT = {"allowedTools": [], "mcpContextUris": [], "mcpServers": {}, "enabledMcpjsonServers": [],
                   "disabledMcpjsonServers": [], "hasTrustDialogAccepted": False}


def merge_claude_mcp(live, servers, projects=None):
    """~/.claude.json: each shared server set at user scope; an entry that already says the
    same thing is left exactly as Claude wrote it. Claude's own servers are untouched. A server
    with "enabled": false is removed from user scope instead, and `projects` ({name: [repo]})
    puts it at local scope in each of its repositories."""
    current = dict(live.get("mcpServers", {}))
    for name, server in servers.items():
        if server.get("enabled") is False:
            current.pop(name, None)
            continue
        if name in current and _spec(current[name]) == _spec(server):
            continue
        current[name] = _claude_entry(server)
    merged = live if current == live.get("mcpServers", {}) else dict(live, mcpServers=current)
    for name, repos in (projects or {}).items():
        for repo in repos:
            entry = (merged.get("projects") or {}).get(repo) or json.loads(json.dumps(_CLAUDE_PROJECT))
            have = (entry.get("mcpServers") or {}).get(name)
            if have is not None and _spec(have) == _spec(servers[name]):
                continue
            entry = dict(entry, mcpServers=dict(entry.get("mcpServers") or {}, **{name: _claude_entry(servers[name])}))
            merged = dict(merged, projects=dict(merged.get("projects") or {}, **{repo: entry}))
    return merged


# ---- ~/.codex/config.toml -----------------------------------------------------

_HEADER = re.compile(r"^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")

# Keys pinned inside tables Codex owns: (table pattern, key, TOML value, table to create when
# no table matches, or None to pin only where Codex already wrote the table).
CODEX_PINS = (
    # Codex desktop's "import from other agents" sync copied Cursor's built-in skills into
    # ~/.agents/skills (renaming Cursor to Codex in them), wrote a stale ~/AGENTS.md, and
    # enabled every Claude Cowork plugin. Skills and instructions come from this repo instead.
    (re.compile(r"desktop$"), "external-agent-import-sync-enabled", "false", None),
    # The Cowork plugins that sync enabled: ~120 business skills (legal, HR, sales, ...).
    (re.compile(r'plugins\."[^"]+@claude-cowork"$'), "enabled", "false", None),
    # Codex-managed worktrees always go to $CODEX_HOME/worktrees, detached, and nothing can
    # redirect them; checkouts belong in <project>/.worktrees (~/.local/bin/worktree).
    (re.compile(r"features$"), "worktrees", "false", "features"),
    # ~/.codex/hooks.json (herdr's and tmux-agents' state hooks) runs only with hooks on.
    (re.compile(r"features$"), "hooks", "true", "features"),
    # Codex's shared background server keeps the first terminal's environment, so herdr would
    # attribute every Codex session to that first pane.
    (re.compile(r"features$"), "daemon_auto_start", "false", "features"),
)


def _pin(table, body):
    for pattern, key, value, _ in CODEX_PINS:
        if not pattern.match(table or ""):
            continue
        line = "%s = %s" % (key, value)
        key_re = re.compile(r"^\s*%s\s*=" % re.escape(key))
        hits = [i for i, l in enumerate(body) if key_re.match(l)]
        if hits:
            if body[hits[0]].strip() != line:
                body[hits[0]] = line
        else:
            body.insert(1, line)
    return body


def _set_toml_key(text, table, key, value):
    """Set `key = value` in [table], adding the table at the end if it is missing."""
    blocks, current = [], (None, [])
    for line in text.splitlines():
        match = _HEADER.match(line)
        if match and not line.lstrip().startswith("#"):
            blocks.append(current)
            current = (match.group(1).strip(), [line])
        else:
            current[1].append(line)
    blocks.append(current)
    line = "%s = %s" % (key, value)
    key_re = re.compile(r"^\s*%s\s*=" % re.escape(key))
    out, found = [], False
    for name, body in blocks:
        if name == table:
            found = True
            hits = [i for i, l in enumerate(body) if key_re.match(l)]
            if hits:
                body[hits[0]] = line
            else:
                body.insert(1, line)
        out.extend(body)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.extend(["[%s]" % table, line])
    return "\n".join(out).strip("\n") + "\n"


def trust_codex_projects(text, repos):
    """Codex reads a repo's .codex/config.toml only for a trusted project, and trusting a
    parent directory does not cover it. Trust each repo that a project server is enabled in,
    unless the config already says something about it."""
    for repo in repos:
        table = 'projects.%s' % json.dumps(repo)
        if not any((m := _HEADER.match(l)) and m.group(1).strip() == table for l in text.splitlines()):
            text = _set_toml_key(text, table, "trust_level", '"trusted"')
    return text


def _toml_table(name, server):
    q = json.dumps  # a JSON string is a valid TOML basic string
    spec = _spec(server)
    lines = ["[mcp_servers.%s]" % name]
    if server.get("enabled") is False:
        lines.append("enabled = false")
    if "url" in spec:
        lines.append("url = %s" % q(spec["url"]))
        if "clientId" in spec:
            lines.append("scopes = [%s]" % ", ".join(q(s) for s in CODEX_SCOPES))
            lines += ["", "[mcp_servers.%s.oauth]" % name,
                      "client_id = %s" % q(spec["clientId"]), "callback_port = %d" % CALLBACK_PORT["codex"],
                      "callback_url = %s" % q(CODEX_CALLBACK_URL)]
    else:
        lines.append("command = %s" % q(spec["command"]))
        lines.append("args = [%s]" % ", ".join(q(a) for a in spec["args"]))
        if spec["env"]:
            lines += ["", "[mcp_servers.%s.env]" % name]
            lines += ["%s = %s" % (k, q(v)) for k, v in spec["env"].items()]
    return lines


def merge_codex_toml(text, servers):
    """Replace or append one [mcp_servers.<name>] table (and its subtables) per shared server,
    and apply CODEX_PINS. Text-level, so comments, ordering and every other table are kept as
    Codex wrote them."""
    lines = text.splitlines()
    # Split into blocks: (table name or None for the preamble, lines).
    blocks, current = [], (None, [])
    for line in lines:
        match = _HEADER.match(line)
        if match and not line.lstrip().startswith("#"):
            blocks.append(current)
            current = (match.group(1).strip(), [line])
        else:
            current[1].append(line)
    blocks.append(current)
    # A table may appear once in TOML; fold repeats (an earlier version of the pins below
    # wrote `[features]` once per key) into the first, dropping the repeated header.
    merged, first = [], {}
    for table, body in blocks:
        if table is not None and table in first:
            target = merged[first[table]][1]
            while target and not target[-1].strip():
                target.pop()
            target.extend(l for l in body[1:] if l.strip())
            target.append("")
            continue
        if table is not None:
            first[table] = len(merged)
        merged.append((table, list(body)))
    blocks = merged

    def owner(table):
        for name in servers:
            if table == "mcp_servers.%s" % name or (table or "").startswith("mcp_servers.%s." % name):
                return name
        return None

    out, done = [], set()
    for table, body in blocks:
        name = owner(table)
        if name is None:
            out.extend(_pin(table, list(body)))
            continue
        if name in done:
            continue
        done.add(name)
        old = [l for t, b in blocks if owner(t) == name for l in b]
        new = _toml_table(name, servers[name])
        if [l for l in old if l.strip()] == new:
            out.extend(old)
        else:
            trailing = len(old) - len("\n".join(old).rstrip().split("\n"))
            out.extend(new + [""] * max(trailing, 1))
    for name, server in servers.items():
        if name not in done:
            if out and out[-1].strip():
                out.append("")
            out.extend(_toml_table(name, server))
    tables = [t for t, _ in blocks]
    # Pins whose table is missing: one new table each, holding all of that table's pins.
    # (One per pin wrote `[features]` three times on a fresh file, which Codex rejects as
    # a duplicate key.)
    missing = {}
    for pattern, key, value, create in CODEX_PINS:
        if create and not any(pattern.match(t or "") for t in tables):
            missing.setdefault(create, []).append("%s = %s" % (key, value))
    for create, lines in missing.items():
        if out and out[-1].strip():
            out.append("")
        out.extend(["[%s]" % create] + lines)
    result = "\n".join(out)
    if text.endswith("\n") or not text:
        result = result.rstrip("\n") + "\n"
    return result
