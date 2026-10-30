"""Retirement integration tests: real Git repositories, temporary homes only."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from lib import retire_project_policy as retirement


class Retirement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="retire-policy-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.repo = self.home / "Projects/arbitrary-repository"
        self.repo.mkdir(parents=True)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.excludesFile", os.devnull)
        self.old = self.repo / ".agents/tool-gate.json"
        self.local = self.repo / ".claude/settings.local.json"
        self.policy = self.repo / ".pi/tool-gate.json"
        self.legacy = self.home / ".pi/agent/tool-gate/project-grants.json"
        self.policy_value = {"directories": {"read": ["~/Projects/neighbor"], "write": ["~/Documents"]},
                             "permissions": {"allow": ["Bash(npm test:*)", "web_fetch", "Edit(src/**)"],
                                             "ask": ["Bash(git push:*)"]}}

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True).stdout

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value) + "\n")

    def commit(self, *paths):
        self.git("add", "--", *paths)
        self.git("commit", "--allow-empty", "-qm", "fixture")

    def ready(self):
        self.put(self.policy, self.policy_value)
        self.commit(".pi/tool-gate.json")
        self.put(self.old, {"directories": {"read": [str(self.home / "Projects/neighbor")]}})

    def run_retire(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            retirement.retire(self.home)
        return out.getvalue(), err.getvalue()

    def test_generated_subset_removed_and_idempotent_with_no_git_mutations(self):
        self.ready()
        index = self.git("ls-files", "--stage")
        shared = self.policy.read_bytes()
        self.assertIn("generated project policy", self.run_retire()[0])
        self.assertFalse(self.old.exists())
        self.assertEqual(self.run_retire(), ("", ""))
        self.assertEqual(index, self.git("ls-files", "--stage"))
        self.assertEqual(shared, self.policy.read_bytes())

    def test_missing_untracked_staged_dirty_and_staged_only_replacements_retained(self):
        self.ready()
        original = self.policy.read_text()
        for kind in ("missing", "dirty", "staged", "untracked", "local-only"):
            with self.subTest(kind=kind):
                self.git("reset", "-q", "HEAD")
                self.put(self.policy, original)
                if kind == "missing":
                    self.policy.unlink()
                elif kind in ("dirty", "staged"):
                    self.put(self.policy, original + "\n")
                    if kind == "staged":
                        self.git("add", ".pi/tool-gate.json")
                else:
                    self.git("rm", "--cached", "-q", ".pi/tool-gate.json")
                    if kind == "local-only":
                        self.policy.rename(self.policy.with_name("tool-gate.local.json"))
                self.run_retire()
                self.assertTrue(self.old.exists())
        # An index entry without a committed HEAD is not a replacement either.
        self.git("reset", "-q", "HEAD")
        self.put(self.policy, original)
        self.git("checkout", "--orphan", "unborn")
        self.run_retire()
        self.assertTrue(self.old.exists())

    def test_non_directory_keys_or_unmatched_directory_preserve_entire_old_file(self):
        self.ready()
        for value in ({"directories": {"read": ["~/Projects/not-granted"]}},
                      {"directories": {"write": ["~/Projects/neighbor"]}},
                      {"directories": {"read": ["~/Projects/neighbor"], "enabled": True}},
                      {"directories": {"read": []}, "permissions": {"allow": []}},
                      {"directories": {}, "unknown": True}):
            with self.subTest(value=value):
                self.put(self.old, value)
                before = self.old.read_bytes()
                self.assertEqual(self.run_retire(), ("", ""))
                self.assertEqual(self.old.read_bytes(), before)

    def test_tracked_candidates_in_index_or_head_are_never_modified(self):
        self.ready()
        self.put(self.local, {"permissions": {"additionalDirectories": ["~/Documents"]}})
        self.put(self.repo / ".claude/settings.json", {"permissions": {"additionalDirectories": ["~/Documents"]}})
        self.commit(".agents/tool-gate.json", ".claude/settings.local.json", ".claude/settings.json")
        for staged_delete in (False, True):
            if staged_delete:
                self.git("rm", "--cached", "-q", ".agents/tool-gate.json", ".claude/settings.local.json")
            before = (self.old.read_bytes(), self.local.read_bytes())
            self.run_retire()
            self.assertEqual(before, (self.old.read_bytes(), self.local.read_bytes()))

    def test_claude_equivalence_comments_unknown_keys_and_approvals_preserved(self):
        self.ready()
        shared = {"permissions": {"additionalDirectories": ["~/Documents"],
                                  "allow": ["Read(~/Projects/neighbor/**)"]},
                  "sandbox": {"filesystem": {"allowWrite": ["~/Documents"]}}}
        self.put(self.repo / ".claude/settings.json", shared)
        self.commit(".claude/settings.json")
        read = "Read(/" + str(self.home / "Projects/neighbor") + "/**)"
        text = '''{
  // retain top comment
  "permissions": {
    "additionalDirectories": [/* before */ %s /* after */, "~/other",],
    "allow": ["Bash(custom command)", %s, // approval comment
      "Read(~/private/file)"],
    "deny": ["Bash(rm:*)"]
  },
  "sandbox": {"filesystem": {"allowWrite": [%s /* write comment */]}},
  "unknown": {"keep": true}
}
''' % (json.dumps(str(self.home / "Documents")), json.dumps(read), json.dumps(str(self.home / "Documents")))
        self.put(self.local, text)
        self.local.chmod(0o600)
        self.run_retire()
        after = self.local.read_text()
        data = retirement.parse(after).value
        self.assertEqual(data["permissions"]["additionalDirectories"], ["~/other"])
        self.assertEqual(data["permissions"]["allow"], ["Bash(custom command)", "Read(~/private/file)"])
        self.assertEqual(data["sandbox"]["filesystem"]["allowWrite"], [])
        self.assertEqual(data["unknown"], {"keep": True})
        for comment in ("// retain top comment", "/* before */", "/* after */", "// approval comment", "/* write comment */"):
            self.assertIn(comment, after)
        self.assertIn('"deny": ["Bash(rm:*)"]', after)
        self.assertEqual(self.local.stat().st_mode & 0o777, 0o600)
        before = self.local.stat()
        self.assertEqual(self.run_retire(), ("", ""))
        self.assertEqual(self.local.stat().st_mtime_ns, before.st_mtime_ns)

    def test_uncommitted_or_dirty_shared_claude_does_not_qualify(self):
        self.ready()
        shared = self.repo / ".claude/settings.json"
        value = {"permissions": {"additionalDirectories": ["~/Documents"]}}
        self.put(shared, value)
        self.put(self.local, value)
        before = self.local.read_bytes()
        self.run_retire()
        self.assertEqual(before, self.local.read_bytes())
        self.commit(".claude/settings.json")
        shared.write_text(shared.read_text() + "\n")
        self.run_retire()
        self.assertEqual(before, self.local.read_bytes())

    def test_legacy_format_matching_and_unmatched_metadata_preserved(self):
        self.ready()
        matching = ["dir:read:" + str(self.home / "Projects/neighbor"), "dir:write:~/Documents",
                    "allow:web_fetch", "tool:web_fetch", "bash:npm test", "ask:Bash(git push:*)", "edit:src"]
        unmatched = ["dir:write:~/Projects/neighbor", "dir:read:~/unmatched", "deny:web_fetch",
                     "bash:unparsed shell: npm test", "unknown", "write:src"]
        entries = [{"key": key, "label": "original", "added": "date", "custom": 1} for key in matching + unmatched]
        other = str(self.home / "Projects/absent-on-this-machine")
        self.put(self.legacy, {str(self.repo): entries, other: entries})
        self.run_retire()
        actual = json.loads(self.legacy.read_text())
        self.assertEqual(actual[str(self.repo)], entries[len(matching):])
        self.assertEqual(actual[other], entries)
        self.assertEqual(self.run_retire(), ("", ""))

    def test_untracked_bio_local_and_archived_missing_replacements_keep_legacy(self):
        self.ready()
        bio = self.home / "Projects/bio-discovery"
        bio.mkdir()
        self.put(bio / ".pi/tool-gate.local.json", self.policy_value)
        absent = str(self.home / "Projects/archived-focus")
        entries = [{"key": "dir:read:~/Projects/neighbor", "label": "keep", "added": "date"}]
        self.put(self.legacy, {str(bio): entries, absent: entries})
        before = self.legacy.read_bytes()
        self.run_retire()
        self.assertEqual(self.legacy.read_bytes(), before)

    def test_malformed_files_warn_without_overwriting(self):
        for target in ("policy", "old", "local", "legacy"):
            with self.subTest(target=target):
                self.ready()
                shared = self.repo / ".claude/settings.json"
                self.put(shared, {})
                self.commit(".claude/settings.json") if not self.git("ls-files", ".claude/settings.json") else None
                path = getattr(self, target)
                self.put(path, '{"broken": [')
                if target == "policy":
                    self.commit(".pi/tool-gate.json")
                before = path.read_bytes()
                _, warning = self.run_retire()
                self.assertIn("retained", warning)
                self.assertEqual(path.read_bytes(), before)
                # Reset malformed files before next subtest.
                path.unlink()

    def test_pi_comments_and_trailing_commas_are_malformed(self):
        self.ready()
        for text in ('{// comment\n"directories":{}}', '{"directories":{},}'):
            with self.subTest(text=text):
                self.put(self.policy, text)
                self.commit(".pi/tool-gate.json")
                self.assertIn("retained", self.run_retire()[1])
                self.assertTrue(self.old.exists())
        self.put(self.policy, self.policy_value)
        self.commit(".pi/tool-gate.json")
        for target in (self.old, self.legacy):
            for text in ('{// comment\n"directories":{}}', '{"directories":{},}'):
                self.put(target, text)
                self.assertIn("retained", self.run_retire()[1])
                self.assertEqual(target.read_text(), text)
            if target == self.old:
                target.unlink()

    def test_malformed_shapes_and_duplicate_keys_are_not_rewritten(self):
        self.ready()
        for bad in ('{"directories": []}', '{"directories":{"read":[null]}}',
                    '{"permissions": []}', '{"directories":{},"directories":{}}'):
            self.put(self.policy, bad)
            self.commit(".pi/tool-gate.json")
            self.assertIn("retained", self.run_retire()[1])
            self.assertTrue(self.old.exists())
        self.put(self.policy, self.policy_value)
        self.commit(".pi/tool-gate.json")
        for bad in ({str(self.repo): [None]}, {str(self.repo): [{"key": 1}]}, {str(self.repo): {}}):
            self.put(self.legacy, bad)
            before = self.legacy.read_bytes()
            self.assertIn("retained", self.run_retire()[1])
            self.assertEqual(self.legacy.read_bytes(), before)

    def test_symlinks_and_hardlinks_never_followed(self):
        self.ready()
        target = self.home / "external-policy"
        self.old.rename(target)
        for link in (self.old.symlink_to, lambda p: os.link(p, self.old)):
            link(target)
            self.assertIn("retained", self.run_retire()[1])
            self.assertTrue(self.old.exists())
            self.assertTrue(target.exists())
            self.old.unlink()
        self.old.parent.rmdir()
        self.old.parent.symlink_to(target.parent, target_is_directory=True)
        self.put(target.parent / "tool-gate.json", {"directories": {}})
        self.assertIn("retained", self.run_retire()[1])

    def test_codex_and_opencode_untouched_and_nested_checkouts_not_discovered(self):
        self.ready()
        paths = [self.repo / ".codex/config.toml", self.repo / ".opencode/opencode.jsonc",
                 self.repo / ".worktrees/branch/.agents/tool-gate.json"]
        for path in paths:
            self.put(path, "unrelated bytes // comments\n")
        self.run_retire()
        for path in paths:
            self.assertEqual(path.read_text(), "unrelated bytes // comments\n")

    def test_users_and_linux_home_semantics_in_temporary_fixtures(self):
        for prefix in ("/Users/test", "/home/test"):
            with self.subTest(home=prefix):
                # Physical fixtures stay in temp; policy values use actual host-style homes.
                logical_home = Path(prefix)
                local = '{"permissions":{"allow":[%s]}}' % json.dumps(f"Read(/{prefix}/Projects/neighbor/**)")
                shared = retirement.parse('{"permissions":{"allow":["Read(~/Projects/neighbor/**)"]}}')
                result = retirement.duplicate_claude(local, shared, logical_home)
                self.assertEqual(retirement.parse(result).value["permissions"]["allow"], [])
                policy = retirement.parse(json.dumps(self.policy_value))
                self.assertTrue(retirement.covered("dir:read:" + prefix + "/Projects/neighbor", policy, logical_home))
                self.assertFalse(retirement.covered("dir:read:/other/Projects/neighbor", policy, logical_home))

    def test_cli_optional_home_and_default_home(self):
        self.ready()
        script = Path(retirement.__file__)
        result = subprocess.run([sys.executable, "-B", str(script), "--home", str(self.home)],
                                capture_output=True, text=True, check=True)
        self.assertIn("generated project policy", result.stdout)
        with patch.object(retirement.Path, "home", return_value=self.home), patch("sys.argv", [str(script)]):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                retirement.main()
            self.assertEqual(out.getvalue(), "")

    def test_absent_projects_and_legacy_are_quiet(self):
        self.assertEqual(self.run_retire(), ("", ""))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            retirement.retire(self.home / "missing")
        self.assertEqual(out.getvalue(), "")

    def test_tracked_legacy_file_is_not_modified(self):
        self.ready()
        self.put(self.legacy, {str(self.repo): [{"key": "tool:web_fetch", "extra": "keep"}]})
        subprocess.run(["git", "-C", str(self.home), "init", "-q"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.home), "add", "--", ".pi/agent/tool-gate/project-grants.json"],
                       check=True, capture_output=True)
        before = self.legacy.read_bytes()
        self.run_retire()
        self.assertEqual(self.legacy.read_bytes(), before)

    def test_legacy_removal_preserves_unknown_fields_and_empty_entries(self):
        self.ready()
        text = '{"%s": [{"key":"tool:web_fetch"}, {"key":"unknown","custom":{"x":1}}], "unmatched": []}' % self.repo
        self.put(self.legacy, text)
        self.run_retire()
        self.assertIn('{"key":"unknown","custom":{"x":1}}', self.legacy.read_text())
        self.assertIn('"unmatched": []', self.legacy.read_text())
        self.assertEqual(self.run_retire(), ("", ""))

    def test_array_edits_preserve_all_comments_for_multiple_positions(self):
        for removed in ({0}, {1}, {2}, {0, 2}, {0, 1}, {1, 2}, {0, 1, 2}):
            text = '{"list":[/*a*/ "one", /*b*/ "two", /*c*/ "three", /*d*/]}'
            node = retirement.at(retirement.parse(text), "list")
            after = retirement.remove_values(text, [(node, removed)])
            self.assertEqual(retirement.parse(after).value["list"], [x for i, x in enumerate(node.value) if i not in removed])
            for comment in ("/*a*/", "/*b*/", "/*c*/", "/*d*/"):
                self.assertIn(comment, after)


if __name__ == "__main__":
    unittest.main()
