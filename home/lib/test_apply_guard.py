"""apply_guard.sh and its hooks in .chezmoi.toml.tmpl; temporary repositories only."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "lib/apply_guard.sh"
CHEZMOI = shutil.which("chezmoi")


class Guard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        gitconfig = base / "gitconfig"
        gitconfig.write_text("[user]\n\tname = t\n\temail = t@example.com\n")
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=str(gitconfig), GIT_CONFIG_NOSYSTEM="1")
        self.env.pop("DOTFILES_ALLOW_DIRTY_APPLY", None)
        self.repo = base / "dotfiles"
        self.git(base, "init", "-q", "-b", "main", str(self.repo))
        (self.repo / "home").mkdir()
        (self.repo / "home/dot_a").write_text("a\n")
        self.git(self.repo, "add", "-A")
        self.git(self.repo, "commit", "-q", "-m", "init")

    def git(self, cwd, *args):
        subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=self.env)

    def guard(self, tree, **env):
        return subprocess.run(["sh", str(GUARD)], capture_output=True, text=True,
                              env=dict(self.env, CHEZMOI_WORKING_TREE=str(tree), **env))

    def assertRefused(self, result, reason):
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(reason, result.stderr)

    def test_clean_main_passes(self):
        result = self.guard(self.repo)
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_changes_outside_home_pass(self):
        (self.repo / "README.md").write_text("draft\n")
        self.assertEqual(self.guard(self.repo).returncode, 0)

    def test_uncommitted_source_is_refused(self):
        (self.repo / "home/dot_a").write_text("edited\n")
        (self.repo / "home/dot_new").write_text("new\n")
        result = self.guard(self.repo)
        self.assertRefused(result, "uncommitted changes under home/")
        self.assertIn("home/dot_a", result.stderr)
        self.assertIn("home/dot_new", result.stderr)

    def test_worktree_branch_and_non_git_are_refused(self):
        wt = self.repo / ".worktrees/topic"
        self.git(self.repo, "worktree", "add", "-q", str(wt), "-b", "topic")
        self.assertRefused(self.guard(wt), "linked worktree")
        self.git(self.repo, "switch", "-q", "-c", "other")
        self.assertRefused(self.guard(self.repo), "on other, not main")
        self.assertRefused(self.guard(Path(self.tmp.name)), "not a Git checkout")

    def test_override(self):
        (self.repo / "home/dot_a").write_text("edited\n")
        self.assertEqual(self.guard(self.repo, DOTFILES_ALLOW_DIRTY_APPLY="1").returncode, 0)


@unittest.skipUnless(CHEZMOI, "chezmoi is not installed")
class Config(unittest.TestCase):
    def test_hooks_on_every_host_but_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp, "chezmoi.toml")
            empty.write_text("")
            for host in ("mac-pro", "mac-air", "nuc", "agentbox-box"):
                with self.subTest(host=host):
                    rendered = subprocess.run(
                        [CHEZMOI, "--config", str(empty), "--source", str(ROOT.parent), "execute-template",
                         "--init", "--promptChoice", "host=" + host, "--promptString", "extras="],
                        input=(ROOT / ".chezmoi.toml.tmpl").read_text(), capture_output=True, text=True,
                        check=True).stdout
                    hooks = tomllib.loads(rendered).get("hooks", {})
                    if host == "agentbox-box":
                        self.assertEqual(hooks, {})
                        continue
                    for command in ("apply", "update"):
                        self.assertEqual(hooks[command]["pre"],
                                         {"command": "sh", "args": [str(ROOT.parent / "home/lib/apply_guard.sh")]})


if __name__ == "__main__":
    unittest.main()
