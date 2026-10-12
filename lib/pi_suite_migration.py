#!/usr/bin/env python3
"""Move staged third-party pi packages into the pi-plugins suite, in the dotfiles source.

Reads private_dot_pi/private_agent/pi-suite-migration.managed.json (the staged list) and
settings.managed.json (the pins), and asks the pinned suite revision which components it
provides: `git show <commit>:package.json` in a checkout (~/Projects/pi-plugins, or
--checkout), else in pi's installed clone. Nothing here touches ~/.pi or installed copies, and
nothing runs chezmoi: review `git diff`, then apply and commit as docs/plugins.md describes.

  check      report the pin, what it provides, which staged externals are duplicates (exit 1)
             and which are still pending (exit 0); the default
  apply      drop the duplicates from settings.managed.json, record them under `migrated`
  rollback   put every `migrated` entry back where it was and re-stage it

--components <name,...> supplies the provided set directly (tests, or a revision not checked
out anywhere); --dry-run prints the resulting package list instead of writing.
"""
import argparse
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_settings as a  # noqa: E402

SETTINGS = "private_dot_pi/private_agent/settings.managed.json"
MIGRATION = "private_dot_pi/private_agent/pi-suite-migration.managed.json"
CHECKOUT = os.path.join(a.HOME, "Projects/pi-plugins")
INSTALLED = os.path.join(a.HOME, ".pi/agent/git/github.com/justmytwospence/pi-plugins")


def _read(rel):
    path = os.path.join(a.source_dir(), rel)
    with open(path) as handle:
        return path, json.load(handle)


def _write(path, data):
    with open(path, "w") as handle:
        handle.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def manifest_at(commit, checkouts):
    """package.json of the suite at `commit`, from the first checkout that has it."""
    for path in checkouts:
        if not os.path.isdir(path):
            continue
        proc = subprocess.run(["git", "-C", path, "show", "%s:package.json" % commit],
                              capture_output=True, text=True)
        if proc.returncode == 0:
            return json.loads(proc.stdout), path
    raise SystemExit("commit %s is in none of: %s (fetch it, or pass --components)" % (commit[:12], ", ".join(checkouts)))


def resolve(args):
    settings_path, settings = _read(SETTINGS)
    migration_path, migration = _read(MIGRATION)
    packages = settings.get("packages", [])
    pin = a.suite_entry(packages, migration["suite"])
    if pin is None:
        raise SystemExit("no %s package in %s" % (migration["suite"], SETTINGS))
    if args.components is not None:
        components, origin = {c.strip() for c in args.components.split(",") if c.strip()}, "--components"
    elif pin[2] is None:
        raise SystemExit("%s is pinned without a commit; pass --components" % migration["suite"])
    else:
        manifest, origin = manifest_at(pin[2], [args.checkout, INSTALLED])
        components = a.suite_components(manifest)
    return settings_path, settings, migration_path, migration, pin, components, origin


def cmd_check(args):
    _, settings, _, migration, pin, components, origin = resolve(args)
    packages = settings.get("packages", [])
    duplicates = a.suite_duplicates(packages, components, migration.get("staged", []))
    pending = [s for s in migration.get("staged", []) if s not in duplicates]
    print("suite: %s (components from %s)" % (pin[1], origin))
    print("provides: %s" % ", ".join(sorted(components)))
    for entry in duplicates:
        print("duplicate: %s and packages/%s both enabled; run apply" % (entry["package"], entry["component"]))
    for entry in pending:
        print("pending: %s (suite has no packages/%s yet)" % (entry["package"], entry["component"]))
    for record in migration.get("migrated", []):
        print("migrated: %s -> packages/%s at %s" % (a.package_source(record["package"]), record["component"], record["suite"]))
    return 1 if duplicates else 0


def cmd_apply(args):
    settings_path, settings, migration_path, migration, pin, components, _ = resolve(args)
    packages, moved, pending = a.migrate_to_suite(settings.get("packages", []), components, migration)
    if not moved:
        print("nothing to migrate: %d pending" % len(pending))
        return 0
    for record in moved:
        print("migrate: %s -> packages/%s" % (a.package_source(record["package"]), record["component"]))
    if args.dry_run:
        print(json.dumps(packages, indent=2, ensure_ascii=False))
        return 0
    _write(settings_path, dict(settings, packages=packages))
    _write(migration_path, dict(migration, staged=pending, migrated=migration.get("migrated", []) + moved))
    print("wrote %s and %s; review `git diff`, then commit with the pin bump" % (SETTINGS, MIGRATION))
    return 0


def cmd_rollback(args):
    settings_path, settings = _read(SETTINGS)
    migration_path, migration = _read(MIGRATION)
    migrated = migration.get("migrated", [])
    if not migrated:
        print("nothing migrated")
        return 0
    packages = a.rollback_from_suite(settings.get("packages", []), migrated)
    for record in migrated:
        print("restore: %s at %d" % (a.package_source(record["package"]), record["index"]))
    if args.dry_run:
        print(json.dumps(packages, indent=2, ensure_ascii=False))
        return 0
    staged = migration.get("staged", []) + [{"package": a.package_source(r["package"]), "component": r["component"]} for r in migrated]
    _write(settings_path, dict(settings, packages=packages))
    _write(migration_path, dict(migration, staged=staged, migrated=[]))
    print("wrote %s and %s; review `git diff`" % (SETTINGS, MIGRATION))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", default="check", choices=("check", "apply", "rollback"))
    parser.add_argument("--checkout", default=CHECKOUT, help="suite checkout to read package.json from (default %(default)s)")
    parser.add_argument("--components", help="comma-separated components the pinned suite provides (skips git)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return {"check": cmd_check, "apply": cmd_apply, "rollback": cmd_rollback}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
