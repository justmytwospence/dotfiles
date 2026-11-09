import copy
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
ACTIVITY_KEY = "Workspace.programActivityStatusPreferences"
ACTIVITY = {
    "working": {"isEnabled": True, "showsInTabs": True, "showsNotification": False, "badgesDockIcon": False, "playsSound": False},
    "blocked": {"isEnabled": True, "showsInTabs": True, "showsNotification": True, "badgesDockIcon": True, "playsSound": True},
    "error": {"isEnabled": True, "showsInTabs": True, "showsNotification": True, "badgesDockIcon": True, "playsSound": True},
    "done": {"isEnabled": True, "showsInTabs": True, "showsNotification": True, "badgesDockIcon": True, "playsSound": False},
}
PREFERENCES = {
    "Workspace.showsProgramStatusInTabs": True,
    "Workspace.showsProgramActivityNotifications": True,
    "Workspace.showsProgramActivityDockBadge": True,
    "Workspace.playsProgramActivitySounds": True,
    ACTIVITY_KEY: ACTIVITY,
    "Workspace.appearance": "system",
    "Workspace.darkThemeID": "merino-dark",
    "Workspace.lightThemeID": "terracotta-noon",
    "Workspace.tabStyle": "vertical",
    "Workspace.sidebarPosition": "left",
    "Workspace.interfaceStyle": "blendTheme",
    "Workspace.usesPaneGlass": True,
    "Workspace.tabIconTintMode": "off",
    "Workspace.inactivePaneFadeMode": "both",
    "Workspace.terminalFontName": "JetBrains Mono",
    "Workspace.terminalFontPointSize": 14.0,
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
            assert kind == ("-data" if key == ACTIVITY_KEY else "-bool" if type(PREFERENCES[key]) is bool
                            else "-float" if type(PREFERENCES[key]) is float else "-string")
            if kind == "-data":
                decoded = json.loads(bytes.fromhex(value))
                assert isinstance(decoded, dict)
                for state, flags in ACTIVITY.items():
                    for flag, expected in flags.items():
                        assert type(decoded[state][flag]) is bool and decoded[state][flag] is expected
            self.write_count += 1
            if self.on_write:
                self.on_write(self.state)
                self.on_write = None
            if self.write_count == self.fail_at:
                return result(1, err=SENTINEL.encode())
            if not self.ignore:
                self.state[key] = (bytes.fromhex(value) if kind == "-data" else value == "true" if kind == "-bool"
                                   else float(value) if kind == "-float" else value)
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

    def test_glass_preferences_typed_write_and_noop(self):
        style = "Workspace.interfaceStyle"
        glass = "Workspace.usesPaneGlass"
        self.manifest({"rex": {"preferences": {style: "blendTheme", glass: True}}})
        self.fake.state[style] = "useTheme"
        opaque = self.fake.state["RexSync.servers"]
        self.assertEqual(self.invoke(check=True), (1, "", ""))
        self.assertFalse(any(call[1:2] == ["write"] for call in self.fake.calls))
        self.assertEqual(self.invoke()[0], 0)
        writes = [call for call in self.fake.calls if call[1:2] == ["write"]]
        self.assertEqual(writes, [
            ["defaults", "write", r.DOMAIN, style, "-string", "blendTheme"],
            ["defaults", "write", r.DOMAIN, glass, "-bool", "true"],
        ])
        self.assertIs(type(self.fake.state[style]), str)
        self.assertEqual(self.fake.state[style], "blendTheme")
        self.assertIs(self.fake.state[glass], True)
        self.assertEqual(self.fake.state["RexSync.servers"], opaque)
        self.fake.calls.clear()
        self.assertEqual(self.invoke(), (0, "", ""))
        self.assertEqual(self.invoke(check=True), (0, "", ""))
        self.assertFalse(any(call[1:2] == ["write"] for call in self.fake.calls))

    def test_glass_boolean_type_drift(self):
        key = "Workspace.usesPaneGlass"
        self.manifest({"rex": {"preferences": {key: True}}})
        for value in (False, 1, "true"):
            with self.subTest(value=value):
                self.fake.state[key] = value
                self.fake.calls.clear()
                self.assertEqual(self.invoke(check=True), (1, "", ""))
                self.assertFalse(any(call[1:2] == ["write"] for call in self.fake.calls))
                self.assertEqual(self.invoke()[0], 0)
                self.assertIn(["defaults", "write", r.DOMAIN, key, "-bool", "true"], self.fake.calls)
                self.assertIs(self.fake.state[key], True)
        self.manifest({"rex": {"preferences": {key: False}}})
        self.fake.calls.clear()
        self.assertEqual(self.invoke()[0], 0)
        self.assertIn(["defaults", "write", r.DOMAIN, key, "-bool", "false"], self.fake.calls)
        self.assertIs(self.fake.state[key], False)
        self.fake.calls.clear()
        self.assertEqual(self.invoke(), (0, "", ""))
        self.assertEqual(self.invoke(check=True), (0, "", ""))
        self.assertFalse(any(call[1:2] == ["write"] for call in self.fake.calls))

    def test_invalid_glass_boolean_before_native_io(self):
        for value in (0, 1, "true", None, [], {}):
            with self.subTest(value=value):
                values = {"Workspace.interfaceStyle": "blendTheme", "Workspace.usesPaneGlass": value}
                self.manifest({"rex": {"preferences": values}})
                self.assertEqual(self.invoke()[0], 2)
                with self.assertRaises(r.SettingsError):
                    r._write_defaults(values)
                self.assertEqual(self.fake.calls, [])

    def test_font_size_write_drift_and_noop(self):
        key = "Workspace.terminalFontPointSize"
        self.manifest({"rex": {"preferences": {key: 14.0}}})
        opaque = self.fake.state["RexSync.servers"]
        for value in (None, "14.0", True, 14, 15.0):
            with self.subTest(value=value):
                self.fake.state.pop(key, None)
                if value is not None:
                    self.fake.state[key] = value
                self.fake.calls.clear()
                self.assertEqual(self.invoke(check=True), (1, "", ""))
                self.assertFalse(any(call[1:2] == ["write"] for call in self.fake.calls))
                self.assertEqual(self.invoke()[0], 0)
                self.assertIn(["defaults", "write", r.DOMAIN, key, "-float", "14.0"], self.fake.calls)
                self.assertIs(type(self.fake.state[key]), float)
                self.assertEqual(self.fake.state[key], 14.0)
                self.assertEqual(self.fake.state["RexSync.servers"], opaque)
                self.fake.calls.clear()
                self.assertEqual(self.invoke(), (0, "", ""))
                self.assertEqual(self.invoke(check=True), (0, "", ""))
                self.assertFalse(any(call[1:2] == ["write"] for call in self.fake.calls))

    def test_invalid_font_sizes_rejected_before_native_io(self):
        key = "Workspace.terminalFontPointSize"
        for value in (14, True, False, 0.0, -1.0, "14.0", None,
                      float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                values = {"Workspace.terminalFontName": "JetBrains Mono", key: value}
                self.manifest({"rex": {"preferences": values}})
                self.assertEqual(self.invoke()[0], 2)
                with self.assertRaises(r.SettingsError):
                    r._write_defaults(values)
                self.assertEqual(self.fake.calls, [])

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
            actual = self.fake.state[key]
            self.assertEqual(json.loads(actual) if key == ACTIVITY_KEY else actual, PREFERENCES[key])
        self.assertNotIn("merino-dark", out)
        self.assertEqual(self.fake.state["RexSync.servers"], original + b"updated")
        self.assertEqual(self.fake.state["concurrent"], b"\x00\xfe")
        self.assertEqual(self.invoke(), (0, "", ""))
        self.assertEqual(self.invoke(check=True), (0, "", ""))

    def test_wrong_native_types_corrected_and_unmanaged_bytes_unchanged(self):
        self.fake.state.update(PREFERENCES)
        self.fake.state[ACTIVITY_KEY] = json.dumps(ACTIVITY).encode()
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
                       {"Workspace.appearance": "ok", "unknown": True},
                       {"Workspace.appearance": "ok", ACTIVITY_KEY: {"working": {}}},
                       {"Workspace.appearance": "ok", ACTIVITY_KEY: b"{}"}):
            with self.assertRaises(r.SettingsError):
                r._write_defaults(values)
        self.assertEqual(self.fake.calls, [])

    def test_activity_manifest_validation_before_native_io(self):
        self.assertEqual(r.ACTIVITY_PREFERENCE, ACTIVITY_KEY)
        self.assertEqual(set(r.ACTIVITY_STATES), set(ACTIVITY))
        self.assertEqual(set(r.ACTIVITY_FLAGS), set(ACTIVITY["working"]))
        cases = []
        missing = copy.deepcopy(ACTIVITY)
        missing.pop("working")
        cases.append(missing)
        extra = copy.deepcopy(ACTIVITY)
        extra["future"] = {}
        cases.append(extra)
        missing = copy.deepcopy(ACTIVITY)
        missing["working"].pop("isEnabled")
        cases.append(missing)
        extra = copy.deepcopy(ACTIVITY)
        extra["working"]["sound"] = "tap"
        cases.append(extra)
        for value in (1, 0, None, [], "true"):
            invalid = copy.deepcopy(ACTIVITY)
            invalid["working"]["isEnabled"] = value
            cases.append(invalid)
        for value in (None, [], "invalid", 1):
            cases.append(value)
            invalid = copy.deepcopy(ACTIVITY)
            invalid["blocked"] = value
            cases.append(invalid)
        for value in cases:
            with self.subTest(value=value):
                self.manifest({"rex": {"preferences": {"Workspace.appearance": "ok", ACTIVITY_KEY: value}}})
                self.assertEqual(self.invoke()[0], 2)
                self.assertEqual(self.fake.calls, [])

    def test_activity_json_data_write_and_semantic_noop(self):
        self.assertEqual(self.invoke()[0], 0)
        value = self.fake.state[ACTIVITY_KEY]
        self.assertIs(type(value), bytes)
        self.assertEqual(json.loads(value), ACTIVITY)
        self.assertEqual(value, json.dumps(ACTIVITY, sort_keys=True, separators=(",", ":")).encode())
        writes = [call for call in self.fake.calls if call[1:2] == ["write"] and call[3] == ACTIVITY_KEY]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][4], "-data")
        self.assertEqual(bytes.fromhex(writes[0][5]), value)
        self.fake.calls.clear()
        self.assertEqual(self.invoke(), (0, "", ""))
        self.assertEqual(self.invoke(check=True), (0, "", ""))
        self.assertFalse(any(call[1:2] == ["write"] for call in self.fake.calls))
        self.fake.state[ACTIVITY_KEY] = json.dumps(dict(reversed(list(ACTIVITY.items()))), indent=4).encode()
        self.fake.calls.clear()
        self.assertEqual(self.invoke(), (0, "", ""))
        self.assertEqual(self.invoke(check=True), (0, "", ""))
        self.assertFalse(any(call[1:2] == ["write"] for call in self.fake.calls))

    def test_activity_preserves_sound_unknown_fields_and_statuses(self):
        live = copy.deepcopy(ACTIVITY)
        live["blocked"].update({"sound": "warning", "futureField": {"nested": [1, 2]}})
        live["done"]["sound"] = "success"
        live["future"] = {"sound": "tap", "opaque": SENTINEL}
        live["working"]["isEnabled"] = False
        self.fake.state[ACTIVITY_KEY] = json.dumps(live).encode()
        opaque = self.fake.state["RexSync.servers"]
        self.assertEqual(self.invoke()[0], 0)
        live["working"]["isEnabled"] = True
        self.assertEqual(json.loads(self.fake.state[ACTIVITY_KEY]), live)
        self.assertEqual(self.fake.state["RexSync.servers"], opaque)
        self.assertEqual(self.invoke(), (0, "", ""))

    def test_activity_type_sensitive_leaf_drift(self):
        live = copy.deepcopy(ACTIVITY)
        live["working"]["isEnabled"] = 1
        live["working"]["playsSound"] = 0
        live["working"]["sound"] = "tap"
        live["blocked"].pop("showsInTabs")
        live.pop("error")
        self.fake.state[ACTIVITY_KEY] = json.dumps(live).encode()
        self.assertEqual(self.invoke(check=True)[0], 1)
        self.assertEqual(self.invoke()[0], 0)
        actual = json.loads(self.fake.state[ACTIVITY_KEY])
        self.assertIs(actual["working"]["isEnabled"], True)
        self.assertIs(actual["working"]["playsSound"], False)
        self.assertEqual(actual["working"]["sound"], "tap")
        self.assertEqual(actual["blocked"], ACTIVITY["blocked"])
        self.assertEqual(actual["error"], ACTIVITY["error"])
        self.assertEqual(self.invoke(), (0, "", ""))

    def test_activity_reloads_latest_value_before_write(self):
        self.manifest({"rex": {"preferences": {ACTIVITY_KEY: ACTIVITY}}})
        live = copy.deepcopy(ACTIVITY)
        live["blocked"]["isEnabled"] = False
        live["blocked"]["nested"] = {"version": "old"}
        self.fake.state[ACTIVITY_KEY] = json.dumps(live).encode()
        native = self.fake.run
        reads = 0

        def concurrent(args):
            nonlocal reads
            if args[:2] == ["defaults", "export"]:
                reads += 1
                if reads == 2:
                    live["blocked"]["nested"]["version"] = "new"
                    self.fake.state[ACTIVITY_KEY] = json.dumps(live).encode()
            return native(args)

        with patch.object(r, "_run", side_effect=concurrent):
            self.assertEqual(self.invoke()[0], 0)
        self.assertGreaterEqual(reads, 2)
        self.assertEqual(json.loads(self.fake.state[ACTIVITY_KEY])["blocked"]["nested"], {"version": "new"})

    def test_activity_malformed_live_value_fails_redacted(self):
        with self.assertRaises(r.SettingsError) as exc:
            r.changed_preferences({ACTIVITY_KEY: None}, {ACTIVITY_KEY: ACTIVITY})
        self.assertNotIn(SENTINEL, str(exc.exception))
        self.manifest({"rex": {"preferences": {ACTIVITY_KEY: ACTIVITY}}})
        cases = [SENTINEL, 1, True, [SENTINEL], {"secret": SENTINEL},
                 b'\xff', (SENTINEL + '{').encode(),
                 ('{"secret":"' + SENTINEL + '","x":1,"x":2}').encode(),
                 ('{"secret":"' + SENTINEL + '","x":NaN}').encode(),
                 ('{"secret":"' + SENTINEL + '","x":Infinity}').encode(),
                 ('["' + SENTINEL + '"]').encode(), b'null',
                 ('{"working":"' + SENTINEL + '"}').encode()]
        for value in cases:
            with self.subTest(value=repr(value)):
                self.fake.state[ACTIVITY_KEY] = value
                self.fake.calls.clear()
                self.assertEqual(self.invoke()[0], 2)
                self.assertEqual(self.invoke(check=True)[0], 2)
                self.assertFalse(any(call[1:2] == ["write"] for call in self.fake.calls))

    def test_activity_partial_failure_and_ignored_write_retry(self):
        self.manifest({"rex": {"preferences": {"Workspace.appearance": "system", ACTIVITY_KEY: ACTIVITY}}})
        self.fake.fail_at = 2
        self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(self.fake.state["Workspace.appearance"], "system")
        self.assertNotIn(ACTIVITY_KEY, self.fake.state)
        self.fake.fail_at = None
        self.assertEqual(self.invoke()[0], 0)
        self.fake.state.pop(ACTIVITY_KEY)
        self.fake.ignore = True
        self.assertEqual(self.invoke()[0], 2)
        self.assertNotIn(ACTIVITY_KEY, self.fake.state)
        self.fake.ignore = False
        self.assertEqual(self.invoke()[0], 0)
        self.assertEqual(self.invoke(), (0, "", ""))

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
