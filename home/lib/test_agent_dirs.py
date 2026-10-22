"""Tests for the per-project directory grants (lib/agent_dirs.py) on a fixture home.
No live settings or checkouts are read or modified."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "lib"))
import agent_dirs as d  # noqa: E402


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        for rel in ("dotfiles", "Projects/app", "Projects/herdr-a", "Projects/herdr-b", "Projects/blog", "Documents", ".cache"):
            os.makedirs(os.path.join(self.home, rel))
        self.data = {
            "hosts": ["mac-pro"],
            "private": ["~/Projects", "~/dotfiles", "~/Documents", "~/Missing"],
            "alwaysWrite": ["/tmp", "$TMPDIR", "~/.cache"],
            "projects": {
                "dotfiles": {"root": "~/dotfiles", "read": ["*"], "write": ["~/Projects/herdr-*"]},
                "app": {"root": "~/Projects/app", "read": ["~/Documents"], "write": ["~/dotfiles"]},
                "blog": {"root": "~/Projects/blog", "read": ["*"], "write": []},
            },
        }

    def tearDown(self):
        self.tmp.cleanup()

    def p(self, rel):
        return os.path.join(self.home, rel)


class Grants(Fixture):
    def test_globs_expand_to_existing_directories_and_missing_paths_drop(self):
        g = d.grants("dotfiles", self.data, self.home)
        self.assertEqual(g, {"root": self.p("dotfiles"), "anywhere": True, "read": [],
                             "write": [self.p("Projects/herdr-a"), self.p("Projects/herdr-b")]})
        self.assertEqual(d.expand("~/Missing", self.home), [])

    def test_hosts(self):
        self.assertTrue(d.enabled_here(self.data, "mac-pro"))
        self.assertFalse(d.enabled_here(self.data, "nuc"))


class Claude(Fixture):
    def test_grants_are_added_and_claudes_own_entries_stay(self):
        live = json.dumps({"permissions": {"allow": ["Bash(npm test:*)"]}, "outputStyle": "default"}, indent=2) + "\n"
        out = json.loads(d.claude_local(live, "app", self.data, self.home))
        self.assertEqual(out["permissions"]["additionalDirectories"], [self.p("dotfiles")])
        self.assertEqual(out["permissions"]["allow"][0], "Bash(npm test:*)")
        self.assertIn("Read(/%s/**)" % self.p("Documents"), out["permissions"]["allow"])
        self.assertIn("Read(/%s/**)" % self.p("dotfiles"), out["permissions"]["allow"])
        self.assertFalse([r for r in out["permissions"]["allow"] if r.startswith(("Grep(", "Glob("))])
        self.assertEqual(out["sandbox"]["filesystem"]["allowWrite"], [self.p("dotfiles")])
        self.assertEqual(out["outputStyle"], "default")

    def test_anywhere_and_idempotent(self):
        first = d.claude_local("", "blog", self.data, self.home)
        self.assertEqual(json.loads(first), {"permissions": {"allow": ["Read(//**)"]}})
        # Grep and Glob rules from before are dropped; Claude only matches Read rules.
        old = json.dumps({"permissions": {"allow": ["Bash(ls)", "Read(//**)", "Grep(//**)", "Glob(//**)"]}}, indent=2) + "\n"
        self.assertEqual(json.loads(d.claude_local(old, "blog", self.data, self.home))["permissions"]["allow"], ["Bash(ls)", "Read(//**)"])
        self.assertEqual(d.claude_local(first, "blog", self.data, self.home), first)

    def test_global_sandbox_only_on_policy_hosts(self):
        settings = {"theme": "dark"}
        self.assertEqual(d.claude_global(settings, self.data, "nuc"), settings)
        out = d.claude_global(settings, self.data, "mac-pro")
        self.assertTrue(out["sandbox"]["enabled"])
        self.assertEqual(out["sandbox"]["filesystem"]["allowWrite"], ["~/.cache"])


class Codex(Fixture):
    LIVE = (
        'approval_policy = "on-request"\nsandbox_mode = "workspace-write"\nmodel = "m"\n\n'
        '[sandbox_workspace_write]\nnetwork_access = true\nwritable_roots = [ "~/.cache" ]\n\n'
        '[projects."/x"]\ntrust_level = "trusted"\n'
    )

    def test_global_profile_replaces_sandbox_mode_and_is_stable(self):
        out = d.codex_global(self.LIVE, self.data, self.home, "mac-pro")
        self.assertTrue(out.startswith('default_permissions = "self"\n\napproval_policy'))
        self.assertNotIn("sandbox_mode", out)
        self.assertNotIn("[sandbox_workspace_write]", out)
        self.assertIn('[projects."/x"]\ntrust_level = "trusted"\n\n[permissions.self]\n', out)
        self.assertIn('"%s" = "deny"' % self.p("Projects"), out)
        self.assertNotIn("Missing", out)
        self.assertIn('"%s" = "write"' % self.p(".cache"), out)
        self.assertIn("[permissions.self.network]\nenabled = true\n", out)
        self.assertEqual(d.codex_global(out, self.data, self.home, "mac-pro"), out)
        # A table Codex appends later stays after ours; ours are replaced in place.
        later = out + '\n[projects."/y"]\ntrust_level = "trusted"\n'
        self.assertEqual(d.codex_global(later, self.data, self.home, "mac-pro"), later)

    def test_global_keeps_the_next_tables_marker_comment(self):
        out = d.codex_global(self.LIVE, self.data, self.home, "mac-pro")
        marked = out + '\n# >>> Sphinx managed MCP server\n[mcp_servers.sphinx]\ncommand = "node"\n# <<< Sphinx managed MCP server\n'
        self.assertEqual(d.codex_global(marked, self.data, self.home, "mac-pro"), marked)

    def test_global_untouched_elsewhere(self):
        self.assertEqual(d.codex_global(self.LIVE, self.data, self.home, "nuc"), self.LIVE)

    def test_project_profile_keeps_other_tables(self):
        live = "[mcp_servers.vercel]\nenabled = true\n"
        out = d.codex_project(live, "app", self.data, self.home)
        self.assertEqual(out, (
            'default_permissions = "project"\n\n[mcp_servers.vercel]\nenabled = true\n\n'
            '[permissions.project]\nextends = "self"\n\n'
            '[permissions.project.workspace_roots]\n"%s" = true\n\n'
            '[permissions.project.filesystem]\n"%s" = "write"\n"%s" = "read"\n' % (self.p("dotfiles"), self.p("dotfiles"), self.p("Documents"))))
        self.assertEqual(d.codex_project(out, "app", self.data, self.home), out)

    def test_anywhere_reopens_private_roots_but_not_the_checkout_itself(self):
        out = d.codex_project("", "dotfiles", self.data, self.home)
        self.assertIn('"%s" = "read"' % self.p("Projects"), out)
        self.assertNotIn('"%s" = "read"' % self.p("dotfiles"), out)
        self.assertIn('"%s" = true' % self.p("Projects/herdr-a"), out)


class Opencode(Fixture):
    def test_read_grants_stay_read_only(self):
        live = json.dumps({"mcp": {"vercel": {"enabled": True}}}, indent=2) + "\n"
        out = d.opencode_project(live, "app", self.data, self.home)
        data = json.loads(out)
        self.assertEqual(data["mcp"], {"vercel": {"enabled": True}})
        self.assertEqual(data["permission"]["external_directory"], {"~/Documents/**": "allow", "~/dotfiles/**": "allow"})
        self.assertEqual(data["permission"]["edit"]["~/Documents/**"], "ask")
        self.assertEqual(data["permission"]["edit"]["~/dotfiles/**"], "allow")
        self.assertEqual(data["permission"]["edit"]["~/Projects/app/**"], "allow")
        # The format the project-MCP script writes, so it finds nothing to change.
        self.assertEqual(out, json.dumps(data, indent=2) + "\n")
        self.assertEqual(d.opencode_project(out, "app", self.data, self.home), out)


class DropRoot(Fixture):
    def test_removes_only_the_old_roots_entries(self):
        old = os.path.join(self.home, "dotfiles")
        new = self.p("Projects/dotfiles")
        os.makedirs(os.path.join(self.home, ".codex"))
        codex = os.path.join(self.home, ".codex/config.toml")
        Path(codex).write_text('[projects."%s"]\ntrust_level = "trusted"\n\n[projects."%s"]\ntrust_level = "trusted"\n' % (old, new))
        claude = Path(self.home, "Projects/app/.claude/settings.local.json")
        claude.parent.mkdir()
        claude.write_text(json.dumps({"permissions": {"additionalDirectories": [old, new],
                                                      "allow": ["Read(/%s/**)" % old, "Bash(ls)"]},
                                      "sandbox": {"filesystem": {"allowWrite": [old]}}}))
        opencode = Path(self.home, "Projects/app/.opencode/opencode.jsonc")
        opencode.parent.mkdir()
        opencode.write_text(json.dumps({"permission": {"external_directory": {"~/dotfiles/**": "allow", "~/Documents/**": "allow"},
                                                       "edit": {"*": "allow", "~/dotfiles/**": "allow"}}}))
        self.assertEqual(len(d.drop_root(old, self.home)), 3)
        self.assertEqual(Path(codex).read_text(), '[projects."%s"]\ntrust_level = "trusted"\n' % new)
        self.assertEqual(json.loads(claude.read_text()), {"permissions": {"additionalDirectories": [new], "allow": ["Bash(ls)"]}})
        self.assertEqual(json.loads(opencode.read_text()), {"permission": {"external_directory": {"~/Documents/**": "allow"},
                                                                            "edit": {"*": "allow"}}})
        self.assertEqual(d.drop_root(old, self.home), [])


class Templates(unittest.TestCase):
    def test_every_project_has_its_modify_scripts(self):
        data = json.loads((ROOT / ".chezmoidata/agent_dirs.json").read_text())["agentDirs"]
        for name, spec in data["projects"].items():
            base = ROOT / spec["root"].replace("~/", "", 1)
            for rel, kind in (("dot_claude/modify_settings.local.json", "claude"), ("dot_codex/modify_config.toml", "codex"),
                              ("dot_opencode/modify_opencode.jsonc", "opencode")):
                self.assertIn('agent_dirs.run("%s", "%s")' % (kind, name), (base / rel).read_text(), base / rel)
            self.assertIn('"name" "%s"' % name, (base / "dot_agents/tool-gate.json.tmpl").read_text())


if __name__ == "__main__":
    unittest.main()
