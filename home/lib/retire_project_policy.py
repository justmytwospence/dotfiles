"""Retire redundant machine-local policy only behind committed on-machine replacements.

Discover immediate ~/Projects children, never write shared policy, and leave unknown
legacy keys alone. JSONC edits remove array values only: comments and other settings
retain their original bytes. No Codex or OpenCode configuration is touched.
"""
import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


@dataclass
class Node:
    value: object
    start: int
    end: int
    children: object = field(default_factory=dict)
    commas: list = field(default_factory=list)


# Comments are tokens too, but never included in a removal span.
TOKEN = re.compile(r'\s+|//[^\r\n]*|/\*[\s\S]*?\*/|"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"|[{}\[\],:]|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|true|false|null')


def parse(text):
    """Parse JSON with comments/trailing commas, retaining value and comma spans."""
    tokens, pos = [], 0
    while pos < len(text):
        match = TOKEN.match(text, pos)
        if not match:
            raise ValueError("invalid JSON/JSONC")
        word = match.group()
        if not word.isspace() and not word.startswith(("//", "/*")):
            tokens.append((word, pos, match.end()))
        pos = match.end()
    index = 0

    def take():
        nonlocal index
        if index >= len(tokens):
            raise ValueError("incomplete JSON/JSONC")
        token = tokens[index]
        index += 1
        return token

    def node():
        word, start, end = take()
        if word not in ("{", "["):
            return Node(json.loads(word), start, end)
        obj = word == "{"
        close = "}" if obj else "]"
        values, children, commas = ({} if obj else []), ({} if obj else []), []
        while index < len(tokens) and tokens[index][0] != close:
            if obj:
                key = json.loads(take()[0])
                if not isinstance(key, str) or key in values or take()[0] != ":":
                    raise ValueError("invalid or duplicate JSON key")
            child = node()
            if obj:
                values[key], children[key] = child.value, child
            else:
                values.append(child.value)
                children.append(child)
            if index < len(tokens) and tokens[index][0] == ",":
                commas.append(take()[1:])
            elif index >= len(tokens) or tokens[index][0] != close:
                raise ValueError("missing JSON separator")
        if take()[0] != close:
            raise ValueError("invalid JSON container")
        return Node(values, start, tokens[index - 1][2], children, commas)

    root = node()
    if index != len(tokens) or not isinstance(root.value, dict):
        raise ValueError("policy must be a JSON object")
    return root


def parse_pi(text):
    """Pi uses JSON.parse, not JSONC: comments/trailing commas must fail closed."""
    json.loads(text)
    return parse(text)


def at(node, *keys):
    for key in keys:
        if not isinstance(node.value, dict):
            raise ValueError("policy container must be an object")
        if key not in node.children:
            return None
        node = node.children[key]
    return node


def array(node):
    if node is None:
        return []
    if not isinstance(node.value, list) or any(not isinstance(x, str) for x in node.value):
        raise ValueError("directory/rule list must contain strings")
    return node.value


def remove_values(text, removals):
    spans = set()
    for node, indices in removals:
        for i in indices:
            child = node.children[i]
            spans.add((child.start, child.end))
            # Preserve every comment, removing just the necessary separators.
        kept = [i for i in range(len(node.children)) if i not in indices]
        needed = {i for i in kept[:-1]}
        for i, span in enumerate(node.commas):
            if i not in needed:
                spans.add(tuple(span))
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + text[end:]
    parse(text)  # Never write a syntactically broken edit.
    return text


def warn(path, error):
    print(f"retired: project policy: {path}: {error}; retained", file=sys.stderr)


def plain(path, boundary):
    """Do not follow symlinks, including parent directories, or rewrite hard links."""
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("symlinked policy path")
        if part == boundary:
            break
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("policy is not a single regular file")
    return path.read_bytes().decode("utf-8")


def git(repo, *args):
    return subprocess.run(["git", "--no-optional-locks", "-C", str(repo), *args],
                          stdin=subprocess.DEVNULL, capture_output=True, check=False)


def tracked(repo, relative):
    result = git(repo, "ls-files", "--error-unmatch", "--", relative)
    if result.returncode not in (0, 1):
        raise ValueError("cannot verify Git tracking")
    return result.returncode == 0 or git(repo, "cat-file", "-e", f"HEAD:./{relative}").returncode == 0


def replacement(repo, relative, home):
    path = repo / relative
    if not path.exists():
        return None
    text = plain(path, home)
    if git(repo, "ls-files", "--error-unmatch", "--", relative).returncode != 0:
        return None
    head = git(repo, "show", f"HEAD:{relative}")
    staged = git(repo, "diff", "--cached", "--quiet", "HEAD", "--", relative)
    if head.returncode or staged.returncode or head.stdout != path.read_bytes():
        return None
    return parse_pi(text) if relative.startswith(".pi/") else parse(text)


def expand(value, home):
    if value == "~" or value.startswith("~/"):
        return str(home) + value[1:]
    return value


def directory_sets(policy, home):
    result = {}
    directories = at(policy, "directories")
    if directories is not None and not isinstance(directories.value, dict):
        raise ValueError("directories must be an object")
    for access in ("read", "write"):
        result[access] = {expand(x, home) for x in array(at(policy, "directories", access))}
    return result


def read_rule(value, home):
    if not value.startswith("Read(") or not value.endswith(")"):
        return None
    path = value[5:-1]
    if not path.endswith("/**") and path != "//**":
        return None
    if path.startswith("//"):
        path = path[1:]  # Claude's absolute Read(//Users/...) syntax.
    elif not path.startswith("~/"):
        return None
    return "Read(" + expand(path, home) + ")"


def duplicate_claude(text, shared, home):
    local = parse(text)
    removals = []
    for keys in (("permissions", "additionalDirectories"), ("permissions", "allow"),
                 ("sandbox", "filesystem", "allowWrite")):
        left, right = at(local, *keys), at(shared, *keys)
        normalize = (lambda x: read_rule(x, home)) if keys[-1] == "allow" else (lambda x: expand(x, home))
        equivalents = {normalize(x) for x in array(right)} - {None}
        indices = {i for i, x in enumerate(array(left)) if normalize(x) in equivalents}
        if indices:
            removals.append((left, indices))
    return remove_values(text, removals) if removals else text


def covered(key, policy, home):
    """Exact replacements only; no guessing broader rule or wildcard equivalence."""
    dirs = directory_sets(policy, home)
    match = re.fullmatch(r"dir:(read|write):(.+)", key)
    if match:
        return expand(match[2], home) in dirs[match[1]]
    match = re.fullmatch(r"(allow|ask|deny):([\s\S]+)", key)
    if match:
        category, rule = match.groups()
    elif key.startswith("tool:"):
        category, rule = "allow", key[5:]
    elif key.startswith("bash:") and not key.startswith("bash:unparsed shell: "):
        category, rule = "allow", f"Bash({key[5:]}:*)"
    elif re.fullmatch(r"(edit|write):.+", key):
        tool, folder = key.split(":", 1)
        category, rule = "allow", f"{tool.title()}({folder.rstrip('/')}/**)"
    else:
        return False
    return rule in array(at(policy, "permissions", category))


def update(path, before, after, home):
    if before == after:
        return
    info = path.stat()
    if plain(path, home) != before:
        raise ValueError("policy changed during cleanup")
    temporary = None
    try:
        fd, name = tempfile.mkstemp(prefix=".retire-policy-", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(fd, stat.S_IMODE(info.st_mode))
            handle.write(after)
        if plain(path, home) != before:
            raise ValueError("policy changed during cleanup")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"retired: redundant project policy in {path}")


def retire(home=None):
    home = Path.home() if home is None else Path(home).absolute()
    policies = {}
    for repo in sorted((home / "Projects").glob("*")):
        if not repo.is_dir() or repo.is_symlink():
            continue
        try:
            root = git(repo, "rev-parse", "--show-toplevel")
            if root.returncode or Path(os.fsdecode(root.stdout).rstrip("\n")).resolve() != repo.resolve():
                continue
            policy = replacement(repo, ".pi/tool-gate.json", home)
            if policy is None:
                continue  # Includes untracked/local-only replacements and absent remote commits.
            directory_sets(policy, home)
            for category in ("allow", "ask", "deny"):
                array(at(policy, "permissions", category))
            policies[str(repo)] = policy
        except (OSError, ValueError) as error:
            warn(repo / ".pi/tool-gate.json", error)
            continue
        old = repo / ".agents/tool-gate.json"
        try:
            if old.exists() and not tracked(repo, ".agents/tool-gate.json"):
                text = plain(old, home)
                generated = parse_pi(text)
                value = generated.value
                previous = directory_sets(generated, home)
                if (set(value) == {"directories"} and isinstance(value["directories"], dict)
                        and set(value["directories"]) <= {"read", "write"}):
                    current = directory_sets(policy, home)
                    if all(previous[k] <= current[k] for k in previous):
                        if plain(old, home) != text or tracked(repo, ".agents/tool-gate.json"):
                            raise ValueError("policy changed during cleanup")
                        old.unlink()
                        print(f"retired: generated project policy {old}")
        except (OSError, ValueError) as error:
            warn(old, error)
        local = repo / ".claude/settings.local.json"
        try:
            if local.exists() and not tracked(repo, ".claude/settings.local.json"):
                shared = replacement(repo, ".claude/settings.json", home)
                if shared is not None:
                    text = plain(local, home)
                    update(local, text, duplicate_claude(text, shared, home), home)
        except (OSError, ValueError) as error:
            warn(local, error)

    legacy = home / ".pi/agent/tool-gate/project-grants.json"
    try:
        if not legacy.exists():
            return
        # A home may itself be version-controlled. Never rewrite tracked state.
        repository = git(legacy.parent, "rev-parse", "--show-toplevel")
        if repository.returncode == 0 and tracked(legacy.parent, legacy.name):
            return
        text = plain(legacy, home)
        state = parse_pi(text)
        removals = []
        for project, entries in state.children.items():
            if not isinstance(entries.value, list) or any(
                    not isinstance(x, dict) or not isinstance(x.get("key"), str) or not x["key"]
                    for x in entries.value):
                raise ValueError("invalid legacy grants list")
            policy = policies.get(project)
            if policy is not None:
                indices = {i for i, entry in enumerate(entries.value) if covered(entry["key"], policy, home)}
                if indices:
                    removals.append((entries, indices))
        if removals:
            update(legacy, text, remove_values(text, removals), home)
    except (OSError, ValueError) as error:
        warn(legacy, error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    retire(args.home)


if __name__ == "__main__":
    main()
