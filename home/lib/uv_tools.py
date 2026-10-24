"""Converge uv tool receipts with the release cooldown (docs/cooldown.md).

uv records each tool's resolver settings (exclude-newer, exclude-newer-package) and its
requirements in the tool's receipt, and `uv tool upgrade` reuses both. This fixes three
things in receipts by reinstalling the tool with the same requirements, which makes uv
rewrite the receipt from the current settings:

- Exemptions. A tool whose requirements name a package I maintain (cooldownExempt.uv)
  carries `exclude-newer-package <pkg>=false` for each of those packages, so upgrades take
  them on release day. The user-level uv.toml cannot hold them: uv merges it into every
  project's uv.lock, which then fails `uv sync --locked` in CI.
- Lapsed allowances. A declared tool pinned to an exact version (`cooldown-allow uv`) with
  no active allowance is reinstalled unpinned. Otherwise the pin and its cutoff stay in the
  receipt, and the tool never upgrades past that release.
- Retired 2026-10-24: the "2999-01-01T00:00:00Z" sentinels the old uv.toml wrote into
  every receipt.

    python3 uv_tools.py --declared a,b --maintained m,n [--allow pkg==1.2.3@<cutoff>]...

Silent when every receipt is converged. Exits 1 when a reinstall fails. Python 3.9 (the
system python3 on the NUC and in the Mac's Command Line Tools).
"""
import argparse
import os
import re
import subprocess
import sys

SENTINEL = "2999-01-01T00:00:00Z"
TOOL_LINE = re.compile(r"^(?P<name>\S+) v(?P<version>\S+)(?P<rest>.*)$")
FIELD = re.compile(r"\[(required|extras|with): ([^\]]*)\]")
OPERATOR = re.compile(r"^[<>=!~]")


def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def req_name(requirement):
    return norm(re.split(r"[\s\[<>=!~;@]", requirement.strip(), maxsplit=1)[0])


def split_with(raw):
    """`uv tool list` joins requirements with ", ", and a specifier may contain commas."""
    out = []
    for token in raw.split(", "):
        if out and OPERATOR.match(token):
            out[-1] += "," + token
        else:
            out.append(token)
    return [t for t in out if t]


def parse_list(text):
    tools = []
    for line in text.splitlines():
        m = TOOL_LINE.match(line)
        if not m or line.startswith("- "):
            continue
        fields = dict(FIELD.findall(m.group("rest")))
        tools.append({
            "name": m.group("name"),
            "required": fields.get("required", ""),
            "extras": fields.get("extras", ""),
            "with": split_with(fields.get("with", "")),
        })
    return tools


def receipt_exemptions(text):
    """The exclude-newer-package table of a receipt: {normalized name: raw value}."""
    for line in text.splitlines():
        if line.startswith("exclude-newer-package"):
            body = line.split("=", 1)[1].strip()[1:-1]
            return {norm(k.strip('"')): v for k, v in
                    re.findall(r'("?[A-Za-z0-9_.-]+"?) = (false|"[^"]*"|\{[^}]*\})', body)}
    return {}


def requirement(tool, required):
    extras = "[%s]" % tool["extras"] if tool["extras"] else ""
    if not required:
        return tool["name"] + extras
    if "://" in required or required.startswith(("git+", "/", ".")):
        return "%s%s @ %s" % (tool["name"], extras, required)
    return tool["name"] + extras + required


def plan(tool, receipt, declared, maintained, allow):
    """The reinstall command for one tool and why, or (None, [])."""
    name = norm(tool["name"])
    required = tool["required"]
    reasons = []
    allowed = allow.get(name)
    pinned = required.startswith("==")
    if pinned and name in declared and not (allowed and required == "==" + allowed[0]):
        reasons.append("cooldown allowance lapsed, unpinned")
        required, allowed = "", None
    names = {name} | {req_name(w) for w in tool["with"]}
    exempt = sorted(maintained) if names & maintained else []
    have = receipt_exemptions(receipt)
    if any(have.get(m) != "false" for m in exempt):
        reasons.append("exempt maintained packages")
    if SENTINEL in receipt:
        reasons.append("drop retired 2999 sentinels")
    if not reasons:
        return None, []
    cmd = ["uv", "tool", "install", requirement(tool, required)]
    for w in tool["with"]:
        cmd += ["--with", w]
    for m in exempt:
        cmd += ["--exclude-newer-package", m + "=false"]
    if allowed and pinned:
        cmd += ["--exclude-newer-package", "%s=%s" % (name, allowed[1])]
    return cmd, reasons


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--declared", default="")
    p.add_argument("--maintained", default="")
    p.add_argument("--allow", action="append", default=[], help="pkg==version@cutoff")
    a = p.parse_args(argv)
    declared = {norm(n) for n in a.declared.split(",") if n}
    maintained = {norm(n) for n in a.maintained.split(",") if n}
    allow = {}
    for spec in a.allow:
        pkg, _, rest = spec.partition("==")
        version, _, cutoff = rest.partition("@")
        allow[norm(pkg)] = (version, cutoff)
    listed = subprocess.run(["uv", "tool", "list", "--show-with", "--show-extras", "--show-version-specifiers"],
                            capture_output=True, text=True)
    if listed.returncode != 0:
        print("uv tool list failed: " + listed.stderr.strip(), file=sys.stderr)
        return 1
    tool_dir = subprocess.run(["uv", "tool", "dir"], capture_output=True, text=True).stdout.strip()
    rc = 0
    for tool in parse_list(listed.stdout):
        try:
            with open(os.path.join(tool_dir, tool["name"], "uv-receipt.toml")) as f:
                receipt = f.read()
        except OSError:
            continue
        cmd, reasons = plan(tool, receipt, declared, maintained, allow)
        if cmd:
            print("==> uv tool %s: %s" % (tool["name"], "; ".join(reasons)), flush=True)
            done = subprocess.run(cmd, capture_output=True, text=True)
            if done.returncode != 0:
                sys.stderr.write(done.stderr)
                rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
