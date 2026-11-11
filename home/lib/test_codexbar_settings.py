"""CodexBar ownership and lifecycle regressions, using fixtures only.

No test reads the real HOME, application bundle, config, defaults, or accounts.
The native-command boundary is an in-memory simulator in lifecycle tests; all
filesystem writes are confined to TemporaryDirectory fixtures.
"""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
import math
import os
from pathlib import Path
import plistlib
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from lib import codexbar_settings as c


MANIFEST = Path(__file__).resolve().parents[1] / ".chezmoidata/codexbar.json"
IDS = tuple(f"7F3A2C10-5E5B-4C1E-9A11-5E55105E000{i}" for i in range(1, 5))
FAMILIES = ("menuBarLayout", "menuBarLayoutOverrides", "menuBarLayoutConditionals")
OTHER_ID = "12345678-1234-4321-9876-123456789ABC"
OTHER_ID_2 = "ABCDEF01-1234-4321-9876-123456789ABC"
SENTINEL = "fixture-only-secret-\u2603-DO-NOT-PRINT"


def settings():
    return c.load_settings(MANIFEST)


def evaluate_rule(rule, metrics):
    """Model CodexBar's left-to-right clause fold, not Python precedence."""
    result = False
    for index, clause in enumerate(rule["clauses"]):
        predicate = clause["predicate"]
        value = metrics.get(predicate["metric"])
        matched = False
        if type(value) in (int, float) and math.isfinite(value):
            if predicate["comparison"] == "greaterThan":
                matched = value > predicate["threshold"]
            elif predicate["comparison"] == "lessThan":
                matched = value < predicate["threshold"]
            else:
                raise AssertionError("unsupported fixture comparison")
        if index == 0:
            result = matched
        elif clause["combinator"] == "and":
            result = result and matched
        elif clause["combinator"] == "or":
            result = result or matched
        else:
            raise AssertionError("unsupported fixture combinator")
    return result


def encode(value):
    # Deliberately independent from the helper's deterministic serializer.
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def key(family, generation):
    return family if generation == 1 else f"{family}V{generation}"


def icon_layout():
    return {"lines": [[{"icon": {}}]]}


def unmanaged_rule(rid=OTHER_ID):
    return {"id": rid, "name": "Local rule", "clauses": [{"predicate": {
        "metric": "sessionPace", "direction": "used", "comparison": "lessThan", "threshold": 1}}],
        "thenToken": {"text": {"value": "local"}}, "elseToken": {"hidden": {}},
        "futureExtension": {"preserve": True}}


def projected_layout(layout, generation):
    """Independent oracle for the approved restricted native token vocabulary."""
    out = deepcopy(layout)
    if generation == 1:
        out["lines"] = [[token for token in row if "conditional" not in token]
                        for row in out["lines"]]
        out["lines"] = [row for row in out["lines"] if row]
        if not out["lines"]:
            out = {"lines": [[{"icon": {}}, {"percent": {"window": "automatic"}}]]}
    return out


def projected_rules(rules, generation):
    return deepcopy(rules if generation >= 3 else rules[2:] if generation == 2 else [])


def native_reconcile_maps(blobs, project):
    """Restricted upstream compatibility model, not just a persisted-byte check.

    Start at the newest generation. An existing older mirror owns membership;
    it removes absent entries and its edits override newer entries when their
    downgrade differs. Equivalent downgraded entries retain newer-only tokens.
    Absent older mirrors are materialized from effective state, not empty maps.
    This models the precedence that makes updating only V6/V7 insufficient.
    """
    effective = deepcopy(blobs[max(blobs)])
    for generation in sorted(blobs, reverse=True)[1:]:
        older = blobs[generation]
        effective = {pid: (effective[pid] if pid in effective and
                          project(effective[pid], generation) == value else deepcopy(value))
                     for pid, value in older.items()}
    return effective


class Manifest(unittest.TestCase):
    def test_exact_approved_preferences(self):
        true_keys = """statusChecksEnabled sessionQuotaNotificationsEnabled
            quotaWarningNotificationsEnabled predictivePaceWarningNotificationsEnabled
            quotaWarningSessionEnabled quotaWarningWeeklyEnabled quotaWarningSoundEnabled
            quotaWarningMarkersVisible paceVisible usageBarsShowUsed tokenCostUsageEnabled
            showOptionalCreditsAndExtraUsage refreshAllProvidersOnMenuOpen menuBarHidesCritters
            menuBarColorPace menuBarLayoutMonospacedDigits menuBarShowsBrandIconWithPercent""".split()
        false_keys = """quotaWarningOnScreenAlertEnabled resetTimesShowAbsolute
            costComparisonPeriodsEnabled hidePersonalInfo randomBlinkEnabled
            confettiOnSessionLimitResetsEnabled confettiOnWeeklyLimitResetsEnabled
            menuBarShowsHighestUsage providerChangelogLinksEnabled providersSortedAlphabetically
            mergeIcons mergeIconsStacked""".split()
        expected = dict.fromkeys(true_keys, True)
        expected.update(dict.fromkeys(false_keys, False))
        expected.update(refreshFrequency="adaptive", costSummaryDisplayStyle="both",
                        preferredCurrencyCode="USD", workdayTickAppearance="subtle",
                        weeklyProgressWorkDays=5)
        self.assertEqual(settings()["preferences"], expected)
        self.assertNotIn("costUsageEnabled", expected)

    def test_exact_approved_providers(self):
        self.assertEqual(settings()["providers"], {
            "codex": {"enabled": True, "cookieSource": "off"},
            "claude": {"enabled": True, "source": "cli"},
            "antigravity": {"enabled": True, "source": "oauth"},
            "muse": {"enabled": True, "cookieSource": "auto", "workspaceID": "1533933215445498"},
            "typesafe": {"enabled": True, "cookieSource": "auto", "accentColor": "#111111"},
        })

    def test_exact_layouts_and_resolved_references(self):
        layout = settings()["layout"]
        icon = {"icon": {}}
        percent = lambda window: {"percent": {"window": window}}
        conditional = lambda index: {"conditional": {"id": IDS[index - 1]}}
        self.assertEqual(layout["default"], {"lines": [[icon, percent("automatic")]]})
        baseline = {"lines": [
            [icon, percent("session"), conditional(3), conditional(1)],
            [percent("weekly"), conditional(4), conditional(2)]]}
        for pid in ("claude", "antigravity", "muse"):
            self.assertEqual(layout["overrides"][pid], baseline)
        self.assertEqual(layout["overrides"]["codex"], {"lines": [
            [icon, percent("weekly"), conditional(4), conditional(2)]]})
        self.assertEqual(layout["overrides"]["typesafe"], {"lines": [[icon, {"balance": {}}]]})
        refs = {token["conditional"]["id"] for value in layout["overrides"].values()
                for row in value["lines"] for token in row if "conditional" in token}
        self.assertEqual(refs, set(IDS))
        self.assertEqual({rule["id"] for rule in layout["conditionals"]}, refs)

    def test_exact_conditional_semantics(self):
        rules = settings()["layout"]["conditionals"]
        names = ("Session reset when over 70% used or pace is bad",
                 "Weekly reset when over 70% used or bad pace within 48h",
                 "Session pace when pace is bad", "Weekly pace when pace is bad and resets within 48h")
        for index, rule in enumerate(rules):
            window = "session" if index % 2 == 0 else "weekly"
            clauses = [{"predicate": {"metric": window + "Pace", "direction": "used",
                                      "comparison": "greaterThan", "threshold": 0}}]
            if window == "weekly":
                clauses.append({"combinator": "and", "predicate": {
                    "metric": "weeklyResetsIn", "direction": "used", "comparison": "lessThan", "threshold": 48}})
            if index < 2:
                clauses.append({"combinator": "or", "predicate": {
                    "metric": window, "direction": "used", "comparison": "greaterThan", "threshold": 70}})
            self.assertEqual(rule, {"id": IDS[index], "name": names[index], "clauses": clauses,
                                   "thenToken": {"windowResetCountdown" if index < 2 else "pace": {"window": window}},
                                   "elseToken": {"hidden": {}}})

    def test_reset_countdown_usage_threshold_bypasses_pace_and_distance(self):
        rules = settings()["layout"]["conditionals"]
        for window, index in (("session", 0), ("weekly", 1)):
            for used, expected in ((0, False), (70, False), (70.1, True), (71, True), (100, True)):
                for pace in (None, -1, 0, float("nan"), float("inf")):
                    for hours in (48, 72, 120, 168):
                        with self.subTest(window=window, used=used, pace=pace, hours=hours):
                            metrics = {window: used, window + "Pace": pace, "weeklyResetsIn": hours}
                            self.assertEqual(evaluate_rule(rules[index], metrics), expected)
                            # High usage must not change the separate pace token rules.
                            self.assertFalse(evaluate_rule(rules[index + 2], metrics))

    def test_reset_countdown_preserves_existing_bad_pace_paths(self):
        rules = settings()["layout"]["conditionals"]
        for used in (0, 70):
            with self.subTest(window="session", used=used):
                metrics = {"session": used, "sessionPace": 1}
                self.assertTrue(evaluate_rule(rules[0], metrics))
                self.assertTrue(evaluate_rule(rules[2], metrics))
            for hours, expected in ((47, True), (48, False), (72, False), (None, False)):
                with self.subTest(window="weekly", used=used, hours=hours):
                    metrics = {"weekly": used, "weeklyPace": 1, "weeklyResetsIn": hours}
                    self.assertEqual(evaluate_rule(rules[1], metrics), expected)
                    self.assertEqual(evaluate_rule(rules[3], metrics), expected)
        # Absent/nonfinite measurements are not zero or a satisfied predicate.
        for rule in rules:
            self.assertFalse(evaluate_rule(rule, {}))
        # The final OR must bypass a false time predicate even with positive pace.
        for hours in (48, 120, 168):
            self.assertTrue(evaluate_rule(rules[1], {
                "weekly": 100, "weeklyPace": 1, "weeklyResetsIn": hours}))

    def assert_invalid(self, document):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(document))
            with self.assertRaises(c.SettingsError) as raised:
                c.load_settings(path)
            self.assertNotIn(SENTINEL, str(raised.exception))

    def test_unknown_and_secret_fields_are_rejected_at_every_owned_level(self):
        for field in ("apiKey", "manualCookie", "tokenAccounts", "migrationFlags", "hiddenUsage",
                      "accountID", "deviceIdentifier", "launchAtLogin", "unknown"):
            for location in ((), ("codexbar",), ("codexbar", "preferences"),
                             ("codexbar", "layout"), ("codexbar", "layout", "default")):
                with self.subTest(field=field, location=location):
                    document = {"codexbar": settings()}
                    target = document
                    for part in location:
                        target = target[part]
                    target[field] = SENTINEL
                    self.assert_invalid(document)
            for pid in settings()["providers"]:
                with self.subTest(field=field, provider=pid):
                    document = {"codexbar": settings()}
                    document["codexbar"]["providers"][pid][field] = SENTINEL
                    self.assert_invalid(document)

    def test_strict_roots_required_sections_and_provider_ids(self):
        for value in (None, [], True, "settings", {}, {"codexbar": []}):
            with self.subTest(value=value):
                self.assert_invalid(value)
        for section in ("schemaVersion", "preferences", "providers", "layout"):
            document = {"codexbar": settings()}
            del document["codexbar"][section]
            self.assert_invalid(document)
        for version in (True, False, 0, 2, 1.0, "1", None):
            document = {"codexbar": settings()}
            document["codexbar"]["schemaVersion"] = version
            self.assert_invalid(document)
        for pid in ("openai", "museai", "unknown"):
            document = {"codexbar": settings()}
            document["codexbar"]["providers"][pid] = {"enabled": True}
            self.assert_invalid(document)
        document = {"codexbar": settings()}
        del document["codexbar"]["providers"]["codex"]
        self.assert_invalid(document)

    def test_preference_types_and_ranges(self):
        for field, invalid in {
            "statusChecksEnabled": (0, 1, "true", None, [], {}),
            "weeklyProgressWorkDays": (True, 0, 8, 5.0, "5", None),
            "refreshFrequency": (True, 1, "forever", [], {}),
            "costSummaryDisplayStyle": ("unsupported", 1),
            "preferredCurrencyCode": ("not-a-currency", None),
            "workdayTickAppearance": ("unsupported", False),
        }.items():
            for value in invalid:
                with self.subTest(field=field, value=value):
                    document = {"codexbar": settings()}
                    document["codexbar"]["preferences"][field] = value
                    self.assert_invalid(document)

    def test_provider_types_and_ranges(self):
        cases = {
            ("codex", "enabled"): (1, "true", None),
            ("codex", "cookieSource"): (True, [], {}, "manual", SENTINEL),
            ("claude", "source"): (True, [], {}, "auto", "oauth", SENTINEL),
            ("antigravity", "source"): (True, [], {}, "cli", SENTINEL),
            ("muse", "workspaceID"): (1533933215445498, "", "-1", "123x", "1" * 33, None),
            ("typesafe", "accentColor"): ("111111", "#123", "#GGGGGG", True, None),
        }
        for (pid, field), invalid in cases.items():
            for value in invalid:
                with self.subTest(provider=pid, field=field, value=value):
                    document = {"codexbar": settings()}
                    document["codexbar"]["providers"][pid][field] = value
                    self.assert_invalid(document)

    def test_layout_shapes_tokens_and_reference_validation(self):
        invalid_layouts = (None, [], {}, {"lines": []}, {"lines": [[]]},
                           {"lines": [[{"icon": {}}]] * 3}, {"lines": ["row"]},
                           {"lines": [[{"separator": {}}]]}, {"lines": [[{"icon": {"extra": 1}}]]},
                           {"lines": [[{"icon": {}, "balance": {}}]]},
                           {"lines": [[{"percent": {"window": "monthly"}}]]},
                           {"lines": [[{"conditional": {"id": OTHER_ID}}]]})
        for value in invalid_layouts:
            with self.subTest(value=value):
                document = {"codexbar": settings()}
                document["codexbar"]["layout"]["default"] = value
                self.assert_invalid(document)
        for section in ("default", "overrides", "conditionals"):
            document = {"codexbar": settings()}
            del document["codexbar"]["layout"][section]
            self.assert_invalid(document)
        document = {"codexbar": settings()}
        del document["codexbar"]["layout"]["overrides"]["codex"]
        self.assert_invalid(document)
        for mutate in (
            lambda rules: rules.pop(),
            lambda rules: rules.append(deepcopy(rules[0])),
            lambda rules: rules[0].update(id=OTHER_ID),
            lambda rules: rules[0].update(extra=SENTINEL),
            lambda rules: rules[0]["clauses"][0]["predicate"].update(threshold=True),
            lambda rules: rules[1]["clauses"][1]["predicate"].update(threshold=49),
            lambda rules: rules[0]["clauses"][-1]["predicate"].update(threshold=True),
            lambda rules: rules[1]["clauses"][-1]["predicate"].update(threshold=71),
            lambda rules: rules[0]["clauses"][-1]["predicate"].update(metric="sessionUsage"),
            lambda rules: rules[1]["clauses"][-1].update(combinator="and"),
            lambda rules: rules[0].update(elseToken={"text": {"value": SENTINEL}}),
        ):
            document = {"codexbar": settings()}
            mutate(document["codexbar"]["layout"]["conditionals"])
            self.assert_invalid(document)

    def test_duplicate_json_keys_nonfinite_and_malformed_manifest(self):
        for raw in (b"", b"not json", b"\xff", b'{"codexbar":{},"codexbar":{}}',
                    b'{"codexbar":NaN}', b'{"codexbar":Infinity}'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "manifest.json"
                path.write_bytes(raw)
                with self.assertRaises(c.SettingsError):
                    c.load_settings(path)

    def test_unreadable_manifest_has_safe_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(c.SettingsError, "read settings failed"):
                c.load_settings(Path(tmp) / "absent")


class Config(unittest.TestCase):
    def test_merge_preserves_local_secrets_extensions_order_and_input(self):
        live = {"version": 1, "rootExtension": {"token": SENTINEL}, "providers": [
            {"id": "unmanaged", "apiKey": SENTINEL, "enabled": False},
            {"id": "muse", "enabled": False, "workspaceID": "old", "manualCookie": SENTINEL,
             "tokenAccounts": [{"refreshToken": SENTINEL, "accountID": "local"}],
             "extension": {"nested": [SENTINEL]}},
            {"id": "codex", "cookieSource": "auto", "apiKey": SENTINEL},
        ]}
        before = deepcopy(live)
        providers = settings()["providers"]
        merged = c.merge_config(live, providers)
        self.assertEqual(live, before)
        self.assertEqual([entry["id"] for entry in merged["providers"]],
                         ["unmanaged", "muse", "codex", "claude", "antigravity", "typesafe"])
        self.assertEqual(merged["rootExtension"], before["rootExtension"])
        by_id = {entry["id"]: entry for entry in merged["providers"]}
        self.assertEqual(by_id["unmanaged"], before["providers"][0])
        for entry in before["providers"][1:]:
            for field, value in entry.items():
                if field not in providers[entry["id"]]:
                    self.assertEqual(by_id[entry["id"]][field], value)
        self.assertEqual(by_id["muse"]["manualCookie"].encode(), SENTINEL.encode())
        for pid, fields in providers.items():
            self.assertEqual({field: by_id[pid][field] for field in fields}, fields)
        self.assertEqual(c.merge_config(merged, providers), merged)
        merged["rootExtension"]["token"] = "changed"
        merged["providers"][1]["tokenAccounts"][0]["refreshToken"] = "changed"
        self.assertEqual(live, before)

    def test_invalid_config_structures_and_duplicate_ids(self):
        invalid = (None, [], {}, {"version": True, "providers": []},
                   {"version": 1.0, "providers": []}, {"version": 2, "providers": []},
                   {"version": 1}, {"version": 1, "providers": {}},
                   *({"version": 1, "providers": [entry]} for entry in (None, [], {}, {"id": ""}, {"id": 1})),
                   {"version": 1, "providers": [{"id": "codex"}, {"id": "codex"}]},
                   {"version": 1, "providers": [{"id": "extra"}, {"id": "extra"}]})
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(c.SettingsError):
                c.merge_config(value, settings()["providers"])

    def test_resolution_precedence_and_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            modern = home / ".config/codexbar/config.json"
            legacy = home / ".codexbar/config.json"
            self.assertEqual(c.resolve_config(home, {}), modern)
            legacy.parent.mkdir()
            legacy.write_text("fixture")
            self.assertEqual(c.resolve_config(home, {}), legacy)
            modern.parent.mkdir(parents=True)
            modern.write_text("fixture")
            self.assertEqual(c.resolve_config(home, {}), modern)
            for env, expected in (
                ({"CODEXBAR_CONFIG": "~/custom.json", "XDG_CONFIG_HOME": "/other"}, home / "custom.json"),
                ({"CODEXBAR_CONFIG": "relative.json"}, Path("relative.json")),
                ({"CODEXBAR_CONFIG": "  ~/custom.json  "}, home / "custom.json"),
                ({"CODEXBAR_CONFIG": "  ", "XDG_CONFIG_HOME": "  ~/xdg  "}, home / "xdg/codexbar/config.json"),
                ({"CODEXBAR_CONFIG": "", "XDG_CONFIG_HOME": str(home / "xdg")}, home / "xdg/codexbar/config.json"),
                ({"XDG_CONFIG_HOME": "~/xdg"}, home / "xdg/codexbar/config.json"),
                ({"XDG_CONFIG_HOME": "relative"}, modern),
                ({"XDG_CONFIG_HOME": ""}, modern),
            ):
                with self.subTest(env=env):
                    self.assertEqual(c.resolve_config(home, env), expected)

    def test_read_config_missing_valid_and_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            self.assertEqual(c._read_config(path), {"version": 1, "providers": []})
            value = {"version": 1, "providers": [{"id": "codex", "apiKey": SENTINEL}]}
            path.write_bytes(encode(value))
            self.assertEqual(c._read_config(path), value)
            for raw in (b"", b"{", b"[]", b"null", b"\xff", b'{"version":1,"version":1,"providers":[]}',
                        b'{"version":2,"providers":[]}', b'{"version":1,"providers":[],"extra":NaN}'):
                with self.subTest(raw=raw):
                    path.write_bytes(raw)
                    with self.assertRaises(c.SettingsError):
                        c._read_config(path)
                    self.assertEqual(path.read_bytes(), raw)

    def test_read_config_rejects_symlink_directory_and_hardlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.write_bytes(encode({"version": 1, "providers": []}))
            path = root / "config.json"
            path.symlink_to(target)
            with self.assertRaises(c.SettingsError):
                c._read_config(path)
            path.unlink()
            path.mkdir()
            with self.assertRaises(c.SettingsError):
                c._read_config(path)
            path.rmdir()
            os.link(target, path)
            with self.assertRaises(c.SettingsError):
                c._read_config(path)

    def test_atomic_private_publish_creates_only_config_and_permanent_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private/nested/config.json"
            real_replace = os.replace
            observations = []

            def replace(source, destination):
                source = Path(source)
                observations.append(source)
                self.assertEqual(source.parent, path.parent)
                self.assertEqual(destination, path)
                self.assertEqual(stat.S_IMODE(source.stat().st_mode), 0o600)
                self.assertFalse(path.exists())
                real_replace(source, destination)

            with patch.object(c.os, "replace", side_effect=replace):
                c._write_config(path, settings()["providers"])
            self.assertEqual(len(observations), 1)
            for directory in (path.parent, path.parent.parent):
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            lock = path.with_name("config.json.lock")
            self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o600)
            inode = lock.stat().st_ino
            before = path.read_bytes()
            with patch.object(c.os, "replace") as replace:
                c._write_config(path, settings()["providers"])
                replace.assert_not_called()
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(lock.stat().st_ino, inode)
            self.assertEqual({p.name for p in path.parent.iterdir()}, {"config.json", "config.json.lock"})

    def test_writer_rereads_after_lock_and_preserves_app_flush(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_bytes(encode({"version": 1, "providers": []}))
            real_flock = c.fcntl.flock
            flushed = {"version": 1, "flushExtension": SENTINEL, "providers": [
                {"id": "claude", "manualCookie": SENTINEL}]}

            def flock(fd, operation):
                real_flock(fd, operation)
                path.write_bytes(encode(flushed))

            with patch.object(c.fcntl, "flock", side_effect=flock):
                c._write_config(path, settings()["providers"])
            self.assertEqual(c._read_config(path), c.merge_config(flushed, settings()["providers"]))

    def test_symlink_lock_rejected_without_touching_target_or_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            original = encode({"version": 1, "providers": []})
            path.write_bytes(original)
            target = Path(tmp) / "target"
            target.write_text(SENTINEL)
            path.with_name("config.json.lock").symlink_to(target)
            with self.assertRaises(c.SettingsError):
                c._write_config(path, settings()["providers"])
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(target.read_text(), SENTINEL)

    def test_replace_failure_removes_temporary_keeps_original_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            original = encode({"version": 1, "providers": []})
            path.write_bytes(original)
            with patch.object(c.os, "replace", side_effect=OSError(SENTINEL)):
                with self.assertRaises(c.SettingsError) as raised:
                    c._write_config(path, settings()["providers"])
            self.assertNotIn(SENTINEL, str(raised.exception))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual({p.name for p in path.parent.iterdir()}, {"config.json", "config.json.lock"})
            # A second independently opened descriptor can take the permanent lock.
            with path.with_name("config.json.lock").open("rb") as stream:
                c.fcntl.flock(stream.fileno(), c.fcntl.LOCK_EX | c.fcntl.LOCK_NB)

    def test_lock_wait_is_bounded_without_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            with patch.object(c.fcntl, "flock", side_effect=BlockingIOError), \
                    patch.object(c.time, "monotonic", side_effect=[0, 11]), \
                    patch.object(c.time, "sleep"), patch.object(c.os, "replace") as replace:
                with self.assertRaisesRegex(c.SettingsError, "lock config failed"):
                    c._write_config(path, settings()["providers"])
                replace.assert_not_called()
            self.assertFalse(path.exists())


class Defaults(unittest.TestCase):
    def test_absent_domain_seeds_only_modern_v6_and_returns_changed_keys(self):
        desired = settings()
        live = {"localCookie": SENTINEL, "NSStatusItem Position": 17}
        before = deepcopy(live)
        changed = c.merge_defaults(live, desired)
        self.assertEqual(live, before)
        self.assertEqual(set(changed), set(desired["preferences"]) | {f + "V6" for f in FAMILIES})
        self.assertEqual(json.loads(changed[FAMILIES[0] + "V6"]), desired["layout"]["default"])
        self.assertEqual(json.loads(changed[FAMILIES[1] + "V6"]), desired["layout"]["overrides"])
        self.assertEqual(json.loads(changed[FAMILIES[2] + "V6"]), desired["layout"]["conditionals"])
        self.assertEqual(c.merge_defaults({**live, **changed}, desired), {})

    def test_independent_projections_for_every_existing_generation(self):
        desired = settings()
        rules = desired["layout"]["conditionals"]
        live = dict(desired["preferences"])
        unrelated = unmanaged_rule()
        for generation in range(1, 8):
            live[key(FAMILIES[0], generation)] = encode(icon_layout())
            live[key(FAMILIES[1], generation)] = encode({"local": icon_layout(), "codex": icon_layout()})
            stale = deepcopy(rules)
            for rule in stale:
                rule["name"] = "Stale managed rule"
            live[key(FAMILIES[2], generation)] = encode([unrelated, *stale])
        before = deepcopy(live)
        changed = c.merge_defaults(live, desired)
        self.assertEqual(live, before)
        self.assertEqual(set(changed), set(live) - set(desired["preferences"]))
        for generation in range(1, 8):
            with self.subTest(generation=generation):
                self.assertEqual(json.loads(changed[key(FAMILIES[0], generation)]), desired["layout"]["default"])
                overrides = json.loads(changed[key(FAMILIES[1], generation)])
                self.assertEqual(overrides.pop("local"), icon_layout())
                self.assertEqual(overrides, {pid: projected_layout(value, generation)
                                            for pid, value in desired["layout"]["overrides"].items()})
                self.assertEqual(json.loads(changed[key(FAMILIES[2], generation)]),
                                 [unrelated, *projected_rules(rules, generation)])
        self.assertEqual(c.merge_defaults({**live, **changed}, desired), {})

    def test_projection_functions_match_independent_oracle_and_do_not_alias(self):
        desired = settings()["layout"]
        before = deepcopy(desired)
        for generation in range(1, 8):
            for value in (desired["default"], *desired["overrides"].values()):
                self.assertEqual(c.project_layout(value, generation), projected_layout(value, generation))
            self.assertEqual(c.project_rules(desired["conditionals"], generation),
                             projected_rules(desired["conditionals"], generation))
        result = c.project_layout(desired["default"], 6)
        result["lines"][0][0]["icon"]["new"] = True
        result = c.project_rules(desired["conditionals"], 6)
        result[0]["clauses"].clear()
        self.assertEqual(desired, before)
        conditional_only = {"lines": [[{"conditional": {"id": IDS[0]}}]]}
        self.assertEqual(c.project_layout(conditional_only, 1), desired["default"])
        for invalid in (0, 8, True, "6", 6.0):
            for function, value in ((c.project_layout, desired["default"]),
                                    (c.project_rules, desired["conditionals"])):
                with self.subTest(generation=invalid, function=function.__name__), self.assertRaises(c.SettingsError):
                    function(value, invalid)

    def test_old_only_families_seed_v6_from_highest_preserving_unmanaged(self):
        desired = settings()
        older_rule, highest_rule = unmanaged_rule(), unmanaged_rule(OTHER_ID_2)
        live = {
            key(FAMILIES[1], 1): encode({"onlyOld": icon_layout()}),
            key(FAMILIES[1], 4): encode({"local": icon_layout(), "extension": icon_layout()}),
            key(FAMILIES[2], 2): encode([older_rule]),
            key(FAMILIES[2], 5): encode([highest_rule]),
        }
        changed = c.merge_defaults(live, desired)
        overrides = json.loads(changed[key(FAMILIES[1], 6)])
        self.assertEqual(overrides["local"], icon_layout())
        self.assertEqual(overrides["extension"], icon_layout())
        self.assertNotIn("onlyOld", overrides)
        self.assertEqual(json.loads(changed[key(FAMILIES[2], 6)]),
                         [highest_rule, *desired["layout"]["conditionals"]])
        self.assertEqual(json.loads(changed[key(FAMILIES[2], 2)]),
                         [older_rule, *desired["layout"]["conditionals"][2:]])
        for family in FAMILIES:
            for generation in (1, 2, 3, 4, 5, 7):
                if key(family, generation) not in live:
                    self.assertNotIn(key(family, generation), changed)

    def test_existing_v7_does_not_create_v6_or_missing_intermediates(self):
        desired = settings()
        exotic = {"lines": [[{"separator": {"style": "future"}}]], "futureMetadata": SENTINEL}
        local_rule = unmanaged_rule()
        live = {key(FAMILIES[0], 7): encode(icon_layout()),
                key(FAMILIES[1], 7): encode({"local": exotic}),
                key(FAMILIES[2], 7): encode([local_rule])}
        changed = c.merge_defaults(live, desired)
        self.assertEqual(set(changed) - set(desired["preferences"]), set(live))
        merged = {**live, **changed}
        self.assertEqual(json.loads(merged[key(FAMILIES[1], 7)])["local"], exotic)
        self.assertEqual(json.loads(merged[key(FAMILIES[2], 7)])[0], local_rule)

    def test_structurally_equivalent_json_bytes_remain_byte_identical(self):
        desired = settings()
        merged = c.merge_defaults({}, desired)
        for family in FAMILIES:
            field = family + "V6"
            merged[field] = json.dumps(json.loads(merged[field]), indent=3, sort_keys=False).encode()
        before = deepcopy(merged)
        self.assertEqual(c.merge_defaults(merged, desired), {})
        self.assertEqual(merged, before)

    def test_scalars_compare_types_not_python_numeric_equality(self):
        desired = settings()
        live = c.merge_defaults({}, desired)
        live.update(statusChecksEnabled=1, quotaWarningOnScreenAlertEnabled=0,
                    weeklyProgressWorkDays=5.0)
        changed = c.merge_defaults(live, desired)
        self.assertEqual(set(changed), {"statusChecksEnabled", "quotaWarningOnScreenAlertEnabled", "weeklyProgressWorkDays"})
        self.assertIs(changed["statusChecksEnabled"], True)
        self.assertIs(changed["quotaWarningOnScreenAlertEnabled"], False)
        self.assertIs(type(changed["weeklyProgressWorkDays"]), int)

    def test_pending_import_blocks_even_when_managed_state_is_converged(self):
        desired = settings()
        for value in (False, True, b"pending", SENTINEL):
            live = {**c.merge_defaults({}, desired), "portablePreferencesPendingImport": value}
            with self.subTest(value=value), self.assertRaisesRegex(c.SettingsError, "open CodexBar"):
                c.merge_defaults(live, desired)

    def test_future_generations_and_malformed_blobs_fail_closed(self):
        desired = settings()
        for family in FAMILIES:
            for generation in (0, 1, 8, 99):
                with self.subTest(family=family, generation=generation), self.assertRaises(c.SettingsError):
                    c.merge_defaults({family + "V" + str(generation): b"{}"}, desired)
            for raw in (None, {}, "{}", b"", b"{", b"\xff", b"null", b"true", b"NaN"):
                with self.subTest(family=family, raw=raw), self.assertRaises(c.SettingsError):
                    c.merge_defaults({family + "V6": raw}, desired)
        for family, values in (
            (FAMILIES[0], ([], {}, {"lines": ["bad"]}, {"lines": [[{}]]})),
            (FAMILIES[1], ([], {"local": {}}, {"local": {"lines": [[1]]}})),
            (FAMILIES[2], ({}, [None], [{"id": OTHER_ID}], [{**unmanaged_rule(), "clauses": []}])),
        ):
            for value in values:
                with self.subTest(family=family, value=value), self.assertRaises(c.SettingsError):
                    c.merge_defaults({family + "V6": encode(value)}, desired)

    def test_native_empty_layout_is_readable_and_utf16_is_not_json_data(self):
        changed = c.merge_defaults({FAMILIES[0] + "V6": encode({"lines": []})}, settings())
        self.assertEqual(json.loads(changed[FAMILIES[0] + "V6"]), settings()["layout"]["default"])
        for family, value in zip(FAMILIES, (icon_layout(), {}, [])):
            with self.subTest(family=family), self.assertRaises(c.SettingsError):
                c.merge_defaults({family + "V6": json.dumps(value).encode("utf-16")}, settings())

    def test_native_rule_clause_and_branch_shape_validation(self):
        for mutate in (
            lambda rule: rule.update(clauses=[None]),
            lambda rule: rule.update(clauses=[{"predicate": {}}]),
            lambda rule: rule["clauses"][0]["predicate"].update(threshold=True),
            lambda rule: rule["clauses"][0]["predicate"].update(metric=[]),
            lambda rule: rule["clauses"][0].update(combinator=1),
            lambda rule: rule.update(thenToken={}),
            lambda rule: rule.update(elseToken={"hidden": []}),
        ):
            rule = unmanaged_rule()
            mutate(rule)
            with self.subTest(rule=rule), self.assertRaises(c.SettingsError):
                c.merge_defaults({FAMILIES[2] + "V6": encode([rule])}, settings())
        bad_managed = settings()["layout"]["conditionals"]
        bad_managed[0]["thenToken"] = {"separator": {}}
        with self.assertRaises(c.SettingsError):
            c.project_rules(bad_managed, 6)

    def test_duplicate_json_and_case_insensitive_rule_ids_rejected(self):
        for raw in (b'{"lines":[],"lines":[[{"icon":{}}]]}',):
            with self.assertRaises(c.SettingsError):
                c.merge_defaults({FAMILIES[0] + "V6": raw}, settings())
        for rid in (OTHER_ID, OTHER_ID.lower()):
            rules = [unmanaged_rule(), unmanaged_rule(rid)]
            with self.assertRaises(c.SettingsError):
                c.merge_defaults({FAMILIES[2] + "V6": encode(rules)}, settings())
        for rid in ("not-a-uuid", "", 1):
            with self.assertRaises(c.SettingsError):
                c.merge_defaults({FAMILIES[2] + "V6": encode([unmanaged_rule(rid)])}, settings())

    def test_managed_rule_matching_is_uuid_based_preserves_unmanaged_order(self):
        desired = settings()
        stale = deepcopy(desired["layout"]["conditionals"][0])
        stale.update(id=stale["id"].lower(), name="stale")
        local_a, local_b = unmanaged_rule(), unmanaged_rule(OTHER_ID_2)
        live = {FAMILIES[2] + "V6": encode([local_a, stale, local_b])}
        result = json.loads(c.merge_defaults(live, desired)[FAMILIES[2] + "V6"])
        self.assertEqual(result[:3], [local_a, desired["layout"]["conditionals"][0], local_b])
        self.assertEqual(result[3:], desired["layout"]["conditionals"][1:])

    def test_native_older_override_precedence_regression(self):
        desired = settings()
        expected = desired["layout"]["overrides"]
        old = {"local": icon_layout(), **{pid: icon_layout() for pid in expected}}
        live = {key(FAMILIES[1], generation): encode(old) for generation in range(1, 8)}
        # The former V6/V7-only approach leaves older authoritative edits active.
        broken = {generation: deepcopy(old) for generation in range(1, 8)}
        broken[6] = broken[7] = {"local": icon_layout(), **deepcopy(expected)}
        self.assertNotEqual(native_reconcile_maps(broken, projected_layout)["codex"], expected["codex"])
        fixed = {**live, **c.merge_defaults(live, desired)}
        blobs = {generation: json.loads(fixed[key(FAMILIES[1], generation)]) for generation in range(1, 8)}
        effective = native_reconcile_maps(blobs, projected_layout)
        self.assertEqual(effective, {"local": icon_layout(), **expected})

    def test_native_missing_mirror_cannot_remove_unmanaged_entries(self):
        desired = settings()
        live = {FAMILIES[1] + "V7": encode({"local": icon_layout()}),
                FAMILIES[2] + "V7": encode([unmanaged_rule()])}
        fixed = {**live, **c.merge_defaults(live, desired)}
        overrides = json.loads(fixed[FAMILIES[1] + "V7"])
        rules = json.loads(fixed[FAMILIES[2] + "V7"])
        # Demonstrate why synthesized partial older maps are destructive.
        partial = {7: overrides, 1: {pid: projected_layout(value, 1)
                                     for pid, value in desired["layout"]["overrides"].items()}}
        self.assertNotIn("local", native_reconcile_maps(partial, projected_layout))
        self.assertIn("local", native_reconcile_maps({7: overrides}, projected_layout))
        self.assertNotIn(FAMILIES[1], fixed)
        self.assertNotIn(FAMILIES[2], fixed)
        self.assertEqual([rule["id"] for rule in rules], [OTHER_ID, *IDS])


class NativeBoundaries(unittest.TestCase):
    def test_read_defaults_plist_and_missing_domain(self):
        value = {"localSecret": SENTINEL, "blob": b"bytes", "flag": True}
        with patch.object(c, "_run", return_value=subprocess.CompletedProcess([], 0, plistlib.dumps(value), b"")) as run:
            self.assertEqual(c._read_defaults(), value)
            run.assert_called_once_with(["defaults", "export", c.DOMAIN, "-"])
        missing = subprocess.CompletedProcess([], 1, b"", f"Domain {c.DOMAIN} does not exist".encode())
        with patch.object(c, "_run", return_value=missing):
            self.assertEqual(c._read_defaults(), {})

    def test_read_defaults_errors_are_not_treated_as_empty_or_leaked(self):
        results = [subprocess.CompletedProcess([], 1, b"", SENTINEL.encode()),
                   subprocess.CompletedProcess([], 2, b"", f"{c.DOMAIN} does not exist {SENTINEL}".encode()),
                   subprocess.CompletedProcess([], 1, b"", b"other.domain does not exist"),
                   subprocess.CompletedProcess([], 0, SENTINEL.encode(), b""),
                   subprocess.CompletedProcess([], 0, plistlib.dumps([SENTINEL]), b"")]
        for result in results:
            with self.subTest(code=result.returncode), patch.object(c, "_run", return_value=result):
                with self.assertRaises(c.SettingsError) as raised:
                    c._read_defaults()
                self.assertNotIn(SENTINEL, str(raised.exception))

    def test_write_defaults_typed_individual_commands_and_error(self):
        values = {"bool": True, "false": False, "int": 5, "string": "USD", "data": b"\x00\xff"}
        with patch.object(c, "_run", return_value=subprocess.CompletedProcess([], 0, b"", b"")) as run:
            c._write_defaults(values)
            self.assertEqual([call.args[0] for call in run.call_args_list], [
                ["defaults", "write", c.DOMAIN, "bool", "-bool", "true"],
                ["defaults", "write", c.DOMAIN, "false", "-bool", "false"],
                ["defaults", "write", c.DOMAIN, "int", "-int", "5"],
                ["defaults", "write", c.DOMAIN, "string", "-string", "USD"],
                ["defaults", "write", c.DOMAIN, "data", "-data", "00ff"],
            ])
        with patch.object(c, "_run", return_value=subprocess.CompletedProcess([], 1, b"", SENTINEL.encode())):
            with self.assertRaisesRegex(c.SettingsError, "write defaults failed"):
                c._write_defaults({"bool": True})
        with patch.object(c, "_run") as run:
            with self.assertRaises(c.SettingsError):
                c._write_defaults({"unsupported": 1.5})
            run.assert_not_called()

    def test_process_lookup_is_current_user_and_handles_errors(self):
        for code, expected in ((0, True), (1, False), (2, None)):
            with patch.object(c, "_run", return_value=subprocess.CompletedProcess([], code, b"", SENTINEL.encode())) as run:
                if expected is None:
                    with self.assertRaises(c.SettingsError):
                        c._running()
                else:
                    self.assertIs(c._running(), expected)
                run.assert_called_once_with(["pgrep", "-u", str(os.getuid()), "-x", "CodexBar"])

    def test_quit_gracefully_waits_and_launch_reports_failure(self):
        with patch.object(c, "_run", return_value=subprocess.CompletedProcess([], 0, b"", b"")) as run, \
                patch.object(c, "_running", side_effect=[True, False]), patch.object(c.time, "sleep"):
            c._quit()
            run.assert_called_once_with(["osascript", "-e", 'tell application id "com.steipete.codexbar" to quit'])
        with patch.object(c, "_run", return_value=subprocess.CompletedProcess([], 1, b"", SENTINEL.encode())):
            with self.assertRaisesRegex(c.SettingsError, "quit failed"):
                c._quit()
            with self.assertRaisesRegex(c.SettingsError, "relaunch failed"):
                c._launch(Path("/fixture/CodexBar.app"))

    def test_run_wraps_native_errors_without_subprocess_output(self):
        for error in (OSError(SENTINEL), subprocess.TimeoutExpired([SENTINEL], 15),
                      subprocess.SubprocessError(SENTINEL)):
            with patch.object(c.subprocess, "run", side_effect=error):
                with self.assertRaisesRegex(c.SettingsError, "native command failed") as raised:
                    c._run(["fixture-command"])
                self.assertNotIn(SENTINEL, str(raised.exception))
        result = subprocess.CompletedProcess([], 0, b"fixture", b"")
        with patch.object(c.subprocess, "run", return_value=result) as run:
            self.assertIs(c._run(["fixture-command"]), result)
            run.assert_called_once_with(["fixture-command"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        timeout=15, check=False)


class FakeNative:
    """Small command simulator: plist state is memory-only, config is temporary."""
    def __init__(self):
        self.defaults = {"fixtureCookie": SENTINEL}
        self.running = False
        self.calls = []
        self.quit_code = 0
        self.quit_exits = True
        self.launch_code = 0
        self.launch_starts = True
        self.write_code = 0
        self.ignore_writes = False
        self.bad_readback = False
        self.did_write = False
        self.flush = None

    def run(self, args):
        self.calls.append(list(args))
        command = args[0]
        code, out, err = 0, b"", b""
        if args[:2] == ["defaults", "export"]:
            assert args == ["defaults", "export", c.DOMAIN, "-"]
            out = b"invalid plist" if self.bad_readback and self.did_write else plistlib.dumps(self.defaults)
        elif args[:2] == ["defaults", "write"]:
            assert args[2] == c.DOMAIN and len(args) == 6
            field, kind, value = args[3:]
            self.did_write = True
            code = self.write_code
            if not code and not self.ignore_writes:
                self.defaults[field] = {"-bool": lambda: value == "true", "-int": lambda: int(value),
                                        "-string": lambda: value, "-data": lambda: bytes.fromhex(value)}[kind]()
        elif command == "pgrep":
            assert args == ["pgrep", "-u", str(os.getuid()), "-x", "CodexBar"]
            code = 0 if self.running else 1
        elif command == "osascript":
            assert args == ["osascript", "-e", 'tell application id "com.steipete.codexbar" to quit']
            code = self.quit_code
            if not code and self.quit_exits:
                self.running = False
                if self.flush:
                    self.flush()
        elif command == "open":
            assert args[1] == "-a" and len(args) == 3
            code = self.launch_code
            if not code and self.launch_starts:
                self.running = True
        else:
            raise AssertionError(f"unexpected native command: {command}")
        if code not in (0, 1) or (code and command != "pgrep"):
            err = SENTINEL.encode()
        return subprocess.CompletedProcess(args, code, out, err)

    def commands(self, name):
        return [args for args in self.calls if args[0] == name]

    def writes(self):
        return [args for args in self.calls if args[:2] == ["defaults", "write"]]


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.app = self.home / "Applications/CodexBar.app"
        self.app.mkdir(parents=True)
        self.path = self.home / ".config/codexbar/config.json"
        self.native = FakeNative()
        real_is_dir = Path.is_dir

        def is_dir(path):
            # Never probe the installed /Applications/CodexBar.app.
            if path == Path("/Applications/CodexBar.app"):
                return False
            if path.is_relative_to(self.home):
                return real_is_dir(path)
            raise AssertionError("filesystem app lookup escaped fixture")

        self.enterContext(patch.object(Path, "is_dir", is_dir))
        self.enterContext(patch.object(Path, "home", return_value=self.home))
        self.enterContext(patch.object(c.sys, "platform", "darwin"))
        self.enterContext(patch.dict(os.environ, {"HOME": str(self.home)}, clear=True))
        self.enterContext(patch.object(c, "_run", side_effect=self.native.run))
        self.enterContext(patch.object(c.subprocess, "run", side_effect=AssertionError("real command forbidden")))
        self.enterContext(patch.object(c.time, "sleep"))
        # Deterministic bounded quit/startup waits, without wall-clock sleeps.
        self.ticks = iter(range(10000))
        self.enterContext(patch.object(c.time, "monotonic", side_effect=lambda: next(self.ticks)))

    def invoke(self, *, check=False):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = c.converge(MANIFEST, check=check)
        self.assertNotIn(SENTINEL, stdout.getvalue() + stderr.getvalue())
        return result, stdout.getvalue(), stderr.getvalue()

    def seed_config(self, value=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        value = value if value is not None else {"version": 1, "providers": []}
        self.path.write_bytes(encode(value))

    def seed_converged(self):
        self.seed_config(c.merge_config({"version": 1, "providers": []}, settings()["providers"]))
        self.native.defaults.update(c.merge_defaults(self.native.defaults, settings()))

    def assert_no_effects(self):
        self.assertFalse(self.native.commands("osascript"))
        self.assertFalse(self.native.commands("open"))
        self.assertFalse(self.native.writes())
        self.assertFalse(self.path.with_name("config.json.lock").exists())

    def test_missing_app_is_silent_and_never_reads_live_state(self):
        self.app.rmdir()
        self.assertEqual(self.invoke(), (0, "", ""))
        self.assertEqual(self.native.calls, [])
        self.assertFalse(self.path.parent.exists())

    def test_non_macos_rejected_without_native_io(self):
        with patch.object(c.sys, "platform", "linux"):
            self.assertEqual(self.invoke(), (2, "", "codexbar: macOS required\n"))
        self.assertEqual(self.native.calls, [])

    def test_no_drift_is_silent_zero_effect_even_when_running(self):
        self.seed_converged()
        self.native.running = True
        original = self.path.read_bytes()
        self.path.chmod(0o640)
        self.assertEqual(self.invoke(), (0, "", ""))
        self.assertEqual(self.invoke(check=True), (0, "", ""))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o640)
        self.assert_no_effects()
        self.assertFalse(self.native.commands("pgrep"))

    def test_check_drift_does_not_create_parents_locks_or_restart(self):
        self.native.running = True
        self.assertEqual(self.invoke(check=True), (1, "codexbar: managed settings differ\n", ""))
        self.assert_no_effects()
        self.assertFalse(self.path.parent.exists())
        self.assertFalse(self.native.commands("pgrep"))

    def test_check_errors_no_effects_and_no_secret_diagnostics(self):
        self.seed_config()
        self.path.write_text(SENTINEL)
        code, stdout, stderr = self.invoke(check=True)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("codexbar:", stderr)
        self.assert_no_effects()
        self.assertEqual(self.path.read_text(), SENTINEL)

    def test_invalid_defaults_block_both_writes_before_quit(self):
        for invalid in ({"menuBarLayoutV8": encode(icon_layout())},
                        {"menuBarLayoutV6": b"bad-json"},
                        {"portablePreferencesPendingImport": SENTINEL}):
            with self.subTest(invalid=tuple(invalid)):
                self.native.defaults = invalid
                self.native.running = True
                code, stdout, stderr = self.invoke()
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertTrue(stderr.startswith("codexbar:"))
                self.assert_no_effects()
                self.assertFalse(self.path.exists())

    def test_stopped_app_drift_writes_without_launch_and_second_run_silent(self):
        self.assertEqual(self.invoke(), (0, "==> CodexBar managed settings\n", ""))
        self.assertFalse(self.native.commands("osascript"))
        self.assertFalse(self.native.commands("open"))
        self.assertTrue(self.native.writes())
        self.assertEqual(c.merge_defaults(self.native.defaults, settings()), {})
        self.assertEqual(c._read_config(self.path), c.merge_config({"version": 1, "providers": []}, settings()["providers"]))
        self.assertEqual(self.native.defaults["fixtureCookie"], SENTINEL)
        self.native.calls.clear()
        before = self.path.read_bytes()
        self.assertEqual(self.invoke(), (0, "", ""))
        self.assertFalse(self.native.writes())
        self.assertFalse(self.native.commands("pgrep"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_running_app_drift_gracefully_restarts_once_and_is_idempotent(self):
        self.native.running = True
        self.assertEqual(self.invoke(), (0, "==> CodexBar managed settings\n", ""))
        self.assertEqual(len(self.native.commands("osascript")), 1)
        self.assertEqual(self.native.commands("open"), [["open", "-a", str(self.app)]])
        commands = [args[0] for args in self.native.calls]
        self.assertLess(commands.index("osascript"), commands.index("open"))
        self.assertTrue(self.native.running)
        self.native.calls.clear()
        self.assertEqual(self.invoke(), (0, "", ""))
        self.assertFalse(self.native.writes())
        self.assertFalse(self.native.commands("osascript"))
        self.assertFalse(self.native.commands("open"))

    def test_app_flush_is_reread_before_merging_both_stores(self):
        self.native.running = True
        flushed_config = {"version": 1, "flushExtension": SENTINEL, "providers": [
            {"id": "claude", "enabled": False, "manualCookie": SENTINEL},
            {"id": "local", "apiKey": SENTINEL}]}

        def flush():
            self.seed_config(flushed_config)
            self.native.defaults.update({"flushedSecret": SENTINEL,
                                         FAMILIES[1] + "V7": encode({"local": icon_layout()})})

        self.native.flush = flush
        self.assertEqual(self.invoke(), (0, "==> CodexBar managed settings\n", ""))
        self.assertEqual(c._read_config(self.path), c.merge_config(flushed_config, settings()["providers"]))
        self.assertEqual(self.native.defaults["flushedSecret"], SENTINEL)
        self.assertEqual(json.loads(self.native.defaults[FAMILIES[1] + "V7"])["local"], icon_layout())
        self.assertNotIn(FAMILIES[1] + "V6", self.native.defaults)

    def test_post_quit_invalid_flush_blocks_writes_but_relaunches(self):
        self.native.running = True
        self.native.flush = lambda: self.native.defaults.update({"portablePreferencesPendingImport": SENTINEL})
        code, _, stderr = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn("open CodexBar", stderr)
        self.assertFalse(self.native.writes())
        self.assertFalse(self.path.exists())
        self.assertEqual(len(self.native.commands("open")), 1)

    def test_quit_timeout_does_not_write_force_kill_or_open_second_app(self):
        self.native.running = True
        self.native.quit_exits = False
        code, stdout, stderr = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "==> CodexBar managed settings\n")
        self.assertIn("quit timeout failed", stderr)
        self.assertFalse(self.native.writes())
        self.assertFalse(self.native.commands("open"))
        self.assertFalse(self.path.exists())
        self.assertFalse(self.path.with_name("config.json.lock").exists())
        self.assertEqual({args[0] for args in self.native.calls}, {"defaults", "pgrep", "osascript"})

    def test_failed_quit_stops_without_writes(self):
        self.native.running = True
        self.native.quit_code = 1
        code, _, stderr = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn("quit failed", stderr)
        self.assertFalse(self.native.writes())
        self.assertFalse(self.native.commands("open"))
        self.assertFalse(self.path.exists())

    def test_config_write_failure_propagates_and_relaunches_only_initially_running(self):
        for running in (True, False):
            with self.subTest(running=running):
                self.native = FakeNative()
                # The _run patch binds the original object; update its side effect.
                with patch.object(c, "_run", side_effect=self.native.run), \
                        patch.object(c, "_write_config", side_effect=c.SettingsError("write config failed")):
                    self.native.running = running
                    code, _, stderr = self.invoke()
                self.assertEqual(code, 2)
                self.assertIn("write config failed", stderr)
                self.assertEqual(len(self.native.commands("open")), int(running))
                self.assertFalse(self.native.writes())

    def test_defaults_write_failure_propagates_and_relaunches(self):
        self.native.running = True
        self.native.write_code = 1
        code, _, stderr = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn("write defaults failed", stderr)
        self.assertEqual(len(self.native.commands("open")), 1)
        self.assertEqual(len(self.native.writes()), 1)

    def test_failed_launch_propagates(self):
        self.native.running = True
        self.native.launch_code = 1
        code, _, stderr = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn("relaunch failed", stderr)
        self.assertEqual(len(self.native.commands("open")), 1)

    def test_successful_open_without_running_app_fails_bounded_readback(self):
        self.native.running = True
        self.native.launch_starts = False
        code, _, stderr = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn("verify managed settings failed", stderr)
        self.assertEqual(len(self.native.commands("open")), 1)
        self.assertLess(len(self.native.commands("pgrep")), 30)

    def test_readback_parse_failure_propagates_after_relaunch(self):
        self.native.running = True
        self.native.bad_readback = True
        code, _, stderr = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn("parse defaults failed", stderr)
        self.assertEqual(len(self.native.commands("open")), 1)

    def test_readback_unapplied_writes_fail_for_running_and_stopped_apps(self):
        for running in (False, True):
            with self.subTest(running=running):
                native = FakeNative()
                native.running = running
                native.ignore_writes = True
                with patch.object(c, "_run", side_effect=native.run):
                    code, _, stderr = self.invoke()
                self.assertEqual(code, 2)
                self.assertIn("verify managed settings failed", stderr)
                self.assertEqual(len(native.commands("open")), int(running))

    def test_cli_delegates_settings_and_check(self):
        with patch.object(c, "converge", return_value=1) as converge:
            self.assertEqual(c.main(["--settings", str(MANIFEST), "--check"]), 1)
            converge.assert_called_once_with(MANIFEST, check=True)


if __name__ == "__main__":
    unittest.main()
