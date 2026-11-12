"""bin/workflow.py: target comparison, validators and landing, on temporary repositories only."""
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


if __name__ == "__main__":
    unittest.main()
