#!/usr/bin/env python3
"""Converge the explicitly managed Rex macOS preferences."""

import argparse
import json
import plistlib
import subprocess
import sys
from pathlib import Path
from xml.parsers.expat import ExpatError

DOMAIN = "com.superlogical.rex"
PREFERENCE_TYPES = {
    "Workspace.appearance": str,
    "Workspace.darkThemeID": str,
    "Workspace.lightThemeID": str,
    "Workspace.tabStyle": str,
    "Workspace.sidebarPosition": str,
    "Workspace.interfaceStyle": str,
    "Workspace.tabIconTintMode": str,
    "Workspace.inactivePaneFadeMode": str,
    "Workspace.terminalImproveTextContrast": bool,
    "Workspace.usesStandardInactiveWindowPaneStyles": bool,
    "rex.agents.names-sessions": bool,
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


def load_settings(path: Path) -> dict:
    try:
        document = json.loads(Path(path).read_bytes(), object_pairs_hook=_unique_object)
        preferences = document["rex"]["preferences"]
        _validate_preferences(preferences)
        return preferences
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise SettingsError("invalid settings") from None


def changed_preferences(live, desired):
    return {key: value for key, value in desired.items()
            if key not in live or type(live[key]) is not type(value) or live[key] != value}


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
        if type(value) is bool:
            kind, text = "-bool", "true" if value else "false"
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
