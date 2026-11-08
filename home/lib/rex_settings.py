#!/usr/bin/env python3
"""Converge the explicitly managed Rex macOS preferences."""

import argparse
import json
import math
import plistlib
import subprocess
import sys
from pathlib import Path
from xml.parsers.expat import ExpatError

DOMAIN = "com.superlogical.rex"
ACTIVITY_PREFERENCE = "Workspace.programActivityStatusPreferences"
ACTIVITY_STATES = ("working", "blocked", "error", "done")
ACTIVITY_FLAGS = ("isEnabled", "showsInTabs", "showsNotification", "badgesDockIcon", "playsSound")
_MISSING = object()
PREFERENCE_TYPES = {
    "Workspace.appearance": str,
    "Workspace.darkThemeID": str,
    "Workspace.lightThemeID": str,
    "Workspace.tabStyle": str,
    "Workspace.sidebarPosition": str,
    "Workspace.interfaceStyle": str,
    "Workspace.tabIconTintMode": str,
    "Workspace.inactivePaneFadeMode": str,
    "Workspace.terminalFontName": str,
    "Workspace.terminalFontPointSize": float,
    "Workspace.terminalImproveTextContrast": bool,
    "Workspace.usesStandardInactiveWindowPaneStyles": bool,
    "rex.agents.names-sessions": bool,
    "Workspace.showsProgramStatusInTabs": bool,
    "Workspace.showsProgramActivityNotifications": bool,
    "Workspace.showsProgramActivityDockBadge": bool,
    "Workspace.playsProgramActivitySounds": bool,
    ACTIVITY_PREFERENCE: dict,
}


class SettingsError(Exception):
    pass


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _validate_preferences(preferences):
    if not isinstance(preferences, dict):
        raise SettingsError("invalid preferences")
    for key, value in preferences.items():
        if key not in PREFERENCE_TYPES or type(value) is not PREFERENCE_TYPES[key]:
            raise SettingsError("invalid preferences")
        if key == "Workspace.terminalFontPointSize" and (not math.isfinite(value) or value <= 0):
            raise SettingsError("invalid preferences")
        if key == ACTIVITY_PREFERENCE:
            if set(value) != set(ACTIVITY_STATES):
                raise SettingsError("invalid preferences")
            for state in value.values():
                if (type(state) is not dict or set(state) != set(ACTIVITY_FLAGS)
                        or any(type(flag) is not bool for flag in state.values())):
                    raise SettingsError("invalid preferences")


def load_settings(path: Path) -> dict:
    try:
        document = json.loads(Path(path).read_bytes(), object_pairs_hook=_unique_object)
        preferences = document["rex"]["preferences"]
        _validate_preferences(preferences)
        return preferences
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise SettingsError("invalid settings") from None


def _decode_activity_preferences(value) -> dict:
    def reject_constant(_value):
        raise ValueError("non-finite value")

    try:
        if type(value) is not bytes:
            raise ValueError("invalid native type")
        result = json.loads(value.decode("utf-8"), object_pairs_hook=_unique_object,
                            parse_constant=reject_constant)
        if type(result) is not dict or any(
                state in result and type(result[state]) is not dict for state in ACTIVITY_STATES):
            raise ValueError("invalid structure")
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise SettingsError("invalid activity preferences") from None


def _encode_activity_preferences(live_value, desired) -> bytes:
    current = {} if live_value is _MISSING else _decode_activity_preferences(live_value)
    for state, flags in desired.items():
        current.setdefault(state, {}).update(flags)
    try:
        return json.dumps(current, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise SettingsError("invalid activity preferences") from None


def changed_preferences(live, desired):
    changed = {}
    for key, value in desired.items():
        if key == ACTIVITY_PREFERENCE:
            current = ({} if key not in live else _decode_activity_preferences(live[key]))
            if any(type(current.get(state, {}).get(flag)) is not bool
                   or current[state][flag] != expected
                   for state, flags in value.items() for flag, expected in flags.items()):
                changed[key] = value
        elif key not in live or type(live[key]) is not type(value) or live[key] != value:
            changed[key] = value
    return changed


def _run(args):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        raise SettingsError("native command failed") from None


def _read_defaults():
    result = _run(["defaults", "export", DOMAIN, "-"])
    if result.returncode:
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


def _write_defaults(changed):
    _validate_preferences(changed)
    for key, value in changed.items():
        if key == ACTIVITY_PREFERENCE:
            live = _read_defaults()
            kind = "-data"
            text = _encode_activity_preferences(live.get(key, _MISSING), value).hex()
        elif type(value) is bool:
            kind, text = "-bool", "true" if value else "false"
        elif type(value) is float:
            kind, text = "-float", str(value)
        else:
            kind, text = "-string", value
        if _run(["defaults", "write", DOMAIN, key, kind, text]).returncode:
            raise SettingsError("write defaults failed")


def converge(settings_path: Path, *, check: bool = False) -> int:
    try:
        desired = load_settings(settings_path)
        if sys.platform != "darwin":
            raise SettingsError("macOS required")
        changed = changed_preferences(_read_defaults(), desired)
        if not changed:
            return 0
        if check:
            return 1
        _write_defaults(changed)
        if changed_preferences(_read_defaults(), desired):
            raise SettingsError("verify managed settings failed")
        print("rex: updated preferences: " + ", ".join(changed))
        return 0
    except SettingsError as error:
        print(f"rex: {error}", file=sys.stderr)
        return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return converge(args.settings, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
