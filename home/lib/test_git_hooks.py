"""Contract tests for the global commit-msg-style and publish-guard hooks and the tidy alias.

Every git call runs against a temporary global config and HOME; live config is never read.
"""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HOME_SRC = Path(__file__).resolve().parents[1]
HOOKS = HOME_SRC / "dot_config/git/hooks"
MSG_HOOK = HOOKS / "executable_commit-msg-style"
PUSH_HOOK = HOOKS / "executable_publish-guard"
GITCONFIG = HOME_SRC / "dot_gitconfig.tmpl"

loader = importlib.machinery.SourceFileLoader("commit_msg_style", str(MSG_HOOK))
spec = importlib.util.spec_from_loader(loader.name, loader)
style = importlib.util.module_from_spec(spec)
loader.exec_module(style)


def tidy_alias():
    for line in GITCONFIG.read_text().splitlines():
        if line.strip().startswith("tidy = "):
            return line.strip()
    return None


class Subjects(unittest.TestCase):
    def test_subject_accepts_conventional(self):
        self.assertEqual(style.check("feat(app): add the weather icon"), (0, []))

    def test_subject_rejects_missing_type(self):
        code, lines = style.check("Add weather icon")
        self.assertEqual(code, 1)
        self.assertIn("conventional type", lines[0])

    def test_subject_warns_over_72(self):
        subject = "feat: " + "x" * 74
        code, lines = style.check(subject)
        self.assertEqual(code, 0)
        self.assertIn("aim for 72", lines[0])

    def test_subject_rejects_over_100(self):
        code, lines = style.check("feat: " + "x" * 96)
        self.assertEqual(code, 1)
        self.assertIn("limit 100", lines[0])

    def test_subject_exemptions(self):
        for subject in ("fixup! x", "squash! x", "amend! x", "Merge branch 'x'", 'Revert "feat: x"', 'Reapply "feat: x"'):
            with self.subTest(subject=subject):
                self.assertEqual(style.check(subject), (0, []))

    def test_subject_ignores_comments_and_scissors(self):
        text = "# c\n\nfeat: x\n# ------------------------ >8 ------------------------\nAdd y\n"
        self.assertEqual(style.subject_of(text), "feat: x")


class GitCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="git-hooks-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.tmp),
            "GIT_CONFIG_GLOBAL": str(self.tmp / "gitconfig"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
        alias = tidy_alias()
        config = (
            "[user]\n\tname = T\n\temail = t@example.com\n"
            "[init]\n\tdefaultBranch = main\n"
            "[rebase]\n\tautosquash = true\n"
            f'[hook "commit-msg-style"]\n\tcommand = python3 {MSG_HOOK}\n\tevent = commit-msg\n'
            f'[hook "publish-guard"]\n\tcommand = python3 {PUSH_HOOK}\n\tevent = pre-push\n'
        )
        if alias:
            config += "[alias]\n\t" + alias + "\n"
        (self.tmp / "gitconfig").write_text(config)
        self.remote = self.tmp / "remote.git"
        self.git("init", "-q", "--bare", str(self.remote), cwd=self.tmp)
        self.work = self.clone("work")
        self.commit("feat: base", "base.txt", "base\n")
        self.git("push", "-q", "origin", "HEAD:main", cwd=self.work)
        self.git("branch", "-q", "--set-upstream-to=origin/main", "main", cwd=self.work, check=False)

    def clone(self, name):
        path = self.tmp / name
        self.git("init", "-q", str(path), cwd=self.tmp)
        self.git("remote", "add", "origin", str(self.remote), cwd=path)
        return path

    def git(self, *args, cwd=None, check=True):
        result = subprocess.run(
            ["git", *args], cwd=cwd or self.work, env=self.env, capture_output=True, text=True
        )
        if check and result.returncode:
            raise AssertionError(f"git {' '.join(args)} failed:\n{result.stdout}{result.stderr}")
        return result

    def commit(self, message, name=None, content=None, cwd=None):
        cwd = cwd or self.work
        if name:
            path = Path(cwd) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content if content is not None else message + "\n")
            self.git("add", name, cwd=cwd)
            return self.git("commit", "-q", "-m", message, cwd=cwd)
        return self.git("commit", "-q", "--allow-empty", "-m", message, cwd=cwd)

    def remote_head(self, branch="main"):
        result = self.git("rev-parse", "-q", "--verify", f"refs/heads/{branch}", cwd=self.remote, check=False)
        return result.stdout.strip()

    def subjects(self, rng):
        return self.git("log", "--format=%s", rng).stdout.splitlines()


class Hooks(GitCase):
    def test_commit_hook_runs_with_repo_hook(self):
        hooks = self.work / ".githooks"
        hooks.mkdir()
        marker = self.tmp / "marker"
        script = hooks / "commit-msg"
        script.write_text(f"#!/bin/sh\ntouch {marker}\n")
        script.chmod(0o755)
        self.git("config", "core.hooksPath", ".githooks")
        before = self.git("rev-parse", "HEAD").stdout
        refused = self.git("commit", "--allow-empty", "-m", "Add x", check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, before)
        self.commit("feat: x")
        self.assertTrue(marker.exists())

    def test_push_blocks_fixup_to_main(self):
        before = self.remote_head()
        self.commit("feat: a", "a.txt", "a\n")
        self.commit("fixup! feat: a", "a.txt", "a2\n")
        result = self.git("push", "origin", "HEAD:main", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to push", result.stderr)
        self.assertEqual(self.remote_head(), before)

    def test_push_allows_fixup_to_dev(self):
        self.commit("feat: a", "a.txt", "a\n")
        self.commit("fixup! feat: a", "a.txt", "a2\n")
        self.git("push", "origin", "HEAD:dev")
        self.assertTrue(self.remote_head("dev"))

    def test_publish_branch_config(self):
        self.git("config", "publish.branch", "prod")
        self.commit("feat: a", "a.txt", "a\n")
        self.commit("fixup! feat: a", "a.txt", "a2\n")
        result = self.git("push", "origin", "HEAD:prod", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to push", result.stderr)
        self.git("push", "origin", "HEAD:main")

    def test_branch_deletion_and_tags_pass(self):
        self.commit("feat: a", "a.txt", "a\n")
        self.commit("fixup! feat: a", "a.txt", "a2\n")
        self.git("push", "origin", "HEAD:dev")
        self.git("tag", "v1")
        self.git("push", "origin", "v1")
        self.git("push", "origin", ":dev")
        self.assertEqual(self.remote_head("dev"), "")

    def test_followup_warning(self):
        self.commit("feat: a", "a.txt", "a\n")
        self.commit("fix: a spacing", "a.txt", "a2\n")
        result = self.git("push", "origin", "HEAD:dev")
        self.assertIn("fold it in", result.stderr)

    def test_published_target_warning(self):
        self.commit("feat: a", "a.txt", "a\n")
        self.git("push", "origin", "HEAD:main")
        self.commit("fixup! feat: a", "a.txt", "a2\n")
        result = self.git("push", "origin", "HEAD:dev")
        self.assertIn("already on origin/main", result.stderr)

    def test_repo_pre_push_hook_still_gets_stdin(self):
        hooks = self.work / ".githooks"
        hooks.mkdir()
        seen = self.tmp / "stdin"
        script = hooks / "pre-push"
        script.write_text(f"#!/bin/sh\ncat > {seen}\n")
        script.chmod(0o755)
        self.git("config", "core.hooksPath", ".githooks")
        self.commit("feat: a", "a.txt", "a\n")
        self.git("push", "origin", "HEAD:dev")
        self.assertRegex(seen.read_text(), r"^\S+ [0-9a-f]{40} refs/heads/dev 0{40}$")
        self.commit("fixup! feat: a", "a.txt", "a2\n")
        blocked = self.git("push", "origin", "HEAD:main", check=False)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("refusing to push", blocked.stderr)

    def test_gitconfig_registers_hooks(self):
        text = GITCONFIG.read_text()
        self.assertRegex(text, r'\[hook "commit-msg-style"\]\n\tcommand = [^\n]+\n\tevent = commit-msg\n')
        self.assertRegex(text, r'\[hook "publish-guard"\]\n\tcommand = [^\n]+\n\tevent = pre-push\n')
        self.assertTrue(MSG_HOOK.exists() and PUSH_HOOK.exists())


class Tidy(GitCase):
    def setUp(self):
        super().setUp()
        self.assertIsNotNone(tidy_alias(), "the tidy alias is missing from dot_gitconfig.tmpl")

    def test_tidy_folds_fixups(self):
        self.commit("feat: a", "a.txt", "a\n")
        self.commit("feat: b", "b.txt", "b\n")
        self.commit("fixup! feat: a", "a.txt", "a2\n")
        result = self.git("tidy")
        self.assertEqual(self.subjects("origin/main.."), ["feat: b", "feat: a"])
        self.assertEqual(self.git("show", "HEAD~1:a.txt").stdout, "a2\n")
        self.assertNotIn("tip tree changed", result.stderr)

    def test_tidy_keeps_base(self):
        self.git("checkout", "-q", "-b", "dev")
        fork_point = self.git("rev-parse", "HEAD").stdout.strip()
        self.commit("feat: a", "a.txt", "a\n")
        other = self.clone("other")
        self.git("pull", "-q", "origin", "main", cwd=other)
        self.commit("feat: elsewhere", "e.txt", "e\n", cwd=other)
        self.git("push", "-q", "origin", "HEAD:main", cwd=other)
        self.git("fetch", "-q")
        self.commit("fixup! feat: a", "a.txt", "a2\n")
        self.git("tidy", "origin/main~1")
        self.assertEqual(self.git("merge-base", "HEAD", "origin/main").stdout.strip(), fork_point)
        self.assertEqual(self.subjects(f"{fork_point}.."), ["feat: a"])

    def test_tidy_refuses_dirty_and_merges(self):
        (self.work / "base.txt").write_text("dirty\n")
        dirty = self.git("tidy", check=False)
        self.assertEqual(dirty.returncode, 1)
        self.assertIn("commit or drop", dirty.stderr)
        self.git("checkout", "-q", "--", "base.txt")
        self.git("checkout", "-q", "-b", "side")
        self.commit("feat: side", "side.txt", "s\n")
        self.git("checkout", "-q", "main")
        self.commit("feat: main work", "m.txt", "m\n")
        self.git("merge", "-q", "--no-ff", "--no-edit", "side")
        merged = self.git("tidy", check=False)
        self.assertEqual(merged.returncode, 1)
        self.assertIn("merge commits since", merged.stderr)

    def test_tidy_nothing_to_do(self):
        result = self.git("tidy")
        self.assertIn("nothing after", result.stdout)


if __name__ == "__main__":
    unittest.main()
