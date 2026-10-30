"""Tests for generic directory defaults and moved-root cleanup on a fixture home.
No live settings or checkouts are read or modified."""
import json
import os
import io
import runpy
import shutil
import subprocess
import tomllib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "lib"))
import agent_dirs as d  # noqa: E402


class TomlParser(unittest.TestCase):
    @staticmethod
    def missing(name):
        return ModuleNotFoundError("No module named " + name, name=name)

    def test_import_and_non_codex_operations_do_not_load_a_parser(self):
        with mock.patch.object(d.importlib, "import_module", side_effect=AssertionError("eager parser")):
            module = runpy.run_path(str(ROOT / "lib/agent_dirs.py"))
            self.assertEqual(module["claude_global"]({}, {"hosts": []}, "nuc"), {})

    def test_prefers_tomllib(self):
        with mock.patch.object(d.importlib, "import_module", return_value=tomllib) as load:
            self.assertIs(d._toml_parser(), tomllib)
        load.assert_called_once_with("tomllib")

    def test_real_tomli_fallback_is_used_for_codex(self):
        # Exercise the parser interface, not a JSON/regex substitute for TOML.
        with mock.patch.object(d.importlib, "import_module",
                               side_effect=[self.missing("tomllib"), tomllib]) as load:
            out = d.codex_global('model = "local"\n', {"hosts": []}, host="nuc")
        self.assertEqual([call.args[0] for call in load.call_args_list], ["tomllib", "tomli"])
        self.assertEqual(tomllib.loads(out)["model"], "local")

    def test_no_parser_fails_without_output(self):
        output = io.StringIO()
        with mock.patch.object(sys, "stdout", output), \
                mock.patch.object(d.importlib, "import_module",
                                  side_effect=[self.missing("tomllib"), self.missing("tomli")]):
            with self.assertRaisesRegex(RuntimeError, "requires tomllib.*or tomli.*refusing rewrite"):
                d.codex_global("", {"hosts": []}, host="nuc")
        self.assertEqual(output.getvalue(), "")

    def test_broken_parser_dependency_is_not_treated_as_absent(self):
        with mock.patch.object(d.importlib, "import_module", side_effect=self.missing("dependency")) as load:
            with self.assertRaises(ModuleNotFoundError):
                d._toml_parser()
        load.assert_called_once_with("tomllib")


class CodexBootstrap(unittest.TestCase):
    GUARD = "_DOTFILES_CODEX_PYTHON_REEXEC"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        lib = self.root / "lib"
        lib.mkdir()
        # Any project import before a successful bootstrap fails the test.
        (lib / "agent_dirs.py").write_text(
            'import importlib, os, sys\n'
            'importlib.import_module("tomllib" if os.environ.get("' + self.GUARD + '") else os.environ["TEST_PARSER"])\n'
            'def codex_global(text):\n'
            '    assert sys.argv[1:] == ["extra", "two words"]\n'
            '    assert os.environ["TEST_PRESERVED"] == "yes"\n'
            '    return text\n')
        (lib / "agent_settings.py").write_text(
            'def project_servers(): return {}\n'
            'def mcp_servers(): return {}\n'
            'def merge_codex_toml(text, servers): return text\n'
            'def trust_codex_projects(text, repos): return text\n')
        # Simulate 3.9's missing parsers in the initial interpreter only.
        (self.root / "sitecustomize.py").write_text(
            'import importlib.abc, os, sys, types\n'
            'class Parsers(importlib.abc.MetaPathFinder):\n'
            '    def find_spec(self, fullname, path=None, target=None):\n'
            '        if fullname not in ("tomllib", "tomli"): return\n'
            '        if os.environ.get("' + self.GUARD + '") and not os.environ.get("TEST_LOOP"): return\n'
            '        if fullname == os.environ.get("TEST_PARSER"): return\n'
            '        raise ModuleNotFoundError("missing " + fullname, name=fullname)\n'
            'sys.meta_path.insert(0, Parsers())\n'
            '# A distinct installed tomli stand-in for the no-reexec branch.\n'
            'if os.environ.get("TEST_PARSER") == "tomli": sys.modules["tomli"] = types.ModuleType("tomli")\n')
        uv = self.root / "uv"
        uv.write_text('#!' + sys.executable + '\n'
                      'import json, os, sys\n'
                      'with open(os.environ["TEST_UV_LOG"], "w") as f:\n'
                      '    json.dump([sys.argv[1:], sys.stdin.read()], f)\n'
                      'if os.environ.get("TEST_UV_FAIL"): sys.exit(1)\n'
                      'print(os.environ.get("TEST_UV_RESULT", sys.executable))\n')
        uv.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root), PYTHONPATH=str(self.root),
                        CHEZMOI_SOURCE_DIR=str(self.root), TEST_PARSER="none",
                        TEST_PRESERVED="yes", TEST_UV_LOG=str(self.root / "uv.json"))
        self.env.pop(self.GUARD, None)

    def run_script(self, **env):
        return subprocess.run(
            [sys.executable, "-B", str(ROOT / "private_dot_codex/modify_private_config.toml"),
             "extra", "two words"], input='model = "preserved"\n# untouched stdin\n',
            capture_output=True, text=True, env=dict(self.env, **env))

    def test_available_parsers_keep_interpreter(self):
        for parser in ("tomllib", "tomli"):
            with self.subTest(parser=parser):
                result = self.run_script(TEST_PARSER=parser)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, 'model = "preserved"\n# untouched stdin\n')
                self.assertFalse((self.root / "uv.json").exists())

    def test_reexec_preserves_stdin_args_and_environment(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'model = "preserved"\n# untouched stdin\n')
        self.assertEqual(json.loads((self.root / "uv.json").read_text()), [
            ["python", "find", "--no-python-downloads", "--managed-python", ">=3.11"], ""])

    def test_discovery_and_exec_failures_emit_no_output(self):
        for env in ({"TEST_UV_FAIL": "1"}, {"TEST_UV_RESULT": ""},
                    {"TEST_UV_RESULT": "/nonexistent/python"},
                    {"TEST_UV_RESULT": "one\ntwo"}, {"PATH": ""}):
            with self.subTest(env=env):
                result = self.run_script(**env)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("refusing rewrite", result.stderr)

    def test_reexec_without_tomllib_fails_instead_of_looping(self):
        result = self.run_script(TEST_LOOP="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("re-executed Python lacks tomllib", result.stderr)
        # A preexisting guard also prevents discovery, even if tomli is available.
        (self.root / "uv.json").unlink()
        result = self.run_script(**{self.GUARD: "1", "TEST_LOOP": "1", "TEST_PARSER": "tomli"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertFalse((self.root / "uv.json").exists())


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
        }

    def tearDown(self):
        self.tmp.cleanup()

    def p(self, rel):
        return os.path.join(self.home, rel)


class Defaults(Fixture):
    def test_globs_expand_to_existing_directories_and_missing_paths_drop(self):
        self.assertEqual(d.expand("~/Projects/herdr-*", self.home),
                         [self.p("Projects/herdr-a"), self.p("Projects/herdr-b")])
        self.assertEqual(d.expand("~/Missing", self.home), [])

    def test_hosts(self):
        self.assertTrue(d.enabled_here(self.data, "mac-pro"))
        self.assertFalse(d.enabled_here(self.data, "nuc"))

    def test_global_sandbox_only_on_policy_hosts(self):
        settings = {"theme": "dark", "sandbox": {"custom": True}}
        for host in ("mac-air", "nuc", "agentbox-box"):
            self.assertEqual(d.claude_global(settings, self.data, host), settings)
        out = d.claude_global(settings, self.data, "mac-pro")
        self.assertTrue(out["sandbox"]["enabled"])
        self.assertTrue(out["sandbox"]["custom"])
        self.assertEqual(out["sandbox"]["filesystem"]["allowWrite"], ["~/.cache"])
        self.assertEqual(d.claude_global(out, self.data, "mac-pro"), out)
        self.assertNotIn("enabled", settings["sandbox"])


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

    def test_global_workspace_profile_elsewhere_preserves_sandbox_and_defaults(self):
        for host in ("mac-air", "nuc", "agentbox-box"):
            for live in ("", self.LIVE, 'default_permissions = "custom"\n' + self.LIVE):
                with self.subTest(host=host, live=live):
                    out = d.codex_global(live, self.data, self.home, host)
                    parsed = tomllib.loads(out)
                    self.assertEqual(parsed["permissions"], {"self": {"extends": ":workspace"}})
                    original = tomllib.loads(live)
                    self.assertEqual({k: v for k, v in parsed.items() if k != "permissions"}, original)
                    self.assertEqual(d.codex_global(out, self.data, self.home, host), out)

    def test_elsewhere_preserves_old_self_without_removing_sandbox_config(self):
        live = self.LIVE + (
            '\n[permissions.self]\nextends = ":workspace"\n'
            '[permissions.self.filesystem]\n"/private" = "deny"\n'
            '[permissions.self.network]\nenabled = true\n')
        out = d.codex_global(live, self.data, self.home, "nuc")
        self.assertEqual(out, live)

    def test_semantic_existing_profiles_are_preserved_elsewhere_and_refused_natively(self):
        for live in (
            'permissions = { self = { extends = ":workspace" } }\n',
            '[permissions]\nself = { extends = ":workspace" }\n',
            '["permissions"."self"]\nextends = ":workspace"\n',
            "['permissions'.'self']\nextends = ':workspace'\n",
            'permissions.self.extends = ":workspace"\n',
        ):
            with self.subTest(live=live):
                self.assertEqual(d.codex_global(live, self.data, self.home, "nuc"), live)
                with self.assertRaisesRegex(ValueError, "refusing rewrite"):
                    d.codex_global(live, self.data, self.home, "mac-pro")

    def test_bad_toml_or_profile_shapes_refuse_rewrite(self):
        for live in ('[permissions.self\n', 'permissions = 1\n',
                     'permissions.self = "no"\n', 'permissions.self = []\n',
                     'permissions.self.extends = 1\n',
                     'permissions.self.filesystem = "invalid"\n'):
            for host in ("nuc", "mac-pro"):
                with self.subTest(live=live, host=host):
                    with self.assertRaisesRegex(ValueError, "refusing rewrite"):
                        d.codex_global(live, self.data, self.home, host)

    def test_absent_profile_quoted_parent_and_dotted_sibling(self):
        for live in ('["permissions"]\nother = { extends = ":workspace" }\n',
                     'permissions.other.extends = ":workspace"\n'):
            out = d.codex_global(live, self.data, self.home, "nuc")
            self.assertTrue(out.startswith(live))
            self.assertEqual(tomllib.loads(out)["permissions"]["self"], {"extends": ":workspace"})
            self.assertEqual(d.codex_global(out, self.data, self.home, "nuc"), out)

    def test_inline_parent_without_self_refuses_invalid_append(self):
        with self.assertRaisesRegex(ValueError, "refusing rewrite"):
            d.codex_global('permissions = { other = {} }\n', self.data, self.home, "nuc")


class DropRoot(Fixture):
    def setUp(self):
        super().setUp()
        repo = self.p("Projects/app")
        subprocess.run(["git", "init", "-q", repo], check=True)
        for key, value in (("core.excludesFile", os.devnull), ("core.hooksPath", os.devnull),
                           ("commit.gpgSign", "false")):
            subprocess.run(["git", "-C", repo, "config", key, value], check=True)

    def native_files(self):
        old = self.p("dotfiles")
        paths = [Path(self.p("Projects/app/.claude/settings.local.json")),
                 Path(self.p("Projects/app/.opencode/opencode.jsonc"))]
        values = [{"permissions": {"additionalDirectories": [old]}},
                  {"permission": {"external_directory": {old + "/**": "allow"}}}]
        for path, value in zip(paths, values):
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(value))
        return paths

    def test_tracked_and_staged_files_are_preserved(self):
        paths = self.native_files()
        repo = self.p("Projects/app")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        before = [p.read_bytes() for p in paths]
        self.assertEqual(d.drop_root(self.p("dotfiles"), self.home), [])
        self.assertEqual([p.read_bytes() for p in paths], before)
        subprocess.run(["git", "-C", repo, "-c", "user.name=Test", "-c",
                        "user.email=test@example.com", "commit", "-qm", "fixture"], check=True)
        self.assertEqual(d.drop_root(self.p("dotfiles"), self.home), [])
        self.assertEqual([p.read_bytes() for p in paths], before)

    def test_failed_ownership_check_warns_and_preserves(self):
        paths = self.native_files()
        before = [p.read_bytes() for p in paths]
        with mock.patch.object(d.subprocess, "run", side_effect=OSError), \
                mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertEqual(d.drop_root(self.p("dotfiles"), self.home), [])
        self.assertIn("ownership check failed", err.getvalue())
        self.assertEqual([p.read_bytes() for p in paths], before)

    def test_non_repository_ownership_check_warns_and_preserves(self):
        paths = self.native_files()
        before = [p.read_bytes() for p in paths]
        shutil.rmtree(self.p("Projects/app/.git"))
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertEqual(d.drop_root(self.p("dotfiles"), self.home), [])
        self.assertIn("ownership check failed", err.getvalue())
        self.assertEqual([p.read_bytes() for p in paths], before)

    def test_symlinks_preserve_target_bytes(self):
        paths = self.native_files()
        before = [p.read_bytes() for p in paths]
        for path in paths:
            target = path.with_suffix(".target")
            path.rename(target)
            path.symlink_to(target)
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(d.drop_root(self.p("dotfiles"), self.home), [])
        self.assertEqual([p.read_bytes() for p in paths], before)

    def test_invalid_inputs_warn_preserve_and_continue(self):
        paths = self.native_files()
        old = self.p("dotfiles")
        for index, malformed in ((0, '{broken'), (1, '// comment\n{broken'),
                                 (0, '["' + old + '"]'),
                                 (0, '{"permissions": null}'),
                                 (0, '{"sandbox": {"filesystem": []}}'),
                                 (0, '{"permissions": {"allow": {}}}'),
                                 (0, '{"permissions": {"allow": [{}]}}'),
                                 (1, '{"permission": []}'),
                                 (1, '{"permission": {"external_directory": []}}')):
            with self.subTest(index=index, malformed=malformed):
                paths = self.native_files()
                paths[index].write_text(malformed)
                before = paths[index].read_bytes()
                with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                    changed = d.drop_root(old, self.home)
                self.assertEqual(changed, [str(paths[1 - index])])
                self.assertEqual(paths[index].read_bytes(), before)
                self.assertIn("invalid input", err.getvalue())

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
    @unittest.skipUnless(shutil.which("chezmoi"), "chezmoi is not installed")
    def test_generic_pi_defaults_render_on_every_host(self):
        policy = json.loads((ROOT / ".chezmoidata/agent_dirs.json").read_text())["agentDirs"]
        self.assertNotIn("projects", policy)
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp, "chezmoi.toml")
            for host in ("mac-pro", "mac-air", "nuc", "agentbox-box"):
                with self.subTest(host=host):
                    config.write_text('[data]\nhost = "%s"\nrole = "pro"\nextras = ""\n' % host)
                    out = subprocess.check_output([
                        "chezmoi", "--config", str(config), "--source", str(ROOT),
                        "execute-template", "--file", str(ROOT / "dot_config/agents/tool-gate.json.tmpl"),
                    ], text=True)
                    rendered = json.loads(out)
                    self.assertNotIn("modes", rendered)
                    self.assertEqual(rendered["persistence"], {"project": "shared", "userWritable": False})
                    directories = rendered["directories"]
                    self.assertTrue(directories["enabled"])
                    self.assertEqual(directories["private"], policy["private"])
                    self.assertEqual(directories["alwaysWrite"], policy["alwaysWrite"])
                    self.assertEqual(directories["exemptCommands"], policy["exemptCommands"])
                    self.assertEqual(directories["derived"], [
                        {"path": path, "hint": policy["derived"]["hint"]}
                        for path in policy["derived"]["paths"]
                    ])

    def test_codex_caller_trusts_only_mcp_repos(self):
        output = io.StringIO()
        with mock.patch.dict(os.environ, {"CHEZMOI_SOURCE_DIR": str(ROOT)}), \
                mock.patch.object(d.a, "project_servers", return_value={"vercel": ["/mcp", "/mcp"]}), \
                mock.patch.object(d.a, "mcp_servers", return_value={}), \
                mock.patch.object(d.a, "merge_codex_toml", side_effect=lambda text, servers: text), \
                mock.patch.object(d, "codex_global", side_effect=lambda text: text), \
                mock.patch("sys.stdin", io.StringIO('model = "local"\n')), \
                mock.patch("sys.stdout", output):
            runpy.run_path(str(ROOT / "private_dot_codex/modify_private_config.toml"))
        self.assertEqual(tomllib.loads(output.getvalue()), {
            "model": "local", "projects": {"/mcp": {"trust_level": "trusted"}},
        })

    def test_project_generators_are_removed(self):
        for path in (ROOT / "Projects").rglob("*"):
            if path.is_file():
                self.assertNotIn("agent_dirs.run(", path.read_text(), str(path))
                self.assertNotIn('template "agent-dirs/tool-gate.json"', path.read_text(), str(path))
        for name in ("grants", "claude_local", "codex_project", "opencode_project",
                     "codex_trusted_repos", "run"):
            self.assertFalse(hasattr(d, name), name)


if __name__ == "__main__":
    unittest.main()
