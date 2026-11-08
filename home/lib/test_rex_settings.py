import io
import json
import plistlib
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from lib import rex_settings as r


SENTINEL = "secret fixture never printed"
PREFERENCES = {
    "Workspace.appearance": "system",
    "Workspace.darkThemeID": "merino-dark",
    "Workspace.lightThemeID": "terracotta-noon",
    "Workspace.tabStyle": "vertical",
    "Workspace.sidebarPosition": "left",
    "Workspace.interfaceStyle": "useTheme",
    "Workspace.tabIconTintMode": "off",
    "Workspace.inactivePaneFadeMode": "both",
    "Workspace.terminalImproveTextContrast": True,
    "Workspace.usesStandardInactiveWindowPaneStyles": True,
    "rex.agents.names-sessions": True,
}


def result(code=0, out=b"", err=b""):
    return subprocess.CompletedProcess([], code, out, err)


class FakeDefaults:
    def __init__(self):
        self.state = {"RexSync.servers": b"\x00\xffsecret\x80", "cookie": SENTINEL}
        self.calls = []
        self.fail_at = None
        self.ignore = False
        self.on_write = None
        self.write_count = 0

    def run(self, args):
        self.calls.append(args[:])
        if args == ["defaults", "export", r.DOMAIN, "-"]:
            return result(out=plistlib.dumps(self.state, fmt=plistlib.FMT_BINARY))
        if len(args) == 6 and args[:3] == ["defaults", "write", r.DOMAIN]:
            key, kind, value = args[3:]
            assert key in PREFERENCES
            assert kind == ("-bool" if type(PREFERENCES[key]) is bool else "-string")
            self.write_count += 1
            if self.on_write:
                self.on_write(self.state)
                self.on_write = None
            if self.write_count == self.fail_at:
                return result(1, err=SENTINEL.encode())
            if not self.ignore:
                self.state[key] = value == "true" if kind == "-bool" else value
            return result()
        raise AssertionError("unexpected command (import, lifecycle or whole-domain write)")


class Preferences(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "settings.json"
        self.manifest({"rex": {"preferences": PREFERENCES, "other": "allowed"}})
        self.fake = FakeDefaults()
        self.enterContext(patch.object(r, "_run", side_effect=self.fake.run))
        self.enterContext(patch.object(r.subprocess, "run", side_effect=AssertionError("real command forbidden")))
        self.enterContext(patch.object(r.sys, "platform", "darwin"))

    def manifest(self, data):
        self.path.write_text(json.dumps(data))

    def invoke(self, check=False):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = r.main(["--settings", str(self.path)] + (["--check"] if check else []))
        self.assertNotIn(SENTINEL, out.getvalue() + err.getvalue())
        return code, out.getvalue(), err.getvalue()

    def test_managed_manifest_matches_reviewed_allowlist(self):
        managed = Path(__file__).resolve().parents[1] / ".chezmoidata/rex.json"
        self.assertEqual(r.load_settings(managed), PREFERENCES)

    def test_non_mac_refuses_native_io(self):
        with patch.object(r.sys, "platform", "linux"):
            self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(self.fake.calls, [])

    def test_type_sensitive_diff(self):
        key = "Workspace.terminalImproveTextContrast"
        self.assertEqual(r.changed_preferences({key: 1}, {key: True}), {key: True})
        self.assertEqual(r.changed_preferences({key: True}, {key: True}), {})
        self.assertEqual(r.changed_preferences({}, {key: False}), {key: False})

    def test_invalid_settings_before_native_io(self):
        cases = [{}, {"rex": {}}, {"rex": {"preferences": []}},
                 {"rex": {"preferences": {"unknown": True}}},
                 {"rex": {"preferences": {"Workspace.appearance": True}}},
                 {"rex": {"preferences": {"Workspace.terminalImproveTextContrast": 1}}}]
        for data in cases:
            with self.subTest(data=data):
                self.manifest(data)
                self.assertEqual(self.invoke()[0], 2)
                self.assertEqual(self.fake.calls, [])
        for raw in ('{', '{"rex":{"preferences":{},"preferences":{}}}', 'null'):
            self.path.write_text(raw)
            self.assertEqual(self.invoke()[0], 2)
            self.assertEqual(self.fake.calls, [])
        self.path.unlink()
        self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(self.fake.calls, [])

    def test_noop_check_drift_and_apply_preserves_unmanaged(self):
        original = self.fake.state["RexSync.servers"]
        code, out, err = self.invoke(check=True)
        self.assertEqual((code, out, err), (1, "", ""))
        self.assertEqual(len(self.fake.calls), 1)
        self.fake.on_write = lambda state: state.update({"concurrent": b"\x00\xfe", "RexSync.servers": original + b"updated"})
        code, out, err = self.invoke()
        self.assertEqual((code, err), (0, ""))
        for key in PREFERENCES:
            self.assertIn(key, out)
            self.assertEqual(self.fake.state[key], PREFERENCES[key])
        self.assertNotIn("merino-dark", out)
        self.assertEqual(self.fake.state["RexSync.servers"], original + b"updated")
        self.assertEqual(self.fake.state["concurrent"], b"\x00\xfe")
        self.assertEqual(self.invoke(), (0, "", ""))
        self.assertEqual(self.invoke(check=True), (0, "", ""))

    def test_wrong_native_types_corrected_and_unmanaged_bytes_unchanged(self):
        self.fake.state.update(PREFERENCES)
        self.fake.state["Workspace.terminalImproveTextContrast"] = 1
        before = self.fake.state["RexSync.servers"]
        self.assertEqual(self.invoke()[0], 0)
        writes = [call for call in self.fake.calls if call[1] == "write"]
        self.assertEqual(writes, [["defaults", "write", r.DOMAIN, "Workspace.terminalImproveTextContrast", "-bool", "true"]])
        self.assertEqual(self.fake.state["RexSync.servers"], before)

    def test_partial_failure_retry_and_ignored_write(self):
        self.fake.fail_at = 3
        self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(len(set(self.fake.state) & set(PREFERENCES)), 2)
        self.fake.fail_at = None
        self.assertEqual(self.invoke()[0], 0)
        self.assertEqual(self.invoke(), (0, "", ""))
        self.fake.state.pop("Workspace.appearance")
        self.fake.ignore = True
        self.assertEqual(self.invoke()[0], 2)
        self.fake.ignore = False
        self.assertEqual(self.invoke()[0], 0)

    def test_missing_domain_is_initialized_and_readback_failure_retries(self):
        native = self.fake.run
        first = True

        def missing_once(args):
            nonlocal first
            if first and args[:2] == ["defaults", "export"]:
                first = False
                return result(1, err=f"Domain {r.DOMAIN} does not exist".encode())
            return native(args)

        with patch.object(r, "_run", side_effect=missing_once):
            self.assertEqual(self.invoke()[0], 0)
        self.fake.state.pop("Workspace.appearance")
        reads = 0

        def bad_readback(args):
            nonlocal reads
            if args[:2] == ["defaults", "export"]:
                reads += 1
                if reads == 2:
                    return result(out=SENTINEL.encode())
            return native(args)

        with patch.object(r, "_run", side_effect=bad_readback):
            self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(self.invoke(), (0, "", ""))

    def test_false_bool_write(self):
        self.manifest({"rex": {"preferences": {"rex.agents.names-sessions": False}}})
        self.assertEqual(self.invoke()[0], 0)
        self.assertIn(["defaults", "write", r.DOMAIN, "rex.agents.names-sessions", "-bool", "false"], self.fake.calls)
        self.assertIs(self.fake.state["rex.agents.names-sessions"], False)

    def test_writer_rejects_invalid_batch_before_any_write(self):
        for values in ({"unknown": "x"}, {"Workspace.appearance": 1},
                       {"Workspace.appearance": "ok", "unknown": True}):
            with self.assertRaises(r.SettingsError):
                r._write_defaults(values)
        self.assertEqual(self.fake.calls, [])

    def test_missing_and_malformed_domain(self):
        missing = result(1, err=f"Domain {r.DOMAIN} does not exist".encode())
        with patch.object(r, "_run", return_value=missing):
            self.assertEqual(r._read_defaults(), {})
        for res in (result(1, err=SENTINEL.encode()),
                    result(2, err=missing.stderr),
                    result(1, err=b"other.domain does not exist"),
                    result(out=SENTINEL.encode()),
                    result(out=plistlib.dumps([SENTINEL]))):
            with self.subTest(res=res), patch.object(r, "_run", return_value=res):
                with self.assertRaises(r.SettingsError) as exc:
                    r._read_defaults()
                self.assertNotIn(SENTINEL, str(exc.exception))

    def test_native_failures_are_bounded_and_redacted(self):
        for error in (OSError(SENTINEL), subprocess.TimeoutExpired([SENTINEL], 15)):
            with patch.object(r.subprocess, "run", side_effect=error):
                with self.assertRaises(r.SettingsError) as exc:
                    # Bypass the setUp mock for _run.
                    with patch.object(r, "_run", new=REAL_RUN):
                        r._read_defaults()
                self.assertNotIn(SENTINEL, str(exc.exception))
        with patch.object(r.subprocess, "run", return_value=result()) as run:
            REAL_RUN(["fixture"])
            run.assert_called_once_with(["fixture"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        timeout=15, check=False)


REAL_RUN = r._run

if __name__ == "__main__":
    unittest.main()
