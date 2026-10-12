"""Contract tests for the prompt helper; never read or alter live repos/config."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "dot_local/bin/executable_git-status-line"
loader = importlib.machinery.SourceFileLoader("git_status_line", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
g = importlib.util.module_from_spec(spec)
loader.exec_module(g)


class Summary(unittest.TestCase):
    def parse(self, changes=b"", tracking=True):
        headers = b"# branch.oid abcdef123\0# branch.head main\0"
        if tracking:
            headers += b"# branch.upstream origin/main\0# branch.ab +2 -1\0"
        return g.parse_status(headers + changes)

    def test_herdr_preserves_original_space_height(self):
        config = (SOURCE.parents[2] / "dot_config/herdr/config.toml.tmpl").read_text()
        block = config.split("[ui.sidebar.spaces]", 1)[1].split("\n[session]", 1)[0]
        rows = block.split("rows = [", 1)[1]
        self.assertEqual(len(re.findall(r"^\s*\[", rows, re.MULTILINE)), 2)
        first, second = rows.split('["branch"', 1)
        self.assertIn('"workspace"', first)
        self.assertNotIn('"$git_summary"', first)
        self.assertIn('"$git_summary"', second)
        self.assertIn('"$pr"', second)

    def test_clean_upstream_has_only_branch(self):
        state = self.parse()
        state.update(ahead=0, behind=0)
        self.assertEqual(g.render(state), "main")
        self.assertEqual(g.render(state, marks_only=True), "")

    def test_counts_unique_records_not_status_categories(self):
        state = self.parse(b"1 MM N... 100644 100644 100644 a b both\0? new\0u UU N... 100644 100644 100644 100644 a b c conflict\0")
        self.assertEqual(g.render(state), "main * ↑2 ↓1 !")

    def test_suffix_is_one_token_with_warning_last_in_all_formats(self):
        state = self.parse(b"? new\0")
        state["conflicts"] = 1
        self.assertEqual(g.render(state, marks_only=True), "* ↑2 ↓1 !")
        for fmt in ("ansi", "zsh", "tmux"):
            with self.subTest(fmt=fmt):
                output = g.render(state, fmt, marks_only=True)
                output = re.sub(r"\x1b\[[0-9;]*m|%F\{[^}]+\}|%f|#\[[^]]+\]", "", output)
                self.assertEqual(output, "* ↑2 ↓1 !")
        self.assertEqual(g.render({"error": True}, marks_only=True), "!")

    def test_paused_operation_without_file_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            subprocess.run(["git", "init", "-b", "main", temp], check=True, capture_output=True)
            admin = Path(temp) / ".git"
            for marker in ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD",
                           "rebase-merge", "rebase-apply"):
                with self.subTest(marker=marker):
                    path = admin / marker
                    if marker.startswith("rebase-"):
                        path.mkdir()
                    else:
                        path.write_text("a" * 40 + "\n")
                    self.assertEqual(g.render(g.collect(temp)), "main !")
                    if path.is_dir():
                        path.rmdir()
                    else:
                        path.unlink()
            self.assertEqual(g.render(g.collect(temp)), "main")

    def test_rename_and_newline_filenames(self):
        state = self.parse(b"2 R. N... 100644 100644 100644 a b R100 new\nname\0u not-a-conflict\0? new\nfile\0")
        self.assertEqual(state["changed"], 2)
        self.assertEqual(state["conflicts"], 0)

    def test_missing_upstream_and_zsh_literal_percent(self):
        state = self.parse(tracking=False)
        state["branch"] = "feature/100%"
        self.assertEqual(g.render(state), "feature/100%")
        self.assertIn("feature/100%%", g.render(state, "zsh"))

    def test_tmux_style_and_hash_escaping(self):
        state = self.parse(b"? new\0")
        state["branch"] = "feature/#[bold]"
        self.assertEqual(g.render(state, "tmux"),
                         "feature/##[bold] #[fg=yellow]*#[fg=default] "
                         "#[fg=green]↑2#[fg=default] #[fg=red]↓1#[fg=default]")

    def test_detached_worktree_identity(self):
        state = g.parse_status(b"# branch.oid abcdef123\0# branch.head (detached)\0")
        state["worktree"] = True
        self.assertEqual(g.render(state), "detached:abcdef1")

    def test_non_utf8_paths_keep_distinct_byte_identity(self):
        state = self.parse(b"? \xff\0? \xfe\0")
        self.assertEqual(state["changed"], 2)
        self.assertEqual(g.render(state), "main * ↑2 ↓1")

    def test_broken_metadata_is_not_a_quiet_nonrepo(self):
        for diagnostic, expected in (
            (b"fatal: not a git repository (or any of the parent directories): .git\n", None),
            (b"fatal: not a git repository (or any parent up to mount point /)\nStopping at filesystem boundary\n", None),
            (b"fatal: not a git repository: /repo/.git/worktrees/broken\n", {"error": True}),
        ):
            result = subprocess.CompletedProcess([], 128, stdout=b"", stderr=diagnostic)
            with self.subTest(diagnostic=diagnostic), patch.object(g.subprocess, "run", return_value=result):
                self.assertEqual(g.collect("/fixture"), expected)

    def test_duplicates_and_invalid_output(self):
        state = self.parse(b"? same\0? same\0")
        self.assertEqual(state["changed"], 1)
        for data in (b"", b"# branch.head main\0", b"# branch.head main\0# branch.oid abcdef1\0garbage\0"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                g.parse_status(data)

    def test_outside_and_error_not_clean(self):
        self.assertEqual(g.render(None), "")
        self.assertEqual(g.render({"error": True}), "!")
        with patch.object(g.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 5)):
            self.assertEqual(g.collect("."), {"error": True})

    def test_real_divergence_is_commit_counts_not_file_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            def git(*args):
                return subprocess.run(["git", "-C", temp, "-c", "core.hooksPath=/dev/null",
                                       "-c", "commit.gpgsign=false", *args], check=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            git("init", "-b", "main")
            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@example.invalid")
            git("commit", "--allow-empty", "-m", "base")
            git("checkout", "-b", "remote-tip")
            git("commit", "--allow-empty", "-m", "remote")
            remote_tip = git("rev-parse", "HEAD").stdout.decode().strip()
            git("checkout", "main")
            git("commit", "--allow-empty", "-m", "local")
            git("config", "remote.origin.url", "https://example.invalid/fixture.git")
            git("config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
            git("update-ref", "refs/remotes/origin/main", remote_tip)
            git("branch", "--set-upstream-to=origin/main", "main")
            git("config", "status.aheadBehind", "false")
            self.assertEqual(g.render(g.collect(temp)), "main ↑1 ↓1")
            git("update-ref", "-d", "refs/remotes/origin/main")
            self.assertEqual(g.render(g.collect(temp)), "main")
            self.assertFalse((Path(temp) / ".git/index.lock").exists())

    def test_claude_summary_and_session_totals_are_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            repo, bindir, cache = (temp / name for name in ("repo", "bin", "cache"))
            for directory in (repo, bindir, cache):
                directory.mkdir()
            shutil.copyfile(SOURCE, bindir / "git-status-line")
            (bindir / "git-status-line").chmod(0o755)
            (cache / "oauth-usage.json").write_text("{}")  # Never trigger live OAuth/network.
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
            (repo / "new").write_text("new")
            payload = {"cwd": str(repo), "model": {"display_name": "Fixture"},
                       "cost": {"total_lines_added": 3}, "context_window": {"used_percentage": 20}}
            env = dict(os.environ, PATH=str(bindir) + ":" + os.environ["PATH"],
                       CLAUDE_STATUSLINE_CACHE_DIR=str(cache))
            for width in (200, 120, 80, 40):
                env["CLAUDE_STATUSLINE_COLS"] = str(width)
                result = subprocess.run(["bash", str(SOURCE.parents[2] / "dot_claude/statusline-command.sh")],
                                        input=json.dumps(payload), text=True, capture_output=True,
                                        env=env, check=True, timeout=10)
                plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
                self.assertNotIn("●", plain)
                if width == 200:
                    self.assertIn("main *", plain)
                    self.assertNotIn("changed", plain)
                    self.assertNotIn("no upstream", plain)
                    self.assertIn("session +3", plain)

    def test_real_unborn_staged_modified_untracked_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            def git(*args):
                return subprocess.run(["git", "-C", temp, *args], check=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            git("init", "-b", "main")
            self.assertEqual(g.render(g.collect(temp)), "main")
            path = Path(temp)
            (path / "file").write_text("one\n")
            git("add", "file")
            (path / "file").write_text("two\n")
            (path / "new\nfile").write_text("new")
            (path / ".git/info/exclude").write_text("ignored\n")
            (path / "ignored").write_text("ignore")
            self.assertEqual(g.render(g.collect(temp)), "main *")
            self.assertFalse((path / ".git/index.lock").exists())
            output = subprocess.run(["python3", str(SOURCE), "-f", "plain", temp],
                                    capture_output=True, text=True, check=True)
            self.assertEqual(output.stdout.strip(), "main *")


if __name__ == "__main__":
    unittest.main()
