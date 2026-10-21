import json
from pathlib import Path
import subprocess
import unittest
from copy import deepcopy

from lib.hermes_settings import merge_connections

ROOT = Path(__file__).resolve().parents[1]
MANAGED = ROOT / "private_Library/private_Application Support/private_Hermes/connections.managed.json"
WRAPPER = MANAGED.with_name("modify_private_connections.json")


class HermesSettingsTests(unittest.TestCase):
    def setUp(self):
        self.managed = json.loads(MANAGED.read_text())

    def test_first_install_and_idempotence(self):
        result = merge_connections({}, self.managed)
        self.assertEqual(result["primary"], "homelab")
        self.assertEqual(result["lastUsed"], "local")
        self.assertEqual(result["connections"][0]["kind"], "local")
        self.assertEqual(merge_connections(result, self.managed), result)
        self.assertNotIn("token", result["connections"][1])

    def test_preserves_auth_and_other_state(self):
        live = merge_connections({}, self.managed)
        live["connections"][1].update(token={"encoding": "fixture", "value": "local-only"}, headers={"X-Test": "local-only"}, installId="local-id")
        live["connections"].append({"id": "other", "kind": "remote", "label": "Other", "url": "https://other.invalid"})
        live["lastUsed"] = "other"
        live["quarantined"] = [{"entry": {"broken": True}, "reason": "fixture"}]
        before = deepcopy(live)
        result = merge_connections(live, self.managed)
        self.assertEqual(result, before)
        self.assertEqual(live, before)

    def test_refuses_invalid_or_future_state(self):
        for live in ([], {"version": 1}, {"version": 3}, {"version": 2, "connections": {}}, {"version": 2, "connections": [None]}):
            with self.subTest(live=live), self.assertRaises(ValueError):
                merge_connections(live, self.managed)

    def test_refuses_endpoint_and_label_collisions(self):
        for change in ({"url": "https://different.invalid"}, {"kind": "local"}):
            live = merge_connections({}, self.managed)
            live["connections"][1].update(change)
            with self.assertRaises(ValueError):
                merge_connections(live, self.managed)
        live = {"version": 2, "connections": [{"id": "other", "label": "HOMELAB"}]}
        with self.assertRaises(ValueError):
            merge_connections(live, self.managed)

    def test_rejects_managed_credentials(self):
        self.managed["connections"][0]["token"] = "must-not-be-tracked"
        with self.assertRaises(ValueError):
            merge_connections({}, self.managed)

    def test_wrapper_preserves_bytes_and_rejects_malformed_json(self):
        text = json.dumps(merge_connections({}, self.managed), indent=4) + "\n"
        result = subprocess.run(["python3", "-B", str(WRAPPER)], input=text, text=True, capture_output=True, env={**__import__("os").environ, "CHEZMOI_SOURCE_DIR": str(ROOT)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, text)
        bad = subprocess.run(["python3", "-B", str(WRAPPER)], input="{broken", text=True, capture_output=True, env={**__import__("os").environ, "CHEZMOI_SOURCE_DIR": str(ROOT)})
        self.assertNotEqual(bad.returncode, 0)
        self.assertEqual(bad.stdout, "")


if __name__ == "__main__":
    unittest.main()
