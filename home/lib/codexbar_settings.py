"""Partially own CodexBar settings without exporting or syncing credentials.

Only the manifest is portable. Live config/defaults are read in memory and never
included in diagnostics. Importing this module performs no platform I/O.
"""

import argparse
from copy import deepcopy
import fcntl
import json
import math
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
import sys
import tempfile
import time
from typing import Mapping
import uuid
from xml.parsers.expat import ExpatError


DOMAIN = "com.steipete.codexbar"
PROVIDERS = ("codex", "claude", "antigravity", "muse", "typesafe")
RULE_IDS = tuple(f"7F3A2C10-5E5B-4C1E-9A11-5E55105E000{i}" for i in range(1, 5))
BOOL_KEYS = frozenset("""
statusChecksEnabled sessionQuotaNotificationsEnabled quotaWarningNotificationsEnabled
predictivePaceWarningNotificationsEnabled quotaWarningSessionEnabled quotaWarningWeeklyEnabled
quotaWarningSoundEnabled quotaWarningMarkersVisible paceVisible usageBarsShowUsed tokenCostUsageEnabled
showOptionalCreditsAndExtraUsage refreshAllProvidersOnMenuOpen menuBarHidesCritters menuBarColorPace
menuBarLayoutMonospacedDigits menuBarShowsBrandIconWithPercent quotaWarningOnScreenAlertEnabled
resetTimesShowAbsolute costComparisonPeriodsEnabled hidePersonalInfo randomBlinkEnabled
confettiOnSessionLimitResetsEnabled confettiOnWeeklyLimitResetsEnabled menuBarShowsHighestUsage
providerChangelogLinksEnabled providersSortedAlphabetically mergeIcons mergeIconsStacked
""".split())
STRING_VALUES = {
    "refreshFrequency": {"adaptive"},
    "costSummaryDisplayStyle": {"both"},
    "preferredCurrencyCode": {"USD"},
    "workdayTickAppearance": {"subtle"},
}
FAMILIES = ("menuBarLayout", "menuBarLayoutOverrides", "menuBarLayoutConditionals")


class SettingsError(Exception):
    """Safe diagnostic; never wrap native errors or live values in its message."""


def _invalid(field):
    raise SettingsError(f"invalid field {field}")


def _keys(value, allowed, field, *, exact=False):
    if not isinstance(value, dict) or set(value) - set(allowed) or (exact and set(value) != set(allowed)):
        _invalid(field)


def _json(raw, field):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _invalid(field)
            result[key] = value
        return result

    def number(text):
        value = float(text)
        if not math.isfinite(value):
            _invalid(field)
        return value

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_float=number,
                          parse_constant=lambda _: _invalid(field))
    except (ValueError, UnicodeError, TypeError):
        _invalid(field)


def _equal(a, b):
    """JSON equality, including bool/int distinctions Python normally ignores."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    return a == b


def _managed_layout(value, field):
    _keys(value, {"lines"}, field, exact=True)
    lines = value["lines"]
    if not isinstance(lines, list) or not 1 <= len(lines) <= 2:
        _invalid(field)
    for row in lines:
        if not isinstance(row, list) or not row:
            _invalid(field)
        for token in row:
            valid = any(_equal(token, {key: {}}) for key in ("icon", "balance"))
            valid |= any(_equal(token, {"percent": {"window": window}})
                         for window in ("automatic", "session", "weekly"))
            valid |= any(_equal(token, {"conditional": {"id": rid}}) for rid in RULE_IDS)
            if not valid:
                _invalid(field)


def load_settings(path: Path) -> dict:
    try:
        document = _json(path.read_bytes(), "settings")
    except OSError:
        raise SettingsError("read settings failed") from None
    _keys(document, {"codexbar"}, "settings", exact=True)
    settings = document["codexbar"]
    _keys(settings, {"schemaVersion", "preferences", "layout", "providers"}, "codexbar", exact=True)
    if type(settings["schemaVersion"]) is not int or settings["schemaVersion"] != 1:
        _invalid("schemaVersion")
    prefs = settings["preferences"]
    _keys(prefs, BOOL_KEYS | STRING_VALUES.keys() | {"weeklyProgressWorkDays"}, "preferences")
    for key, value in prefs.items():
        if key in BOOL_KEYS:
            valid = type(value) is bool
        elif key == "weeklyProgressWorkDays":
            valid = type(value) is int and 1 <= value <= 7
        else:
            valid = type(value) is str and value in STRING_VALUES[key]
        if not valid:
            _invalid(f"preferences.{key}")
    providers = settings["providers"]
    _keys(providers, PROVIDERS, "providers", exact=True)
    fields = {
        "codex": {"enabled", "cookieSource"}, "claude": {"enabled", "source"},
        "antigravity": {"enabled", "source"},
        "muse": {"enabled", "cookieSource", "workspaceID"},
        "typesafe": {"enabled", "cookieSource", "accentColor"},
    }
    sources = {"claude": "cli", "antigravity": "oauth"}
    for pid, entry in providers.items():
        _keys(entry, fields[pid], f"providers.{pid}")
        for key, value in entry.items():
            valid = {
                "enabled": lambda: type(value) is bool,
                "cookieSource": lambda: type(value) is str and value in {"off", "auto"},
                "source": lambda: value == sources[pid],
                "workspaceID": lambda: type(value) is str and bool(re.fullmatch(r"[0-9]{1,32}", value)),
                "accentColor": lambda: type(value) is str and bool(re.fullmatch(r"#[0-9a-fA-F]{6}", value)),
            }[key]()
            if not valid:
                _invalid(f"providers.{pid}.{key}")
    layout = settings["layout"]
    _keys(layout, {"default", "overrides", "conditionals"}, "layout", exact=True)
    _managed_layout(layout["default"], "layout.default")
    _keys(layout["overrides"], PROVIDERS, "layout.overrides", exact=True)
    for pid, value in layout["overrides"].items():
        _managed_layout(value, f"layout.overrides.{pid}")
    _managed_rules(layout["conditionals"])
    return settings


def _managed_rules(rules):
    if not isinstance(rules, list) or len(rules) != 4:
        _invalid("layout.conditionals")
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
            # CodexBar folds left-to-right: (pace AND reset) OR high usage.
            clauses.append({"combinator": "or", "predicate": {
                "metric": window, "direction": "used", "comparison": "greaterThan", "threshold": 70}})
        expected = {"id": RULE_IDS[index], "name": names[index], "clauses": clauses,
                    "thenToken": {"windowResetCountdown" if index < 2 else "pace": {"window": window}},
                    "elseToken": {"hidden": {}}}
        if not _equal(rule, expected):
            _invalid("layout.conditionals")


def resolve_config(home: Path, env: Mapping[str, str]) -> Path:
    def expand(value):
        if value == "~" or value.startswith("~/"):
            return str(home) + value[1:]
        return os.path.expanduser(value)

    override = env.get("CODEXBAR_CONFIG", "").strip()
    if override:
        return Path(expand(override))
    xdg_home = env.get("XDG_CONFIG_HOME", "").strip()
    if xdg_home:
        xdg = Path(expand(xdg_home))
        if xdg.is_absolute():
            return xdg / "codexbar/config.json"
    modern = home / ".config/codexbar/config.json"
    legacy = home / ".codexbar/config.json"
    return modern if modern.exists() or not legacy.exists() else legacy


def merge_config(live: dict, providers: dict) -> dict:
    if not isinstance(live, dict) or type(live.get("version")) is not int or live["version"] != 1:
        _invalid("config.version")
    entries = live.get("providers")
    if not isinstance(entries, list):
        _invalid("config.providers")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
            _invalid("config.providers.id")
        if entry["id"] in seen:
            _invalid("config.providers.id")
        seen.add(entry["id"])
    merged = deepcopy(live)
    by_id = {entry["id"]: entry for entry in merged["providers"]}
    for pid, fields in providers.items():
        if pid not in by_id:
            by_id[pid] = {"id": pid}
            merged["providers"].append(by_id[pid])
        by_id[pid].update(deepcopy(fields))
    return merged


def _generation(generation):
    if type(generation) is not int or not 1 <= generation <= 7:
        _invalid("layout.generation")


def project_layout(layout: dict, generation: int) -> dict:
    """The managed subset of MenuBarLayout.swift's compatibility projections.

    V1 cannot decode conditional references; V2–V7 can decode every token in
    these layouts. Never use this to down-convert unrelated native layouts.
    """
    _generation(generation)
    _managed_layout(layout, "layout")
    result = deepcopy(layout)
    if generation == 1:
        result["lines"] = [[token for token in row if "conditional" not in token] for row in result["lines"]]
        result["lines"] = [row for row in result["lines"] if row]
        if not result["lines"]:
            result["lines"] = [[{"icon": {}}, {"percent": {"window": "automatic"}}]]
    return result


def project_rules(rules: list, generation: int) -> list:
    # Native legacyCompatible rejects pace predicates. releasedCompatible (V2)
    # accepts those predicates but rejects explicit window-reset branch tokens.
    # v3Compatible and all later projections retain this entire managed suite.
    _generation(generation)
    _managed_rules(rules)
    return deepcopy([r for r in rules if generation >= 3 or (generation == 2 and r["id"] in RULE_IDS[2:])])


def _live_layout(value, field):
    # Validate structure, not the unmanaged token vocabulary: newer native tokens
    # in existing V7 data must not be interpreted or projected by this helper.
    if not isinstance(value, dict) or not isinstance(value.get("lines"), list):
        _invalid(field)
    for row in value["lines"]:
        if not isinstance(row, list) or any(not isinstance(t, dict) or len(t) != 1
                                          or not isinstance(next(iter(t.values())), dict) for t in row):
            _invalid(field)


def _rule_id(rule, field):
    try:
        if not isinstance(rule, dict) or not isinstance(rule.get("id"), str):
            _invalid(field)
        return str(uuid.UUID(rule["id"])).upper()
    except ValueError:
        _invalid(field)


def _decode_blob(raw, family):
    if not isinstance(raw, bytes):
        _invalid(family)
    try:
        value = _json(raw.decode("utf-8"), family)
    except UnicodeError:
        _invalid(family)
    if family == FAMILIES[0]:
        _live_layout(value, family)
    elif family == FAMILIES[1]:
        if not isinstance(value, dict):
            _invalid(family)
        for entry in value.values():
            _live_layout(entry, family)
    else:
        if not isinstance(value, list):
            _invalid(family)
        seen = set()
        for rule in value:
            rid = _rule_id(rule, family)
            if rid in seen:
                _invalid(family)
            seen.add(rid)
            if (not isinstance(rule.get("clauses"), list) or not rule["clauses"]
                    or ("name" in rule and not isinstance(rule["name"], str))):
                _invalid(family)
            for branch in ("thenToken", "elseToken"):
                token = rule.get(branch)
                if (not isinstance(token, dict) or len(token) != 1
                        or not isinstance(next(iter(token.values())), dict)):
                    _invalid(family)
            for clause in rule["clauses"]:
                if not isinstance(clause, dict) or not isinstance(clause.get("predicate"), dict):
                    _invalid(family)
                predicate = clause["predicate"]
                if (not isinstance(predicate.get("metric"), str)
                        or not isinstance(predicate.get("comparison"), str)
                        or type(predicate.get("threshold")) not in (int, float)
                        or ("direction" in predicate and not isinstance(predicate["direction"], str))
                        or ("combinator" in clause and not isinstance(clause["combinator"], str))):
                    _invalid(family)
    return value


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def merge_defaults(live: dict, settings: dict) -> dict:
    if "portablePreferencesPendingImport" in live:
        raise SettingsError("open CodexBar to finish the pending import before reapplying")
    changed = {key: deepcopy(value) for key, value in settings["preferences"].items()
               if key not in live or not _equal(live[key], value)}
    layout = settings["layout"]
    for family in FAMILIES:
        existing = {}
        for key in live:
            if key == family:
                generation = 1
            elif key.startswith(family) and re.fullmatch(r"V[0-9]+", key[len(family):]):
                generation = int(key[len(family) + 1:])
                if not 2 <= generation <= 7 or key != family + f"V{generation}":
                    _invalid(family + ".generation")
            else:
                continue
            existing[generation] = (key, _decode_blob(live[key], family))
        targets = dict(existing)
        if 6 not in existing and 7 not in existing:
            seed = deepcopy(existing[max(existing)][1]) if existing else (
                layout["default"] if family == FAMILIES[0] else {} if family == FAMILIES[1] else [])
            targets[6] = (family + "V6", seed)
        for generation, (key, old) in targets.items():
            if family == FAMILIES[0]:
                new = project_layout(layout["default"], generation)
            elif family == FAMILIES[1]:
                new = deepcopy(old)
                new.update({pid: project_layout(value, generation) for pid, value in layout["overrides"].items()})
            else:
                replacements = {r["id"]: r for r in project_rules(layout["conditionals"], generation)}
                new = []
                for rule in old:
                    rid = _rule_id(rule, family)
                    if rid in RULE_IDS:
                        if rid in replacements:
                            new.append(deepcopy(replacements.pop(rid)))
                    else:
                        new.append(deepcopy(rule))
                new.extend(deepcopy(list(replacements.values())))
            if generation not in existing or not _equal(old, new):
                changed[key] = _encode(new)
    return changed


def _run(args):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        raise SettingsError("native command failed") from None


def _read_defaults():
    result = _run(["defaults", "export", DOMAIN, "-"])
    if result.returncode:
        # Only the documented missing-domain diagnostic is an empty domain.
        # Never print stderr: other failures may include preference values.
        if result.returncode == 1 and b"does not exist" in result.stderr and DOMAIN.encode() in result.stderr:
            return {}
        raise SettingsError("read defaults failed")
    try:
        value = plistlib.loads(result.stdout)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, TypeError, plistlib.InvalidFileException, OverflowError, ExpatError):
        raise SettingsError("parse defaults failed") from None


def _private_regular(fd):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
        raise SettingsError("unsafe config file failed")


def _read_config(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {"version": 1, "providers": []}
    except OSError:
        raise SettingsError("read config failed") from None
    try:
        _private_regular(fd)
        with os.fdopen(fd, "rb", closefd=False) as stream:
            value = _json(stream.read(), "config")
        merge_config(value, {})  # validate even when there are no managed entries
        return value
    finally:
        os.close(fd)


def _write_config(path, providers):
    """Keep CodexBar's permanent lock inode and re-read after acquiring it."""
    fd = None
    temporary = None
    try:
        missing = []
        parent = path.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for directory in reversed(missing):
            directory.mkdir(mode=0o700)
        lock = path.with_name(path.name + ".lock")
        fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        _private_regular(fd)
        # Bounded lock acquisition: a stalled app must not hang chezmoi forever.
        deadline = time.monotonic() + 10
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SettingsError("lock config failed")
                time.sleep(0.1)
        live = _read_config(path)
        merged = merge_config(live, providers)
        if _equal(live, merged):
            return
        tmpfd, temporary = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=path.parent)
        with os.fdopen(tmpfd, "wb") as stream:
            stream.write(_encode(merged) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError:
        raise SettingsError("write config failed") from None
    finally:
        if temporary is not None:
            os.unlink(temporary)
        if fd is not None:
            os.close(fd)


def _write_defaults(changed):
    for key, value in changed.items():
        if type(value) is bool:
            kind, text = "-bool", "true" if value else "false"
        elif type(value) is int:
            kind, text = "-int", str(value)
        elif isinstance(value, bytes):
            kind, text = "-data", value.hex()
        elif isinstance(value, str):
            kind, text = "-string", value
        else:
            raise SettingsError("write defaults failed")
        if _run(["defaults", "write", DOMAIN, key, kind, text]).returncode:
            raise SettingsError("write defaults failed")


def _running():
    result = _run(["pgrep", "-u", str(os.getuid()), "-x", "CodexBar"])
    if result.returncode not in (0, 1):
        raise SettingsError("process lookup failed")
    return result.returncode == 0


def _quit():
    if _run(["osascript", "-e", 'tell application id "com.steipete.codexbar" to quit']).returncode:
        raise SettingsError("quit failed")
    deadline = time.monotonic() + 10
    while _running():
        if time.monotonic() >= deadline:
            raise SettingsError("quit timeout failed")
        time.sleep(0.1)


def _launch(app):
    if _run(["open", "-a", str(app)]).returncode:
        raise SettingsError("relaunch failed")


def _diff(path, settings):
    config = _read_config(path)
    defaults = merge_defaults(_read_defaults(), settings)
    return not _equal(config, merge_config(config, settings["providers"])), defaults


def _verify(path, settings, *, relaunched):
    deadline = time.monotonic() + (10 if relaunched else 0)
    while True:
        if (not relaunched or _running()) and not any(_diff(path, settings)):
            return
        if time.monotonic() >= deadline:
            raise SettingsError("verify managed settings failed")
        time.sleep(0.2)


def converge(settings_path: Path, *, check: bool = False) -> int:
    try:
        settings = load_settings(settings_path)
        if sys.platform != "darwin":
            raise SettingsError("macOS required")
        home = Path.home()
        app = next((p for p in (Path("/Applications/CodexBar.app"), home / "Applications/CodexBar.app")
                    if p.is_dir()), None)
        if app is None:
            return 0
        path = resolve_config(home, os.environ)
        config_changed, defaults = _diff(path, settings)
        if not config_changed and not defaults:
            return 0
        if check:
            print("codexbar: managed settings differ")
            return 1
        print("==> CodexBar managed settings")
        running = _running()
        quit_attempted = False
        quit_completed = False
        try:
            if running:
                quit_attempted = True
                _quit()
                quit_completed = True
            # CodexBar flushes preferences/config on exit. Validate both again
            # before either write, then re-read config once more under its lock.
            config_changed, defaults = _diff(path, settings)
            if config_changed:
                _write_config(path, settings["providers"])
            _write_defaults(defaults)
        finally:
            # A quit error/timeout may leave it running: do not open another app
            # in that case. A failure after exit must still attempt the relaunch.
            if running and quit_attempted and (quit_completed or not _running()):
                _launch(app)
        _verify(path, settings, relaunched=running)
        return 0
    except SettingsError as error:
        print(f"codexbar: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError):
        print("codexbar: settings operation failed", file=sys.stderr)
        return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return converge(args.settings, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
