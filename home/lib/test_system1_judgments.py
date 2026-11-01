"""Offline checks for the maintained judgment skill and legacy shell entry point."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HOME = Path(__file__).resolve().parents[1]
SCRIPT = HOME / "dot_local/bin/executable_jev-ask"
SKILL = HOME / "dot_agents/skills/jev-judgments/SKILL.md"
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node is required for the shell helper")
class System1JudgmentsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="system1-judgments-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.agent = self.root / "agent"
        self.agent.mkdir()
        self.env = dict(os.environ, HOME=str(self.root), PI_CODING_AGENT_DIR=str(self.agent))
        for key in ("TYPESAFE_API_KEY", "OPENAI_API_KEY", "SYSTEM1_OPENAI_API_KEY", "OPENAI_DECISIONS_API_KEY", "NODE_OPTIONS"):
            self.env.pop(key, None)
        # Even a routing regression must never make a real HTTP request.
        self.mock = self.root / "mock-network.mjs"
        self.mock.write_text("globalThis.fetch = async () => new Response('NETWORK_DISABLED_IN_TEST', { status: 500 });\n")
        self.env["NODE_OPTIONS"] = f"--import={self.mock}"

    def run_helper(self, request=None, args=()):
        value = "" if request is None else request if isinstance(request, str) else json.dumps(request)
        return subprocess.run([NODE, str(SCRIPT), *args], input=value, text=True, capture_output=True, env=self.env, timeout=10)

    def setting(self, value):
        (self.agent / "system1.json").write_text(json.dumps(value))

    def install_cli(self, source):
        cli = self.agent / "git/github.com/justmytwospence/pi-plugins/packages/pi-system1/bin/ask.mjs"
        cli.parent.mkdir(parents=True)
        cli.write_text(source)
        return cli

    def test_missing_and_explicit_jev_settings_preserve_legacy_credential_requirement(self):
        for value in (None, {"backend": "jev"}, {"waterfall": ["jev"], "backend": "openai-decisions"}):
            if value is not None:
                self.setting(value)
            result = self.run_helper({"state": {}, "questions": {}})
            self.assertEqual(result.returncode, 1)
            self.assertIn("TYPESAFE_API_KEY is not set", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_default_agent_directory_is_used_when_environment_override_is_absent(self):
        self.env.pop("PI_CODING_AGENT_DIR")
        agent = self.root / ".pi/agent"
        agent.mkdir(parents=True)
        (agent / "system1.json").write_text('{"backend":"unknown"}')
        result = self.run_helper({})
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid System 1 backend", result.stderr)
        self.assertNotIn("TYPESAFE_API_KEY is not set", result.stderr)

    def test_invalid_settings_do_not_fall_back_to_jev(self):
        for source in ("{bad", "[]", "{}", '{"backend":"chat"}', '{"backend":false}'):
            (self.agent / "system1.json").write_text(source)
            result = self.run_helper({})
            self.assertEqual(result.returncode, 2, source)
            self.assertIn("System 1", result.stderr)
            self.assertNotIn("TYPESAFE_API_KEY is not set", result.stderr)

    def test_unreadable_existing_setting_fails_instead_of_assuming_jev(self):
        (self.agent / "system1.json").mkdir()
        result = self.run_helper({})
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot read System 1 settings", result.stderr)

    def test_decisions_forwards_raw_stdin_without_a_typesafe_key(self):
        self.setting({"backend": "openai-decisions"})
        self.install_cli("let raw = ''; for await (const x of process.stdin) raw += x; process.stdout.write(JSON.stringify({raw, selected: 'openai-decisions'}));\n")
        raw = '{ "state": "Unicode 界", "questions": {"q":{"type":"noul","instructions":"Relevant?"}} }\n'
        result = self.run_helper(raw)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"raw": raw, "selected": "openai-decisions"})
        self.assertEqual(result.stderr, "")

    def test_both_mixed_orders_delegate_without_requiring_a_typesafe_key(self):
        self.install_cli("let raw = ''; for await (const x of process.stdin) raw += x; process.stdout.write(raw);\n")
        raw = '{"state":"fixture","questions":{"q":{"type":"noul","instructions":"True?"}}}'
        for order in (["jev", "openai-decisions"], ["openai-decisions", "jev"]):
            self.setting({"waterfall": order, "backend": "jev"})
            result = self.run_helper(raw)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, raw)
            self.assertEqual(result.stderr, "")

    def test_new_singleton_openai_order_delegates_despite_jev_legacy_mirror(self):
        self.setting({"waterfall": ["openai-decisions"], "backend": "jev"})
        self.install_cli("process.stdout.write('{\"backend\":\"openai-decisions\"}');\n")
        result = self.run_helper({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["backend"], "openai-decisions")

    def test_invalid_waterfalls_never_fall_back_to_a_valid_backend_mirror(self):
        for order in ([], None, "jev", ["jev", "jev"], ["openai"], [0], ["jev", "openai-decisions", "jev"]):
            self.setting({"waterfall": order, "backend": "jev"})
            result = self.run_helper({})
            self.assertEqual(result.returncode, 2, repr(order))
            self.assertIn("invalid System 1 backend/waterfall", result.stderr)
            self.assertNotIn("TYPESAFE_API_KEY is not set", result.stderr)

    def test_mixed_chain_keeps_stdout_json_and_forwards_notices_to_stderr(self):
        self.setting({"waterfall": ["jev", "openai-decisions"]})
        self.env["TYPESAFE_API_KEY"] = "fake-test-key-not-a-secret"
        self.install_cli("process.stderr.write('System 1: Jev unavailable; trying OpenAI Decisions.\\n'); process.stdout.write(JSON.stringify({backend:'openai-decisions',fallback:true}));\n")
        result = self.run_helper({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["fallback"])
        self.assertIn("Jev unavailable", result.stderr)
        self.assertNotIn("NETWORK_DISABLED_IN_TEST", result.stderr)

    def test_mixed_chain_failure_does_not_retry_the_raw_legacy_implementation(self):
        self.setting({"waterfall": ["jev", "openai-decisions"]})
        self.env["TYPESAFE_API_KEY"] = "fake-test-key-not-a-secret"
        self.install_cli("process.stderr.write('system1: all configured providers unavailable\\n'); process.exitCode = 1;\n")
        result = self.run_helper({})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("all configured providers unavailable", result.stderr)
        self.assertNotIn("NETWORK_DISABLED_IN_TEST", result.stderr)

    def test_decisions_forwards_cli_failure_and_never_tries_typesafe(self):
        self.setting({"backend": "openai-decisions"})
        self.env["TYPESAFE_API_KEY"] = "fake-test-key-not-a-secret"
        self.install_cli("process.stderr.write('native credits exhausted\\n'); process.stdout.write('native-output'); process.exitCode = 7;\n")
        result = self.run_helper({})
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, "native-output")
        self.assertEqual(result.stderr, "native credits exhausted\n")

    def test_missing_installed_cli_reports_update_without_provider_fallback(self):
        self.setting({"backend": "openai-decisions"})
        self.env["TYPESAFE_API_KEY"] = "fake-test-key-not-a-secret"
        result = self.run_helper({})
        self.assertEqual(result.returncode, 1)
        self.assertIn("update the Pi suite", result.stderr)
        self.assertIn("No provider outside the configured order", result.stderr)
        self.assertNotIn("NETWORK_DISABLED_IN_TEST", result.stderr)

    def test_legacy_jev_request_and_experimental_options_are_unchanged(self):
        self.env["TYPESAFE_API_KEY"] = "fake-test-key-not-a-secret"
        self.mock.write_text("""
import assert from 'node:assert/strict';
globalThis.fetch = async (url, options) => {
  assert.equal(url, 'https://api.typesafe.ai/v1/systemone');
  assert.equal(options.headers.authorization, 'Bearer fake-test-key-not-a-secret');
  const body = JSON.parse(options.body);
  assert.equal(body.model, 'jev-preview');
  assert.equal(options.headers['TypeSafe-Danger-Zone-Long-Context'], 'true');
  assert.equal(body.questions.locate.type, 'box');
  assert.equal(options.headers['TypeSafe-Danger-Zone-Images'], 'true');
  return Response.json({model: body.model, answers: {locate: {type: 'box', confidence: 0.9}}, usage: {input_tokens: 5}});
};
""")
        result = self.run_helper({"state": "photo", "model": "jev-preview", "long_context": True, "questions": {"locate": {"type": "box", "instructions": "the mug"}}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["model"], "jev-preview")
        self.assertEqual(json.loads(result.stdout)["answers"]["locate"]["type"], "box")

    def test_help_is_offline_and_documents_the_billing_boundary(self):
        result = self.run_helper(args=("--help",))
        self.assertEqual(result.returncode, 0)
        self.assertIn("native System 1", result.stdout)
        self.assertIn("cannot verify the billing source", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_legacy_plan_grant_follows_system1_without_new_permissions(self):
        settings = json.loads((HOME / "private_dot_pi/private_agent/pi-plan-mode.managed.json").read_text())
        grant = settings["commandGrants"]["jev"]
        self.assertEqual(grant["label"], "System 1 judgments")
        self.assertIn("selected by /system1", grant["description"])
        self.assertIn("waterfall", grant["description"])
        self.assertIn("valid denials", grant["description"])
        self.assertEqual(grant["commands"], ["~/.local/bin/jev-ask"])
        self.assertEqual(grant["skills"], ["~/.agents/skills/jev-judgments"])
        self.assertFalse(grant["enabled"])
        self.assertTrue(grant["planMode"])

    def test_skill_uses_the_shared_tool_and_never_hardcodes_a_model(self):
        text = SKILL.read_text()
        self.assertIn("name: jev-judgments", text)
        self.assertIn("tools.system1_judge", text)
        self.assertNotIn("models.getModelOfType", text)
        self.assertNotIn("models.classify", text)
        self.assertIn("do not bypass the switch", text)
        self.assertIn("no purchased balance", text)
        self.assertIn("not subscription OAuth", text)
        self.assertIn("fallback`/`attempts", text)
        self.assertIn("five minutes", text)
        self.assertIn("Valid negative/uncertain judgments", text)


if __name__ == "__main__":
    unittest.main()
