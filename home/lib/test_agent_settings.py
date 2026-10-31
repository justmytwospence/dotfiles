"""Tests for the Pi settings merge and managed configuration.
Fixtures only: no live settings or checkouts are modified."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "private_dot_pi/private_agent"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "lib"))
import agent_settings as a  # noqa: E402

CHECKOUT = Path.home() / "Projects/pi-plugins"
SUITE = "git:github.com/justmytwospence/pi-plugins"
PIN = SUITE + "@e6e4f87cd0c19563741afe70c09f59eb964fdbfd"
AUTORESEARCH = {"source": "npm:pi-autoresearch", "skills": []}
MANAGED_PACKAGES = [
    "npm:@gotgenes/pi-anthropic-auth", "npm:pi-web-access",
    PIN,
    AUTORESEARCH,
]
# Suite tools excluded from call styling, including the imported pi-todo component.
OWN_RESULT_TOOLS = set()
SUITE_TOOLS = ["ask_planner", "ask_user_question", "bg_kill", "bg_logs", "bg_run", "bg_wait", "continue_plan", "enter_plan_mode",
               "exit_plan_mode", "finish_plan", "herdr", "offer_prompt", "offer_terminal", "plan_ask_planner", "plan_mode_complete", "plan_mode_question",
               "plan_subagents", "plan_submit_merged", "sidebar_agents", "sidebar_transcript", "subagent", "todo"]


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
        self.assertEqual(config["collapseKey"], "ctrl+t")

    def test_keybindings_select_model_on_alt_p_and_alt_m_with_cycling_off(self):
        keys = json.loads((AGENT / "keybindings.json").read_text())
        self.assertEqual(keys["app.model.select"], ["alt+p", "alt+m"])
        self.assertEqual(keys["app.model.cycleForward"], [])
        self.assertEqual(keys["app.model.cycleBackward"], [])
        # The other assignments stay as they were.
        self.assertEqual(keys["app.thinking.cycle"], "alt+t")
        self.assertEqual(keys["tui.editor.historyPrevious"], "ctrl+p")
        self.assertEqual(keys["tui.select.up"], ["up", "ctrl+k"])
        self.assertEqual(keys["tui.select.down"], ["down", "ctrl+j"])
        # No global half-page scroll on ctrl+u/ctrl+d: they stay the editor's and pi-vim's.
        bound = {k for v in keys.values() for k in ([v] if isinstance(v, str) else v)}
        self.assertNotIn("ctrl+u", bound)
        self.assertNotIn("ctrl+d", bound)
        # PageUp/PageDown scroll half a page, as in Claude Code.
        self.assertEqual(keys["tui.altScreen.halfPageUp"], "pageUp")
        self.assertEqual(keys["tui.altScreen.halfPageDown"], "pageDown")
        self.assertEqual(keys["tui.altScreen.pageUp"], [])
        self.assertEqual(keys["tui.altScreen.pageDown"], [])

    def test_cc_render_leaves_suite_tools_alone(self):
        self.assertFalse((AGENT / "pi-cc-extensions.json").exists())
        config = json.loads((AGENT / "pi-cc-render.json").read_text())
        self.assertEqual(config["inputClip"], 500)
        self.assertEqual(config["excludeRenderers"], sorted(SUITE_TOOLS))

    @unittest.skipUnless((CHECKOUT / "packages").is_dir(), "no suite checkout to cross-check")
    def test_suite_tools_list_matches_the_checkout(self):
        """Read-only cross-check of SUITE_TOOLS against the development checkout, when present."""
        names = set()
        for path in [*Path(CHECKOUT, "packages").glob("*/src/**/*.ts"),
                     *Path(CHECKOUT, "packages/pi-todo").glob("todo.ts")]:
            text = path.read_text()
            for match in re.finditer(r"registerTool\(\{\s*name:\s*([A-Za-z_\"']+)", text):
                token = match.group(1)
                if token.startswith(("'", '"')):
                    names.add(token.strip("'\""))
                else:
                    const = re.search(r"(?:const|export const)\s+%s\s*=\s*[\"']([a-z_]+)[\"']" % re.escape(token), text)
                    if const is None:
                        for other in Path(CHECKOUT, "packages", path.relative_to(Path(CHECKOUT, "packages")).parts[0]).rglob("*.ts"):
                            const = re.search(r"(?:const|export const)\s+%s\s*=\s*[\"']([a-z_]+)[\"']" % re.escape(token), other.read_text())
                            if const:
                                break
                    self.assertIsNotNone(const, "could not resolve tool name %s in %s" % (token, path))
                    names.add(const.group(1))
        self.assertEqual(names, set(SUITE_TOOLS) | OWN_RESULT_TOOLS)
        execution = (CHECKOUT / "packages/pi-plan-mode/src/exec.ts").read_text()
        for constant in ("ASK_TOOL", "FINISH_TOOL"):
            definition = re.search(r"registerTool\(\{\s*name:\s*" + constant +
                                   r"\b(.*?)label:", execution, re.S)
            self.assertIsNotNone(definition)
            self.assertIn("ccstyleOwnResult: true", definition.group(1))


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
        mac = a.mcp_servers(host="mac-pro")
        nuc = a.mcp_servers(host="nuc")
        self.assertIs(mac["telebrowser"].get("enabled"), False)
        self.assertNotIn("enabled", nuc["telebrowser"])


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
