"""bin/workflow.py: target comparison, validators and landing, on temporary repositories only."""
import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workflow as w  # noqa: E402

WHICH = shutil.which


def no_herdr(name, *args, **kwargs):
    return None if name == "herdr" else WHICH(name, *args, **kwargs)


class Validators(unittest.TestCase):
    def test_formats(self):
        self.assertIsNone(w.validate("a.json", b'{"a": 1}'))
        self.assertTrue(w.validate("a.json", b'{"a": '))
        self.assertIsNone(w.validate("x/c.toml", b'a = 1\n'))
        self.assertTrue(w.validate("x/c.toml", b'a = \n'))
        self.assertIsNone(w.validate("notes.txt", b"anything {"))

    def test_shells(self):
        self.assertEqual(w.shell_for(".zshrc", b""), "zsh")
        self.assertEqual(w.shell_for(".local/bin/x", b"#!/usr/bin/env bash\n"), "bash")
        self.assertEqual(w.shell_for(".local/bin/x", b"#!/bin/sh\n"), "sh")
        self.assertIsNone(w.shell_for(".local/bin/x", b"#!/usr/bin/env python3\n"))
        self.assertEqual(w.shell_for("a/b.sh", b"echo"), "bash")
        self.assertIsNone(w.validate(".local/bin/x", b"#!/bin/bash\necho ok\n"))
        error = w.validate(".local/bin/x", b"#!/bin/bash\nif then fi (\n")
        self.assertTrue(error)
        self.assertIn(".local/bin/x", error)

    def test_compare(self):
        base = {"a": ("file 644", "1", b""), "b": ("file 644", "2", b""), "d": ("dir", "", b"")}
        head = {"a": ("file 644", "1", b""), "b": ("file 755", "2", b""), "c": ("file 644", "3", b"")}
        self.assertEqual(w.compare(base, head), (["c"], ["d"], ["b"]))


class Land(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name).resolve()
        gitconfig = base / "gitconfig"
        gitconfig.write_text("[user]\n\tname = t\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n")
        env = mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(gitconfig), "GIT_CONFIG_NOSYSTEM": "1",
                                           "DOTFILES_LAND_HOST": "mac-pro"})
        env.start()
        self.addCleanup(env.stop)
        which = mock.patch.object(w.shutil, "which", no_herdr)
        which.start()
        self.addCleanup(which.stop)
        self.origin = base / "origin.git"
        self.main = base / "dotfiles"
        self.git(base, "init", "-q", "--bare", str(self.origin))
        self.git(base, "clone", "-q", str(self.origin), str(self.main))
        self.write(self.main, "home/dot_a", "a\n")
        self.commit(self.main, "init")
        self.git(self.main, "push", "-q", "origin", "main")
        self.wt = self.main / ".worktrees" / "topic"
        self.git(self.main, "worktree", "add", "-q", str(self.wt), "-b", "topic")

    def git(self, cwd, *args):
        return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                              text=True).stdout.strip()

    def write(self, cwd, name, text):
        path = cwd / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self, cwd, message):
        self.git(cwd, "add", "-A")
        self.git(cwd, "commit", "-q", "-m", message)

    def land(self, branch="topic", **kwargs):
        with mock.patch("sys.stdout"):
            w.land(self.main, branch, do_check=False, apply=False, sync=False,
                   remove=kwargs.pop("remove", False), **kwargs)

    def test_rebases_fast_forwards_and_pushes(self):
        self.write(self.wt, "home/dot_b", "b\n")
        self.commit(self.wt, "topic")
        self.write(self.main, "home/dot_c", "c\n")  # main moved on meanwhile
        self.commit(self.main, "other")
        self.land()
        tip = self.git(self.wt, "rev-parse", "HEAD")
        self.assertEqual(self.git(self.main, "rev-parse", "main"), tip)
        self.assertEqual(self.git(self.origin, "rev-parse", "main"), tip)
        self.assertEqual(self.git(self.main, "rev-list", "--count", "main"), "3")

    def test_refuses_dirty_main_and_dirty_branch(self):
        self.write(self.wt, "home/dot_b", "b\n")
        self.commit(self.wt, "topic")
        self.write(self.main, "home/dot_a", "edited\n")
        with self.assertRaisesRegex(w.Fail, "uncommitted changes under home/"):
            self.land()
        self.git(self.main, "checkout", "-q", "--", "home/dot_a")
        self.write(self.wt, "home/dot_b", "dirty\n")
        with self.assertRaisesRegex(w.Fail, "commit them first"):
            self.land()
        self.assertEqual(self.git(self.origin, "rev-list", "--count", "main"), "1")

    def test_untracked_outside_home_is_allowed(self):
        self.write(self.main, "node_modules/x", "x\n")
        self.write(self.wt, "home/dot_b", "b\n")
        self.commit(self.wt, "topic")
        self.land()
        self.assertEqual(self.git(self.origin, "rev-list", "--count", "main"), "2")

    def test_conflict_stops_without_merging(self):
        self.write(self.wt, "home/dot_a", "topic\n")
        self.commit(self.wt, "topic")
        self.write(self.main, "home/dot_a", "main\n")
        self.commit(self.main, "main")
        before = self.git(self.main, "rev-parse", "main")
        with self.assertRaisesRegex(w.Fail, "rebase stopped"):
            self.land()
        self.assertEqual(self.git(self.main, "rev-parse", "main"), before)
        self.assertEqual(self.git(self.origin, "rev-list", "--count", "main"), "1")

    def test_nothing_to_land_and_other_hosts(self):
        with self.assertRaisesRegex(w.Fail, "nothing to land"):
            self.land()
        with mock.patch.dict(os.environ, {"DOTFILES_LAND_HOST": "nuc"}):
            with self.assertRaisesRegex(w.Fail, "only mac-pro"):
                self.land()

    def test_lands_local_main_commits(self):
        self.write(self.main, "home/dot_b", "b\n")
        self.commit(self.main, "direct")
        self.land("main")
        self.assertEqual(self.git(self.origin, "rev-parse", "main"), self.git(self.main, "rev-parse", "main"))

    def test_remove_only_after_landing(self):
        self.write(self.wt, "home/dot_b", "b\n")
        self.commit(self.wt, "topic")
        with self.assertRaisesRegex(w.Fail, "not merged"):
            w.remove_only(self.main, "topic")
        self.land()
        with mock.patch("sys.stdout"):
            w.remove_only(self.main, "topic")
        self.assertFalse(self.wt.exists())
        self.assertNotIn("topic", self.git(self.main, "branch", "--list", "topic"))

    def test_auto_removes_plain_worktree(self):
        self.write(self.wt, "home/dot_b", "b\n")
        self.commit(self.wt, "topic")
        tip = self.git(self.wt, "rev-parse", "HEAD")
        self.land(remove=None)
        self.assertFalse(self.wt.exists())
        self.assertEqual(self.git(self.main, "branch", "--list", "topic"), "")
        self.assertEqual(self.git(self.origin, "rev-parse", "main"), tip)

    def test_auto_keeps_worktree_with_herdr_space(self):
        self.write(self.wt, "home/dot_b", "b\n")
        self.commit(self.wt, "topic")
        with mock.patch.object(w, "herdr_space", return_value="w1"):
            self.land(remove=None)
        self.assertTrue(self.wt.exists())

    def test_auto_keeps_worktree_containing_cwd(self):
        self.write(self.wt, "home/dot_b", "b\n")
        self.commit(self.wt, "topic")
        with mock.patch.object(w.Path, "cwd", return_value=self.wt):
            self.land(remove=None)
        self.assertTrue(self.wt.exists())

    def test_keep_and_remove_are_exclusive(self):
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as cm:
            w.main(["land", "--keep", "--remove"])
        self.assertEqual(cm.exception.code, 2)


class Runner(unittest.TestCase):
    """run_tests: sharded discovery, failures, filters, flaky reruns."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.co = Path(self.tmp.name).resolve() / "co"
        self.write("home/lib/test_a.py", self.module("A", ["test_one", "test_two"]))
        self.write("bin/test_b.py", self.module("B", ["test_three"]))

    @staticmethod
    def module(name, tests, extra=""):
        body = "".join("    def %s(self):\n        pass\n" % t for t in tests)
        return "import unittest\n%s\nclass %s(unittest.TestCase):\n%s" % (extra, name, body)

    def write(self, name, text):
        path = self.co / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def run_it(self, **kwargs):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ok = w.run_tests(self.co, jobs=2, **kwargs)
        return ok, out.getvalue()

    def test_job_selection(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            for cores, expected in ((1, 1), (18, 2), (None, 2)):
                with self.subTest(cores=cores), mock.patch.object(w.os, "cpu_count", return_value=cores):
                    self.assertEqual(w.test_jobs(None), expected)
        with mock.patch.dict(os.environ, {"DOTFILES_TEST_JOBS": "4"}):
            self.assertEqual(w.test_jobs(None), 4)
            self.assertEqual(w.test_jobs(3), 3)
        with mock.patch.dict(os.environ, {"DOTFILES_TEST_JOBS": "bad"}):
            self.assertEqual(w.test_jobs(3), 3)
            with self.assertRaisesRegex(w.Fail, "positive integer"):
                w.test_jobs(None)
        for value in ("", "abc", "0", "-1"):
            with self.subTest(value=value), mock.patch.dict(os.environ, {"DOTFILES_TEST_JOBS": value}):
                with self.assertRaisesRegex(w.Fail, "positive integer"):
                    w.test_jobs(None)
        for value in (0, -1):
            with self.subTest(explicit=value), self.assertRaisesRegex(w.Fail, "positive integer"):
                w.run_tests(self.co, jobs=value)

    def test_all_pass_reports_count(self):
        ok, out = self.run_it()
        self.assertTrue(ok, out)
        self.assertIn("3 passed", out)

    def test_skip_is_reported(self):
        self.write("home/lib/test_a.py", "import unittest\nclass A(unittest.TestCase):\n"
                   "    @unittest.skip('optional tool missing')\n    def test_skip(self): pass\n")
        ok, out = self.run_it()
        self.assertTrue(ok, out)
        self.assertIn("test_skip", out)
        self.assertIn("optional tool missing", out)

    def test_failure_fails_and_names_test(self):
        self.write("home/lib/test_a.py", self.module("A", ["test_one"]) + "    def test_bad(self):\n        self.fail('boom')\n")
        ok, out = self.run_it()
        self.assertFalse(ok)
        self.assertIn("test_bad", out)
        self.assertIn("boom", out)

    def test_filter_selects(self):
        ok, out = self.run_it(filters=["test_b"])
        self.assertTrue(ok, out)
        self.assertIn("1 passed", out)
        ok, out = self.run_it(filters=["nothing_matches"])
        self.assertFalse(ok)
        self.assertIn("no tests match", out)

    def test_flaky_passes_with_warning(self):
        mark = Path(self.tmp.name) / "mark"
        flaky = ("import os, pathlib\nclass F(unittest.TestCase):\n    def test_flaky(self):\n"
                 "        mark = pathlib.Path(os.environ['FLAKY_MARK'])\n"
                 "        if not mark.exists():\n            mark.write_text('x')\n            self.fail('first run')\n")
        self.write("home/lib/test_f.py", "import unittest\n" + flaky)
        with mock.patch.dict(os.environ, {"FLAKY_MARK": str(mark)}):
            ok, out = self.run_it()
        self.assertTrue(ok, out)
        self.assertIn("FLAKY", out)
        self.assertIn("test_flaky", out)

    def test_import_error_fails(self):
        self.write("home/lib/test_c.py", "import nonexistent_xyz\n")
        ok, out = self.run_it()
        self.assertFalse(ok)
        self.assertIn("nonexistent_xyz", out)


class CheckCache(unittest.TestCase):
    """check: passing clean trees are remembered; docs-only changes skip the tests."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve() / "repo"
        self.repo.mkdir()
        env = mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                                           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                                           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})
        env.start()
        self.addCleanup(env.stop)
        self.git("init", "-q", "-b", "main")
        self.write("home/dot_a", "a\n")
        self.commit("init")
        self.git("checkout", "-q", "-b", "topic")
        self.tests = mock.Mock(return_value=True)
        for name, replacement in (("run_tests", self.tests), ("render_diff", mock.Mock(return_value=True))):
            patch = mock.patch.object(w, name, replacement)
            patch.start()
            self.addCleanup(patch.stop)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout.strip()

    def write(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def check(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ok = w.check(self.repo)
        return ok, out.getvalue()

    def test_clean_pass_is_remembered(self):
        self.write("home/dot_b", "b\n")
        self.commit("topic")
        self.assertTrue(self.check()[0])
        ok, out = self.check()
        self.assertTrue(ok)
        self.assertEqual(self.tests.call_count, 1)
        self.assertIn("already passed", out)

    def test_dirty_not_remembered(self):
        self.write("home/dot_b", "b\n")
        self.check()
        self.check()
        self.assertEqual(self.tests.call_count, 2)

    def test_failure_not_remembered(self):
        self.write("home/dot_b", "b\n")
        self.commit("topic")
        self.tests.side_effect = [False, True]
        self.assertFalse(self.check()[0])
        self.assertTrue(self.check()[0])
        self.assertEqual(self.tests.call_count, 2)

    def test_docs_only_skips_tests(self):
        self.write("docs/x.md", "x\n")
        self.commit("docs")
        ok, out = self.check()
        self.assertTrue(ok)
        self.tests.assert_not_called()
        self.assertIn("tests: skipped", out)


class PrePush(unittest.TestCase):
    """.githooks/pre-push skips trees bin/check already passed."""

    HOOK = Path(__file__).resolve().parents[1] / ".githooks/pre-push"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve() / "repo"
        (self.repo / ".githooks").mkdir(parents=True)
        shutil.copy(self.HOOK, self.repo / ".githooks/pre-push")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k != "DOTFILES_CHECKED"}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t",
                        GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
        self.git("init", "-q", "-b", "main")
        (self.repo / "f").write_text("f\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")
        self.sha = self.git("rev-parse", "HEAD")
        self.tree = self.git("rev-parse", "HEAD^{tree}")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True,
                              text=True, env=self.env).stdout.strip()

    def push(self):
        line = "refs/heads/main %s refs/heads/main %s\n" % (self.sha, "0" * 40)
        return subprocess.run(["sh", ".githooks/pre-push"], input=line, cwd=self.repo, env=self.env,
                              capture_output=True, text=True).returncode

    def test_skips_checked_tree(self):
        (self.repo / ".git/dotfiles-checked").write_text(self.tree + "\n")
        self.assertEqual(self.push(), 0)

    def test_unchecked_tree_runs_check(self):
        self.assertNotEqual(self.push(), 0)  # no bin/check in the temporary repository


class Converge(unittest.TestCase):
    """bin/converge: reruns rendered provisioning scripts with a fake chezmoi."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name).resolve()
        self.src = base / "tree" / "home"
        scripts = self.src / ".chezmoiscripts"
        scripts.mkdir(parents=True)
        (self.src / "lib").mkdir()
        (self.src / "lib/apply_guard.sh").write_text("#!/bin/sh\nexit ${GUARD_RC:-0}\n")
        self.log = base / "log"
        for name, body in (("before_00-boot", "echo boot >> %s"), ("after_10-a", "echo a $DOTFILES_CONVERGE_MANUAL $CHEZMOI_SOURCE_DIR >> %s"),
                           ("after_20-empty", "   "), ("after_30-fail", "echo fail >> %s; exit 3"),
                           ("after_40-b", "echo b >> %s")):
            text = body if body.strip() == "" else "#!/bin/sh\n" + body % self.log + "\n"
            (scripts / ("run_onchange_%s.sh.tmpl" % name)).write_text(text)
        bindir = base / "bin"
        bindir.mkdir()
        chezmoi = bindir / "chezmoi"
        chezmoi.write_text('#!/bin/sh\ncase "$1" in\n  source-path) echo %s ;;\n  execute-template) cat "$3" ;;\nesac\n' % self.src)
        chezmoi.chmod(0o755)
        patch = mock.patch.dict(os.environ, {"PATH": "%s:%s" % (bindir, os.environ["PATH"])})
        patch.start()
        self.addCleanup(patch.stop)

    def logged(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_all_scripts_run_in_order_and_failure_is_reported(self):
        with mock.patch("sys.stderr"):
            self.assertEqual(w.converge([]), 1)
        self.assertEqual(self.logged(), ["boot", "a 1 %s" % self.src, "fail", "b"])

    def test_named_script_only(self):
        self.assertEqual(w.converge(["a"]), 0)
        self.assertEqual(self.logged(), ["a 1 %s" % self.src])

    def test_unknown_name_is_refused(self):
        with self.assertRaises(w.Fail) as cm:
            w.converge(["nope"])
        self.assertIn("unknown", str(cm.exception))
        self.assertEqual(self.logged(), [])

    def test_guard_refusal_runs_nothing(self):
        with mock.patch.dict(os.environ, {"GUARD_RC": "1"}), self.assertRaises(w.Fail):
            w.converge([])
        self.assertEqual(self.logged(), [])

    def test_script_name(self):
        self.assertEqual(w.script_name(Path("run_onchange_after_10-brew-bundle.sh.tmpl")), "brew-bundle")
        self.assertEqual(w.script_name(Path("run_onchange_before_00-bootstrap.sh.tmpl")), "bootstrap")

    def test_sync_remote_keeps_going(self):
        calls = []
        with mock.patch.object(w.subprocess, "run", side_effect=lambda cmd, **k: calls.append(cmd) or mock.Mock(returncode=0)), \
                mock.patch.object(w, "run", return_value=mock.Mock(stdout="tip\n")):
            self.assertIsNone(w.sync_remote("spencer@nuc", "tip", True))
        self.assertIn("update --no-tty --keep-going", calls[0][-1])
        self.assertIn("apply --no-tty --keep-going", calls[0][-1])


if __name__ == "__main__":
    unittest.main()
