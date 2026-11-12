#!/usr/bin/env python3
"""bin/check and bin/land: the dotfiles change workflow (AGENTS.md "Source and change workflow").

$HOME tracks committed main. Sessions work in .worktrees/<branch> and never apply;
`check` proves a checkout without touching $HOME, `land` is the only way a change
reaches it: rebase, check, fast-forward main, push, apply, sync the NUC, then remove
the landed worktree unless someone is using it (a herdr space, or the shell inside).
"""
import argparse
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib

REMOTES = ("spencer@nuc",)  # hosts that `chezmoi update` after a push
REMOTE_CHEZMOI = "~/.local/bin/chezmoi"
SSH = ("ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10")
PUSHING_HOSTS = ("mac-pro", "mac-air")  # the NUC and boxes only pull (AGENTS.md)
RENDER_EXCLUDE = "scripts,encrypted,externals"
SHELLS = {".zshrc": "zsh", ".zshenv": "zsh", ".zprofile": "zsh", ".zlogin": "zsh",
          ".bashrc": "bash", ".bash_profile": "bash", ".profile": "sh"}


class Fail(Exception):
    """A refusal or failed step; the message says what to do next."""


def run(cmd, cwd=None, check=True, capture=True, env=None, input=None):
    result = subprocess.run(cmd, cwd=cwd, text=True, env=env, input=input,
                            capture_output=capture)
    if check and result.returncode:
        detail = (result.stderr or result.stdout or "").strip() if capture else ""
        raise Fail("%s failed (%d)%s" % (" ".join(map(str, cmd[:3])), result.returncode,
                                         ": " + detail if detail else ""))
    return result


def git(cwd, *args, check=True):
    return run(["git", "-C", str(cwd), *args], check=check).stdout.strip()


def toplevel(cwd):
    return Path(git(cwd, "rev-parse", "--show-toplevel")).resolve()


def main_checkout(cwd):
    """The main checkout: the parent of the common .git directory."""
    common = Path(git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
    if common.name != ".git":
        raise Fail("cannot find the main checkout for %s" % cwd)
    return common.parent


def branch_of(cwd):
    return git(cwd, "symbolic-ref", "--short", "-q", "HEAD", check=False) or None


def dirty(cwd, *paths):
    return git(cwd, "status", "--porcelain", "--untracked-files=all", "--", *paths)


def is_ancestor(cwd, a, b):
    return run(["git", "-C", str(cwd), "merge-base", "--is-ancestor", a, b], check=False).returncode == 0


def worktrees(cwd):
    """branch -> checkout path, from `git worktree list`."""
    out, path, found = git(cwd, "worktree", "list", "--porcelain"), None, {}
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = Path(line[9:])
        elif line.startswith("branch refs/heads/"):
            found[line[18:]] = path
    return found


# --- check -----------------------------------------------------------------------------

def run_tests(checkout):
    home = checkout / "home"
    tests = sorted(str(p.relative_to(home)) for p in (home / "lib").glob("test_*.py"))
    print("==> tests: home/lib (%d files)" % len(tests), flush=True)
    ok = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q", *tests], cwd=home).returncode == 0
    if (checkout / "bin").is_dir():
        print("==> tests: bin", flush=True)
        ok &= subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-q", "-s", "bin",
                              "-p", "test_*.py"], cwd=checkout).returncode == 0
    return ok


def render(source, out):
    """The target state of `source` as {path: (kind, digest, data)}; never prints contents."""
    tar = out / "targets.tar"
    result = run(["chezmoi", "--source", str(source), "archive", "--exclude", RENDER_EXCLUDE,
                  "--format", "tar", "--output", str(tar)], check=False)
    if result.returncode:
        raise Fail("chezmoi archive failed for %s:\n%s" % (source, result.stderr.strip()))
    # chezmoi's source directory (home/), in both spellings: macOS temp paths resolve /var
    # to /private/var. Not the checkout root, which project entries name for ~/Projects repos.
    markers = sorted({str(source / "home").encode(), str(source.resolve() / "home").encode()},
                     key=len, reverse=True)
    entries = {}
    with tarfile.open(tar) as archive:
        for member in archive:
            name = member.name.rstrip("/")
            if member.isdir():
                entries[name] = ("dir", "", b"")
            elif member.issym():
                link = member.linkname
                for marker in markers:
                    link = link.replace(marker.decode(), "<source>/home")
                entries[name] = ("symlink", link, b"")
            else:
                # Targets that embed the checkout path differ only by where each side lives.
                data = archive.extractfile(member).read()
                for marker in markers:
                    data = data.replace(marker, b"<source>/home")
                entries[name] = ("file %o" % (member.mode & 0o777), hashlib.sha256(data).hexdigest(), data)
    return entries


def compare(base, head):
    added = sorted(set(head) - set(base))
    removed = sorted(set(base) - set(head))
    changed = sorted(n for n in set(base) & set(head) if base[n][:2] != head[n][:2])
    return added, removed, changed


def shell_for(name, data):
    base = name.rsplit("/", 1)[-1]
    if base in SHELLS:
        return SHELLS[base]
    first = data.split(b"\n", 1)[0]
    if first.startswith(b"#!"):
        for shell in ("zsh", "bash", "sh"):
            if first.rstrip().endswith(shell.encode()) or (b" " + shell.encode()) in first:
                return shell
        return None
    for suffix, shell in ((".zsh", "zsh"), (".bash", "bash"), (".sh", "bash")):
        if base.endswith(suffix):
            return shell
    return None


def validate(name, data):
    """An error message when the target's own format rejects it, else None (or unchecked)."""
    base = name.rsplit("/", 1)[-1]
    try:
        if base.endswith(".json"):
            json.loads(data.decode())
            return None
        if base.endswith(".toml"):
            tomllib.loads(data.decode())
            return None
    except (ValueError, UnicodeDecodeError) as error:
        return str(error)
    command = None
    shell = shell_for(name, data)
    if shell and shutil.which(shell):
        command = [shell, "-n"]
    elif name == ".config/ghostty/config" and shutil.which("ghostty"):
        command = ["ghostty", "+validate-config", "--config-file={file}"]
    if not command:
        return None
    with tempfile.NamedTemporaryFile(suffix="-" + base) as tmp:
        tmp.write(data)
        tmp.flush()
        args = [a.replace("{file}", tmp.name) for a in command]
        if "{file}" not in " ".join(command):
            args.append(tmp.name)
        result = run(args, check=False)
        spellings = (os.path.realpath(tmp.name), tmp.name)
    if result.returncode:
        message = (result.stderr or result.stdout).strip()
        for spelling in spellings:
            message = message.replace(spelling, name)
        return message or "rejected"
    return None


def render_diff(checkout, base_ref):
    print("==> render: %s against %s" % (checkout, base_ref), flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        exported = tmp / "base"
        exported.mkdir()
        # An export, not a checkout: main's committed tree, whatever the main checkout holds.
        archive = subprocess.run(["git", "-C", str(checkout), "archive", "--format=tar", base_ref],
                                 capture_output=True)
        if archive.returncode:
            raise Fail("git archive %s failed: %s" % (base_ref, archive.stderr.decode().strip()))
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(exported, filter="tar")
        (tmp / "b").mkdir()
        (tmp / "h").mkdir()
        base = render(exported, tmp / "b")
        head = render(checkout, tmp / "h")
    added, removed, changed = compare(base, head)
    for label, names in (("added", added), ("removed", removed), ("changed", changed)):
        for name in names:
            print("  %-8s ~/%s" % (label, name))
    if not (added or removed or changed):
        print("  no target changes (scripts, externals and encrypted files are not rendered)")
    errors = []
    for name in added + changed:
        kind, _, data = head[name]
        if not kind.startswith("file"):
            continue
        error = validate(name, data)
        # A format we cannot parse on main either (comments in .json, say) is not a regression.
        if error and (name not in base or validate(name, base[name][2]) is None):
            errors.append((name, error))
    for name, error in errors:
        print("  INVALID  ~/%s: %s" % (name, error))
    return not errors


def check(checkout, base_ref="main", tests=True, targets=True):
    checkout = toplevel(checkout)
    ok = True
    if tests:
        ok &= run_tests(checkout)
    if targets:
        ok &= render_diff(checkout, base_ref)
    print("==> check: %s" % ("ok" if ok else "FAILED"), flush=True)
    return ok


# --- land ------------------------------------------------------------------------------

def host():
    if os.environ.get("DOTFILES_LAND_HOST"):
        return os.environ["DOTFILES_LAND_HOST"]
    return json.loads(run(["chezmoi", "data", "--format", "json"]).stdout).get("host")


def lock(main):
    handle = open(main / ".git" / "dotfiles-land.lock", "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("==> waiting for another bin/land to finish", flush=True)
        fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def sync_remote(remote, tip, reinit):
    steps = ["%s update --no-tty" % REMOTE_CHEZMOI]
    if reinit:
        steps += ["%s init --no-tty" % REMOTE_CHEZMOI, "%s apply --no-tty" % REMOTE_CHEZMOI]
    print("==> %s: %s" % (remote, " && ".join(steps)), flush=True)
    if subprocess.run([*SSH, remote, " && ".join(steps)]).returncode:
        return "%s: chezmoi failed (an apt change needs an interactive `ssh %s` and `chezmoi apply`)" % (remote, remote)
    head = run([*SSH, remote, "git -C ~/Projects/dotfiles rev-parse HEAD"], check=False)
    if head.stdout.strip() != tip:
        return "%s: checkout is at %s, not %s" % (remote, head.stdout.strip()[:7] or "?", tip[:7])
    return None


def herdr_space(main, path):
    """The id of the herdr space open on the worktree at `path`, or None."""
    listing = run(["herdr", "worktree", "list", "--cwd", str(main)], check=False) if shutil.which("herdr") else None
    if listing and listing.returncode == 0:
        for tree in json.loads(listing.stdout)["result"]["worktrees"]:
            if Path(tree["path"]) == path:
                return tree.get("open_workspace_id")
    return None


def remove_worktree(main, branch, path):
    if Path.cwd().resolve().is_relative_to(path.resolve()):
        print("==> not removing %s: this shell is inside it" % path)
        return False
    space = herdr_space(main, path)
    if space:
        run(["herdr", "worktree", "remove", "--workspace", space])
    if path.exists():
        git(main, "worktree", "remove", str(path))
    git(main, "branch", "-d", branch, check=False)
    print("==> removed %s and branch %s" % (path, branch))
    return True


def land(cwd, branch=None, do_check=True, apply=True, sync=True, remove=None):
    current = host()
    if current not in PUSHING_HOSTS:
        raise Fail("land pushes main, which only %s do; this is %s" % (", ".join(PUSHING_HOSTS), current))
    main = main_checkout(cwd)
    branch = branch or branch_of(cwd)
    if not branch:
        raise Fail("detached HEAD: name the branch to land")
    held = lock(main)
    try:
        if branch_of(main) != "main":
            raise Fail("%s is not on main" % main)
        pending = dirty(main, "home")
        if pending:
            raise Fail("main has uncommitted changes under home/, which apply would refuse to deploy:\n"
                       + pending + "\nCommit them (or move them to a worktree) first.")
        git(main, "fetch", "-q", "origin", "main")
        if not is_ancestor(main, "origin/main", "main"):
            if not is_ancestor(main, "main", "origin/main"):
                raise Fail("main and origin/main have diverged; reconcile them by hand")
            git(main, "merge", "-q", "--ff-only", "origin/main")
        old = git(main, "rev-parse", "main")
        if branch == "main":
            checkout = main
            if old == git(main, "rev-parse", "origin/main"):
                raise Fail("nothing to land: main is origin/main")
        else:
            checkout = worktrees(main).get(branch)
            if not checkout:
                raise Fail("branch %s is not checked out in a worktree" % branch)
            if dirty(checkout):
                raise Fail("%s has uncommitted changes; commit them first" % checkout)
            if not is_ancestor(main, "main", branch):
                print("==> rebasing %s onto main" % branch, flush=True)
                rebase = run(["git", "-C", str(checkout), "rebase", "-q", "main"], check=False)
                if rebase.returncode:
                    raise Fail("rebase stopped on a conflict in %s:\n%s\nResolve it, `git rebase --continue`, "
                               "then run bin/land again." % (checkout, (rebase.stdout + rebase.stderr).strip()))
            if git(main, "rev-parse", branch) == old:
                raise Fail("nothing to land: %s has no commits beyond main" % branch)
        if do_check and not check(checkout, base_ref="main"):
            raise Fail("check failed; nothing was merged")
        tip = git(checkout, "rev-parse", "HEAD")
        if branch != "main":
            git(main, "merge", "-q", "--ff-only", branch)
        print("==> pushing main (%s)" % tip[:7], flush=True)
        env = dict(os.environ, DOTFILES_CHECKED=tip if do_check else "")
        if subprocess.run(["git", "-C", str(main), "push", "-q", "origin", "main"], env=env).returncode:
            raise Fail("push failed; main is merged locally but not published or deployed")
        changed = git(main, "diff", "--name-only", old, tip).splitlines()
        reinit = "home/.chezmoi.toml.tmpl" in changed
        problems = []
        if apply:
            if reinit and subprocess.run(["chezmoi", "init"]).returncode:
                problems.append("chezmoi init failed")
            print("==> chezmoi apply", flush=True)
            if subprocess.run(["chezmoi", "apply"]).returncode:
                problems.append("chezmoi apply failed")
            elif subprocess.run(["chezmoi", "verify", "--exclude", "scripts"]).returncode:
                problems.append("chezmoi verify reports drift; inspect `chezmoi status`")
        if sync:
            problems += [p for p in (sync_remote(r, tip, reinit) for r in REMOTES) if p]
        if branch != "main":
            if remove is None and herdr_space(main, checkout):
                print("==> kept %s: it has a herdr space (bin/land --remove-only %s removes both)" % (checkout, branch))
            elif remove is False:
                print("==> landed; remove the worktree with: bin/land --remove-only %s" % branch)
            else:
                remove_worktree(main, branch, checkout)
        if problems:
            raise Fail("landed %s, but deployment is incomplete:\n  " % tip[:7] + "\n  ".join(problems))
        print("==> landed %s" % tip[:7])
    finally:
        held.close()


def remove_only(cwd, branch):
    main = main_checkout(cwd)
    path = worktrees(main).get(branch)
    if not path:
        raise Fail("branch %s is not checked out in a worktree" % branch)
    if not is_ancestor(main, branch, "main"):
        raise Fail("%s is not merged into main" % branch)
    if dirty(path):
        raise Fail("%s has uncommitted changes" % path)
    if not remove_worktree(main, branch, path):
        raise Fail("run it from outside %s" % path)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bin/workflow.py")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="test and render a checkout without touching $HOME")
    c.add_argument("path", nargs="?", default=".")
    c.add_argument("--base", default="main", help="ref to render against (default main)")
    c.add_argument("--no-tests", action="store_true")
    c.add_argument("--no-render", action="store_true")
    l = sub.add_parser("land", help="rebase, check, fast-forward main, push, apply and sync")
    l.add_argument("branch", nargs="?", help="default: the current branch; `main` lands local main commits")
    l.add_argument("--no-check", action="store_true")
    l.add_argument("--no-apply", action="store_true")
    l.add_argument("--no-sync", action="store_true")
    gone = l.add_mutually_exclusive_group()
    gone.add_argument("--remove", action="store_true", help="force removal, even of a worktree with a herdr space")
    gone.add_argument("--keep", action="store_true", help="leave the worktree after landing")
    l.add_argument("--remove-only", metavar="BRANCH", help="only remove a landed worktree and branch")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    try:
        if args.command == "check":
            return 0 if check(Path(args.path), args.base, not args.no_tests, not args.no_render) else 1
        if args.remove_only:
            remove_only(repo, args.remove_only)
        else:
            land(repo, args.branch, not args.no_check, not args.no_apply, not args.no_sync,
                 True if args.remove else False if args.keep else None)
        return 0
    except Fail as error:
        print("%s: %s" % (args.command, error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
