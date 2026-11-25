"""Tests for the Pi settings merge and managed configuration.
Fixtures only: no live settings or checkouts are modified."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "private_dot_pi/private_agent"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "lib"))
import agent_settings as a  # noqa: E402

SUITE = "git:github.com/justmytwospence/pi-plugins"
PIN = SUITE + "@e6e4f87cd0c19563741afe70c09f59eb964fdbfd"
AUTORESEARCH = {"source": "npm:pi-autoresearch", "skills": []}
MANAGED_PACKAGES = [
    "npm:@gotgenes/pi-anthropic-auth", "npm:pi-web-access",
    PIN,
    AUTORESEARCH,
]


def managed():
    return {"packages": copy.deepcopy(MANAGED_PACKAGES), "defaultModel": "claude-opus-5-5", "theme": "light/dark"}


def live():
    return {"lastChangelogVersion": "1.1.0", "deviceId": "4280ef3d", "theme": "dark",
            "packages": copy.deepcopy(MANAGED_PACKAGES) + ["../../Projects/pi-quiz"]}


class Merge(unittest.TestCase):
    def test_managed_wins_pi_keys_and_local_packages_stay(self):
        out = a.merge_pi_settings(live(), managed())
        self.assertEqual(out["theme"], "light/dark")
        self.assertEqual(out["deviceId"], "4280ef3d")
        self.assertEqual(out["lastChangelogVersion"], "1.1.0")
        self.assertEqual(out["packages"], MANAGED_PACKAGES + ["../../Projects/pi-quiz"])

    def test_absent_live_file_is_the_managed_file(self):
        self.assertEqual(a.merge_pi_settings({}, managed()), managed())

    def test_live_only_package_the_repo_dropped_goes(self):
        current = live()
        current["packages"].append("npm:pi-something-installed-by-hand")
        out = a.merge_pi_settings(current, managed())
        self.assertNotIn("npm:pi-something-installed-by-hand", out["packages"])
        self.assertIn("../../Projects/pi-quiz", out["packages"])

    def test_todo_npm_provider_is_retired_without_dropping_local_packages(self):
        current = live()
        current["packages"].append("npm:@juicesharp/rpiv-todo")
        out = a.merge_pi_settings(current, managed())
        self.assertNotIn("npm:@juicesharp/rpiv-todo", out["packages"])
        self.assertIn("../../Projects/pi-quiz", out["packages"])

    def test_bash_becomes_shell_path(self):
        out = a.merge_pi_settings(live(), managed(), bash=a.HOMEBREW_BASH)
        self.assertEqual(out["shellPath"], a.HOMEBREW_BASH)
        self.assertEqual(a.merge_pi_settings(copy.deepcopy(out), managed(), bash=a.HOMEBREW_BASH), out)

    def test_shell_path_goes_without_bash_unless_set_by_hand(self):
        current = live()
        current["shellPath"] = a.HOMEBREW_BASH
        self.assertNotIn("shellPath", a.merge_pi_settings(current, managed()))
        current["shellPath"] = "/usr/local/bin/bash"
        self.assertEqual(a.merge_pi_settings(current, managed())["shellPath"], "/usr/local/bin/bash")

    def test_pi_bash_only_a_bash_that_exists(self):
        bash = a.pi_bash()
        if sys.platform != "darwin":
            self.assertIsNone(bash)
        elif bash is not None:
            self.assertTrue(os.access(bash, os.X_OK))

    def test_idempotent(self):
        once = a.merge_pi_settings(live(), managed())
        self.assertEqual(a.merge_pi_settings(copy.deepcopy(once), managed()), once)

    def test_run_json_echoes_unchanged_text_and_rejects_malformed(self):
        text = json.dumps(a.merge_pi_settings(live(), managed()), indent=2) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "x"))
            with open(os.path.join(tmp, "x", "m.json"), "w") as handle:
                json.dump(managed(), handle)
            env = dict(os.environ, CHEZMOI_SOURCE_DIR=tmp)
            code = "import sys; sys.path.insert(0, %r); import agent_settings as a; a.run_json('x/m.json', a.merge_pi_settings)" % str(ROOT / "lib")
            proc = subprocess.run([sys.executable, "-B", "-c", code], input=text, capture_output=True, text=True, env=env)
            self.assertEqual(proc.stdout, text)
            proc = subprocess.run([sys.executable, "-B", "-c", code], input="{not json", capture_output=True, text=True, env=env)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")


class PiFamilies(unittest.TestCase):
    def setUp(self):
        self.managed = json.loads((AGENT / "settings.managed.json").read_text())
        self.base = self.managed["enabledModels"]
        self.families = self.managed["_enabledModelFamilies"]

    def resolve(self, live=(), registry=None):
        return a.resolve_pi_enabled_models(self.base, list(live), self.families, registry or {})

    def test_numeric_stable_physical_provider_and_order(self):
        entries = [{"id": x, "provider": "openai"} for x in
                   ("gpt-6.9-astra", "gpt-6.10-astra", "gpt-6.99-astra-mini", "gpt-6.2-sol")]
        entries += [{"id": "gpt-99-sol", "type": "classifier"},
                    {"id": "gpt-99-sol", "api": "pi-virtual"},
                    {"id": "gpt-99-terra", "provider": "other"},
                    {"id": "gpt-6.2-sol", "type": "classifier"}]
        out, notes = self.resolve(registry={"openai": entries, "other": [{"id": "gpt-99-sol"}]})
        expected = list(self.base)
        expected[3] = "openai/gpt-6.10-astra"
        self.assertEqual(out, expected)
        self.assertEqual(notes, [])
        merged = a.merge_pi_settings({"packages": ["../local"], "custom": True}, self.managed, registry={"openai": entries})
        self.assertEqual(merged["enabledModels"], expected)
        self.assertTrue(merged["custom"])
        self.assertIn("../local", merged["packages"])
        self.assertNotIn("_enabledModelFamilies", merged)

    def test_floor_and_ambiguity(self):
        out, _ = self.resolve(["openai/gpt-7-sol"], {"openai": [{"id": "gpt-6.9-sol"}]})
        self.assertIn("openai/gpt-7-sol", out)
        out, notes = self.resolve(registry={"openai": [{"id": "gpt-6.3-sol"}, {"id": "gpt-6.3.0-sol"}]})
        self.assertIn("openai/gpt-6.2-sol", out)
        self.assertTrue(notes)
        out, _ = self.resolve(["openai/gpt-6.3.0-sol"], {"openai": [{"id": "gpt-6.3-sol"}]})
        self.assertIn("openai/gpt-6.3.0-sol", out)
        self.assertEqual(a.model_family_version("gpt-6.10.0-sol", self.families["families"][2]["pattern"]), (6, 10))

    def test_invalid_metadata_and_overlap(self):
        for mutation in (None, {"version": 2, "families": []},
                         {"version": 1, "families": [{"provider": "openai", "pattern": "("}]},
                         {"version": 1, "families": [{"provider": "openai", "pattern": ".*"}]},
                         {"version": 1, "families": [self.families["families"][0]] * 2}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                a.resolve_pi_enabled_models(self.base, [], mutation, {})

    def test_modify_wrapper_uses_temporary_home_and_noop_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            store = home / ".pi/agent/models-store.json"
            store.parent.mkdir(parents=True)
            store.write_text(json.dumps({"openai": {"models": [{"id": "gpt-6.10-sol"}]}}))
            env = dict(os.environ, HOME=tmp, CHEZMOI_SOURCE_DIR=str(ROOT))
            code = "import sys; sys.path.insert(0, %r); import agent_settings as a; a.run_json(%r, a.merge_pi_settings_here)" % (str(ROOT / "lib"), "private_dot_pi/private_agent/settings.managed.json")
            first = subprocess.run([sys.executable, "-B", "-c", code], input="{}", capture_output=True, text=True, env=env, check=True)
            self.assertIn("openai/gpt-6.10-sol", json.loads(first.stdout)["enabledModels"])
            second = subprocess.run([sys.executable, "-B", "-c", code], input=first.stdout, capture_output=True, text=True, env=env, check=True)
            self.assertEqual(first.stdout, second.stdout)
            store.unlink()
            third = subprocess.run([sys.executable, "-B", "-c", code], input=second.stdout, capture_output=True, text=True, env=env, check=True)
            self.assertEqual(second.stdout, third.stdout)
            self.assertIn("cannot read Pi catalog", third.stderr)

    def test_load_and_atomic_converge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings, managed, registry = (root / x for x in ("settings.json", "managed.json", "store.json"))
            managed.write_text(json.dumps(self.managed))
            self.assertEqual(a.load_pi_models_store(registry)[0], {})
            self.assertFalse(a.converge_pi_enabled_models(settings, managed, registry))
            settings.write_text(json.dumps({"enabledModels": self.base, "unrelated": {"keep": True}}))
            registry.write_text("broken")
            self.assertFalse(a.converge_pi_enabled_models(settings, managed, registry))
            before = settings.stat().st_ino
            registry.write_text(json.dumps({"openai": {"models": [{"id": "gpt-6.10-sol"}]}}))
            self.assertTrue(a.converge_pi_enabled_models(settings, managed, registry))
            self.assertNotEqual(before, settings.stat().st_ino)
            self.assertTrue(json.loads(settings.read_text())["unrelated"]["keep"])
            before = settings.stat().st_ino
            self.assertFalse(a.converge_pi_enabled_models(settings, managed, registry))
            self.assertEqual(before, settings.stat().st_ino)


class HookRetirement(unittest.TestCase):
    def test_retired_plan_hook_removed_without_disturbing_other_hooks(self):
        hook = lambda command: {"type": "command", "command": command}
        keep = hook("$HOME/.claude/hooks/keep.sh")
        other = hook("echo other-event")
        for prefix in ("$HOME", "~", "/Users/example"):
            with self.subTest(prefix=prefix):
                retired = hook('"%s/.claude/hooks/save-plan-to-obsidian.sh"' % prefix)
                live = {"Stop": [{"matcher": "*", "hooks": [retired, keep]},
                                 {"hooks": [retired]}],
                        "SessionEnd": [{"hooks": [other]}],
                        "OnlyRetired": [{"hooks": [retired]}]}
                expected = {"Stop": [{"matcher": "*", "hooks": [keep]}],
                            "SessionEnd": [{"hooks": [other]}]}
                once = a.merge_hooks(live, {})
                self.assertEqual(once, expected)
                self.assertEqual(a.merge_hooks(copy.deepcopy(once), {}), once)

    def test_managed_configs_and_source_do_not_enable_retired_hook(self):
        for path in (ROOT / "private_dot_claude/settings.managed.json",
                     AGENT / "pi-plan-mode.managed.json"):
            with self.subTest(path=path):
                self.assertNotIn("save-plan-to-obsidian.sh", json.dumps(json.loads(path.read_text())))
        self.assertFalse((ROOT / "private_dot_claude/hooks/executable_save-plan-to-obsidian.sh").exists())
        self.assertIn(".claude/hooks/save-plan-to-obsidian.sh",
                      (ROOT / ".chezmoiremove").read_text().splitlines())


class PiConfigFiles(unittest.TestCase):
    def test_suite_replaces_retired_npm_packages(self):
        settings = json.loads((AGENT / "settings.managed.json").read_text())
        sources = [p if isinstance(p, str) else p["source"] for p in settings["packages"]]
        self.assertEqual(sum(s.startswith(SUITE + "@") for s in sources), 1)
        retired = {"npm:pi-btw", "npm:pi-vim", "npm:@saadjs/pi-stash",
                   "npm:pi-sticky-last-prompt", "npm:pi-cc-extensions", "npm:@juicesharp/rpiv-todo"}
        self.assertFalse(retired.intersection(sources))
        self.assertIn("npm:pi-autoresearch", sources)
        for source in ("npm:@gotgenes/pi-anthropic-auth", "npm:pi-web-access"):
            self.assertIn(source, sources)
        self.assertIn("**/*.managed.json", (ROOT / ".chezmoiignore").read_text())

    def test_plan_defaults_do_not_seed_implementation_models(self):
        config = json.loads((AGENT / "pi-plan-mode.managed.json").read_text())
        self.assertNotIn("implementationModelMap", config)
        self.assertNotIn("implementationModelMap", a.seed_defaults({}, config))
        for mapping in ({}, [], {"anthropic/claude-fable-5-1": []},
                        {"openai-codex/gpt-6-astra": ["personal:model:high"]},
                        {"unrelated": "personal:model:low"}):
            with self.subTest(mapping=mapping):
                current = {"implementationModelMap": mapping, "plannerTimeoutSeconds": 123}
                once = a.seed_defaults(current, config)
                self.assertEqual(once["implementationModelMap"], mapping)
                self.assertEqual(once["plannerTimeoutSeconds"], 123)
                self.assertEqual(a.seed_defaults(once, config), once)

    def test_todo_config_preserves_the_personal_collapse_key(self):
        config = json.loads((AGENT / "pi-todo.json").read_text())
        self.assertEqual(config["collapseKey"], "ctrl+shift+t")

    def test_keybindings_select_model_on_alt_p_with_cycling_off(self):
        keys = json.loads((AGENT / "keybindings.json").read_text())
        self.assertEqual(keys["app.model.select"], "alt+p")
        self.assertEqual(keys["app.model.cycleForward"], [])
        self.assertEqual(keys["app.model.cycleBackward"], [])
        # Ctrl+D is navigation, never an empty-editor process exit (even without Vim).
        self.assertEqual(keys["app.exit"], [])
        # The other assignments stay as they were.
        # Effort cycles on ctrl+t (opencode's variant key); ctrl+o expands thinking, and
        # ctrl+y is tool-gate's approvals toggle, so Pi's yank gives it up.
        self.assertEqual(keys["app.thinking.cycle"], "ctrl+t")
        self.assertEqual(keys["app.thinking.toggle"], [])
        self.assertEqual(keys["tui.editor.yank"], [])
        self.assertEqual(keys["tui.editor.historyPrevious"], "ctrl+p")
        self.assertEqual(keys["tui.select.up"], ["up", "ctrl+k"])
        self.assertEqual(keys["tui.select.down"], ["down", "ctrl+j"])
        # No global half-page scroll on ctrl+u/ctrl+d: they stay the editor's and pi-vim's.
        bound = {k for v in keys.values() for k in ([v] if isinstance(v, str) else v)}
        self.assertNotIn("ctrl+u", bound)
        self.assertNotIn("ctrl+d", bound)
        self.assertNotIn("ctrl+shift+t", bound)
        # PageUp/PageDown scroll half a page, as in Claude Code.
        self.assertEqual(keys["tui.altScreen.halfPageUp"], "pageUp")
        self.assertEqual(keys["tui.altScreen.halfPageDown"], "pageDown")
        self.assertEqual(keys["tui.altScreen.pageUp"], [])
        self.assertEqual(keys["tui.altScreen.pageDown"], [])

    def test_cc_render_config_is_not_tracked(self):
        """pi-cc-render's settings panel writes its file, so the file is the program's, not a target."""
        self.assertFalse((AGENT / "pi-cc-extensions.json").exists())
        self.assertFalse((AGENT / "pi-cc-render.json").exists())


class HostScopedMcp(unittest.TestCase):
    SERVERS = {
        "everywhere": {"command": "a"},
        "nuc-only": {"command": "b", "hosts": ["nuc"], "projects": ".x"},
    }

    def test_listed_host_keeps_the_server_without_hosts(self):
        out = a.for_host(self.SERVERS, "nuc")
        self.assertEqual(out["nuc-only"], {"command": "b", "projects": ".x"})
        self.assertEqual(out["everywhere"], {"command": "a"})

    def test_other_hosts_get_it_disabled_and_unscoped(self):
        out = a.for_host(self.SERVERS, "mac-pro")
        self.assertEqual(out["nuc-only"], {"command": "b", "enabled": False})
        self.assertNotIn("hosts", self.SERVERS["everywhere"])
        self.assertIn("hosts", self.SERVERS["nuc-only"])  # input untouched

    def test_claude_drops_a_server_off_its_host(self):
        live = {"mcpServers": {"nuc-only": {"type": "stdio", "command": "b", "args": [], "env": {}}}}
        merged = a.merge_claude_mcp(live, a.for_host(self.SERVERS, "mac-air"))
        self.assertNotIn("nuc-only", merged["mcpServers"])
        self.assertIn("everywhere", merged["mcpServers"])

    def test_codex_writes_it_disabled(self):
        text = a.merge_codex_toml("", a.for_host(self.SERVERS, "mac-air"))
        self.assertIn("[mcp_servers.nuc-only]", text)
        self.assertIn("enabled = false", text.split("[mcp_servers.nuc-only]")[1])

    def test_real_set_parses_and_gates_the_nuc_servers(self):
        # This checkout's managed set, not the deployed one: no `chezmoi source-path`, whose
        # state lock another session's apply can hold.
        with mock.patch.dict(os.environ, {"CHEZMOI_SOURCE_DIR": str(ROOT)}):
            mac = a.mcp_servers(host="mac-pro")
            nuc = a.mcp_servers(host="nuc")
        self.assertIs(mac["telebrowser"].get("enabled"), False)
        self.assertNotIn("enabled", nuc["telebrowser"])

    def test_npx_servers_run_outside_any_project(self):
        # Started from a project whose package.json sets devEngines, npx refuses to run under
        # another Node (EBADDEVENGINES); --prefix /tmp keeps it out of the session's project.
        from unittest import mock
        with mock.patch.dict(os.environ, {"CHEZMOI_SOURCE_DIR": str(ROOT)}):
            servers = a.mcp_servers(host="mac-pro")
        for name, server in servers.items():
            if server.get("command") == "npx":
                self.assertEqual(server["args"][:2], ["--prefix", "/tmp"], name)


class RetiredMcp(unittest.TestCase):
    def test_claude_drops_a_retired_server_and_keeps_claude_own(self):
        live = {"mcpServers": {"chrome-devtools": {"command": "npx"}, "mine": {"command": "x"}}}
        merged = a.merge_claude_mcp(live, {})
        self.assertEqual(set(merged["mcpServers"]), {"mine"})

    def test_codex_drops_a_retired_table_and_its_subtables(self):
        text = '[mcp_servers.chrome-devtools]\ncommand = "npx"\n\n[mcp_servers.chrome-devtools.env]\nA = "1"\n\n[mcp_servers.mine]\ncommand = "x"\n'
        out = a.merge_codex_toml(text, {})
        self.assertNotIn("chrome-devtools", out)
        self.assertIn("[mcp_servers.mine]", out)


if __name__ == "__main__":
    unittest.main()
