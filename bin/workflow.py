#!/usr/bin/env python3
"""bin/check, bin/land and bin/converge: the dotfiles change workflow (AGENTS.md "Source and change workflow").

$HOME tracks committed main. Sessions work in .worktrees/<branch> and never apply;
`check` proves a checkout without touching $HOME, `land` is the only way a change
reaches it: rebase, check, fast-forward main, push, apply, sync the NUC, then remove
the landed worktree unless someone is using it (a herdr space, or the shell inside).
`converge` reruns this host's provisioning scripts by hand (drift repair). `test` runs the
suite alone, in parallel shards (`bin/test [filter...]`).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib

REMOTES = ("spencer@nuc",)  # hosts that `chezmoi update` after a push
REMOTE_CHEZMOI = "~/.local/bin/chezmoi"
SSH = ("ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10")
PUSHING_HOSTS = ("mac-pro", "mac-air")  # the NUC and boxes only pull (AGENTS.md)
SLOW = 2.0  # seconds: tests slower than this are listed after a run
SHARD_TIMEOUT = 600
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

DISCOVER = r"""
import sys, unittest
def flat(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flat(item)
        else:
            yield item
bad = False
for test in flat(unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:])):
    print(test.id())
    bad = bad or test.id().startswith("unittest.loader._FailedTest.")
sys.exit(1 if bad else 0)
"""
DURATIONS = ["--durations", "0"] if sys.version_info >= (3, 12) else []
FAILED = re.compile(r"^(?:FAIL|ERROR): \S+ \(([^)]+)\)", re.M)
TIMED = re.compile(r"^\s*([\d.]+)s\s+\S+ \(([^)]+)\)", re.M)


def took(seconds):
    return "%.1fs" % seconds if seconds < 60 else "%dm%02ds" % divmod(round(seconds), 60)


def unittest_cmd(*ids, extra=()):
    return [sys.executable, "-B", "-m", "unittest", "-q", *extra, *ids]


def run_shard(root, ids):
    """(passed, tests run, {test id: seconds}, output to show) for one shard, rerunning failures once."""
    try:
        first = subprocess.run(unittest_cmd(*ids, extra=DURATIONS), cwd=root, capture_output=True,
                               text=True, timeout=SHARD_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, 0, {}, "shard timed out after %ds: %s\n" % (SHARD_TIMEOUT, " ".join(ids))
    text = first.stdout + first.stderr
    count = re.search(r"Ran (\d+) tests?", text)
    count = int(count.group(1)) if count else 0
    times = {name: float(sec) for sec, name in TIMED.findall(text)}
    if first.returncode == 0:
        return True, count, times, ""
    failing = list(dict.fromkeys(FAILED.findall(text)))
    if not failing:
        return False, count, times, text
    again = subprocess.run(unittest_cmd(*failing), cwd=root, capture_output=True, text=True)
    if again.returncode == 0:
        flaky = "".join("  FLAKY (passed on rerun, fix it): %s\n" % name for name in failing)
        return True, count, times, flaky + text
    return False, count, times, again.stdout + again.stderr


def run_tests(checkout, filters=(), jobs=None):
    """The whole suite (or the test ids containing a filter) in parallel shards of one process each."""
    started = time.monotonic()
    roots = [(checkout / "home", ["lib." + p.stem for p in sorted((checkout / "home/lib").glob("test_*.py"))])]
    if (checkout / "bin").is_dir():
        roots.append((checkout / "bin", [p.stem for p in sorted((checkout / "bin").glob("test_*.py"))]))
    jobs = jobs or min(os.cpu_count() or 2, 8)
    print("==> tests", flush=True)
    shards = []
    for root, modules in roots:
        found = subprocess.run([sys.executable, "-B", "-c", DISCOVER, *modules], cwd=root,
                               capture_output=True, text=True)
        ids = found.stdout.split()
        if found.returncode:
            # The loader hides the cause of a failed import; importing each module shows it.
            for module in modules:
                shown = subprocess.run([sys.executable, "-B", "-c", "import " + module], cwd=root,
                                       capture_output=True, text=True)
                print(shown.stderr, end="")
            print("==> tests: FAILED (import errors)", flush=True)
            return False
        ids = [i for i in ids if not filters or any(f in i for f in filters)]
        for n in range(min(jobs, len(ids))):
            shards.append((root, ids[n::min(jobs, len(ids))]))
    if not shards:
        print("==> tests: no tests match %s" % " ".join(filters), flush=True)
        return False
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda shard: run_shard(*shard), shards))
    total, times, ok = 0, {}, True
    for passed, count, timed, output in results:
        ok &= passed
        total += count
        times.update(timed)
        if output:
            print(output, end="" if output.endswith("\n") else "\n")
    elapsed = took(time.monotonic() - started)
    if ok:
        print("==> tests: %d passed in %s (%d shards)" % (total, elapsed, len(shards)), flush=True)
    else:
        print("==> tests: FAILED in %s" % elapsed, flush=True)
    for name, seconds in sorted(times.items(), key=lambda kv: -kv[1])[:10]:
        if seconds >= SLOW:
            print("  slow: %5.1fs %s" % (seconds, name))
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
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = (pool.submit(render, exported, tmp / "b"), pool.submit(render, checkout, tmp / "h"))
            base, head = (future.result() for future in pending)
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


def checked_file(checkout):
    """Trees that passed a full check, one per line; shared by every worktree (and the pre-push hook)."""
    return Path(git(checkout, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "dotfiles-checked"


def clean_tree(checkout):
    """The tree hash of a clean checkout's HEAD; None when it has uncommitted changes."""
    return None if dirty(checkout) else git(checkout, "rev-parse", "HEAD^{tree}")


def remember(checkout, tree):
    path = checked_file(checkout)
    lines = path.read_text().split() if path.exists() else []
    lines = [line for line in lines if line != tree] + [tree]
    scratch = path.with_name(path.name + ".tmp")
    scratch.write_text("\n".join(lines[-100:]) + "\n")
    os.replace(scratch, path)


def needs_tests(checkout, base_ref):
    """False only when every change since the merge-base is outside what the tests read."""
    paths = []
    for args in (("diff", "--name-only", "%s...HEAD" % base_ref), ("diff", "--name-only", "HEAD"),
                 ("ls-files", "--others", "--exclude-standard")):
        result = run(["git", "-C", str(checkout), *args], check=False)
        if result.returncode:
            return True
        paths += result.stdout.split("\n")
    return any(path.startswith(("home/", "bin/", ".githooks/")) for path in paths)


def check(checkout, base_ref="main", tests=True, targets=True):
    started = time.monotonic()
    checkout = toplevel(checkout)
    tree = clean_tree(checkout)
    if tests and targets and tree:
        seen = checked_file(checkout)
        if seen.exists() and tree in seen.read_text().split():
            print("==> check: ok (already passed for tree %s)" % tree[:7], flush=True)
            return True
    ok = True
    if tests:
        if needs_tests(checkout, base_ref):
            ok &= run_tests(checkout)
        else:
            print("==> tests: skipped (nothing under home/, bin/ or .githooks/ changed since %s)" % base_ref, flush=True)
    if targets:
        ok &= render_diff(checkout, base_ref)
    if ok and tests and targets and tree:
        remember(checkout, tree)
    print("==> check: %s in %s" % ("ok" if ok else "FAILED", took(time.monotonic() - started)), flush=True)
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
    steps = ["%s update --no-tty --keep-going" % REMOTE_CHEZMOI]
    if reinit:
        steps += ["%s init --no-tty" % REMOTE_CHEZMOI, "%s apply --no-tty --keep-going" % REMOTE_CHEZMOI]
    print("==> %s: %s" % (remote, " && ".join(steps)), flush=True)
    if subprocess.run([*SSH, remote, " && ".join(steps)]).returncode:
        return "%s: chezmoi failed (an apt change needs an interactive `ssh %s` and `chezmoi apply`)" % (remote, remote)
    head = run([*SSH, remote, "git -C ~/Projects/dotfiles rev-parse HEAD"], check=False)
    if head.stdout.strip() != tip:
        return "%s: checkout is at %s, not %s" % (remote, head.stdout.strip()[:7] or "?", tip[:7])
    return None


def script_name(path):
    """`run_onchange_after_10-brew-bundle.sh.tmpl` -> `brew-bundle`."""
    name = path.name.removesuffix(".sh.tmpl")
    name = re.sub(r"^run_onchange_(before|after)_", "", name)
    return re.sub(r"^\d+-", "", name)


def converge(names):
    """Rerun this host's provisioning scripts now, without an input change (drift repair).
    Services are ensured loaded but not reloaded. Renders from the deploy checkout, which
    must be clean main, so unlanded scripts never run on $HOME."""
    src = Path(run(["chezmoi", "source-path"]).stdout.strip())
    tree = src.parent
    env = {**os.environ, "CHEZMOI_WORKING_TREE": str(tree), "CHEZMOI_COMMAND": "converge"}
    if subprocess.run(["sh", str(src / "lib/apply_guard.sh")], env=env).returncode:
        raise Fail("the deploy checkout must be clean main")
    scripts = sorted((src / ".chezmoiscripts").glob("run_onchange_before_*.sh.tmpl")) + \
        sorted((src / ".chezmoiscripts").glob("run_onchange_after_*.sh.tmpl"))
    known = [script_name(p) for p in scripts]
    unknown = [n for n in names if n not in known]
    if unknown:
        raise Fail("unknown script(s): %s; known: %s" % (", ".join(unknown), ", ".join(known)))
    failed = []
    for path in scripts:
        name = script_name(path)
        if names and name not in names:
            continue
        rendered = run(["chezmoi", "execute-template", "--file", str(path)]).stdout
        if not rendered.strip():
            continue
        print("==> converge %s" % name, flush=True)
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as handle:
            handle.write(rendered)
        os.chmod(handle.name, 0o700)
        try:
            result = subprocess.run([handle.name], env={**env, "DOTFILES_CONVERGE_MANUAL": "1",
                                                          "CHEZMOI_SOURCE_DIR": str(src)})
        finally:
            os.unlink(handle.name)
        if result.returncode:
            failed.append(name)
    if failed:
        print("converge: failed: %s" % " ".join(failed), file=sys.stderr)
        return 1
    return 0


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
    began, phases = time.monotonic(), {}
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
        mark = time.monotonic()
        if do_check and not check(checkout, base_ref="main"):
            raise Fail("check failed; nothing was merged")
        if do_check:
            phases["check"] = time.monotonic() - mark
        tip = git(checkout, "rev-parse", "HEAD")
        if branch != "main":
            git(main, "merge", "-q", "--ff-only", branch)
        print("==> pushing main (%s)" % tip[:7], flush=True)
        env = dict(os.environ, DOTFILES_CHECKED=tip if do_check else "")
        mark = time.monotonic()
        if subprocess.run(["git", "-C", str(main), "push", "-q", "origin", "main"], env=env).returncode:
            raise Fail("push failed; main is merged locally but not published or deployed")
        phases["push"] = time.monotonic() - mark
        changed = git(main, "diff", "--name-only", old, tip).splitlines()
        reinit = "home/.chezmoi.toml.tmpl" in changed
        problems = []
        mark = time.monotonic()
        if apply:
            if reinit and subprocess.run(["chezmoi", "init"]).returncode:
                problems.append("chezmoi init failed")
            print("==> chezmoi apply", flush=True)
            if subprocess.run(["chezmoi", "apply", "--keep-going"]).returncode:
                problems.append("chezmoi apply failed")
            elif subprocess.run(["chezmoi", "verify", "--exclude", "scripts"]).returncode:
                problems.append("chezmoi verify reports drift; inspect `chezmoi status`")
        if apply:
            phases["apply"] = time.monotonic() - mark
        mark = time.monotonic()
        if sync:
            problems += [p for p in (sync_remote(r, tip, reinit) for r in REMOTES) if p]
            phases["nuc"] = time.monotonic() - mark
        if branch != "main":
            if remove is None and herdr_space(main, checkout):
                print("==> kept %s: it has a herdr space (bin/land --remove-only %s removes both)" % (checkout, branch))
            elif remove is False:
                print("==> landed; remove the worktree with: bin/land --remove-only %s" % branch)
            else:
                remove_worktree(main, branch, checkout)
        if problems:
            raise Fail("landed %s, but deployment is incomplete:\n  " % tip[:7] + "\n  ".join(problems))
        print("==> landed %s in %s (%s)" % (tip[:7], took(time.monotonic() - began),
                                           ", ".join("%s %s" % (k, took(v)) for k, v in phases.items())))
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
    t = sub.add_parser("test", help="run the test suite in parallel shards")
    t.add_argument("filters", nargs="*", help="substrings of test ids (default: all)")
    t.add_argument("--jobs", type=int)
    v = sub.add_parser("converge", help="rerun provisioning scripts now (drift repair)")
    v.add_argument("names", nargs="*", help="script names (default: all)")
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
        if args.command == "test":
            return 0 if run_tests(repo, args.filters, args.jobs) else 1
        if args.command == "converge":
            return converge(args.names)
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
