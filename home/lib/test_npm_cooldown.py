"""Tests for dot_local/bin/executable_npm-cooldown against a fake npm."""
import datetime
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "dot_local/bin/executable_npm-cooldown"

FAKE_NPM = """#!/bin/sh
case "$*" in
  "config get min-release-age") echo 7 ;;
  "config get min-release-age-exclude --json") echo '[]' ;;
  "view pkg version --json") echo '"2.0.0"' ;;
  "view pkg time --json") cat "$HOME/times.json" ;;
  *) echo "$*" >>"$HOME/calls" ;;
esac
"""


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class NpmCooldown(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        bindir = self.home / "bin"
        bindir.mkdir()
        npm = bindir / "npm"
        npm.write_text(FAKE_NPM)
        npm.chmod(npm.stat().st_mode | stat.S_IEXEC)
        self.env = dict(os.environ, HOME=str(self.home), PATH="%s:%s" % (bindir, os.environ["PATH"]))
        self.times(30, 1)

    def times(self, old, new):
        def ago(days):
            return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z")
        (self.home / "times.json").write_text(json.dumps({
            "created": ago(100), "1.0.0": ago(old), "2.0.0": ago(new)}))

    def allow(self, *entries):
        path = self.home / ".config/npm-cooldown/allow.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(list(entries)))

    def run_wrapper(self, *args):
        return subprocess.run(["node", str(SCRIPT), "--", "npm", *args], env=self.env,
                              capture_output=True, text=True, check=True).stdout

    def last_call(self):
        return (self.home / "calls").read_text().splitlines()[-1]

    def test_view_without_allowance_hides_young_release(self):
        self.assertEqual(json.loads(self.run_wrapper("view", "pkg", "version", "--json")), "1.0.0")

    def test_view_with_allowance_shows_allowed_release(self):
        self.allow("pkg@2.0.0")
        self.assertEqual(json.loads(self.run_wrapper("view", "pkg", "version", "--json")), "2.0.0")

    def test_install_latest_is_pinned_and_exempted(self):
        self.allow("pkg@2.0.0")
        self.run_wrapper("install", "pkg@latest", "--prefix", "/x")
        self.assertEqual(self.last_call(), "install pkg@2.0.0 --prefix /x --min-release-age-exclude=pkg")

    def test_install_exact_allowed_version_is_exempted(self):
        self.allow("pkg@2.0.0")
        self.run_wrapper("install", "pkg@2.0.0")
        self.assertEqual(self.last_call(), "install pkg@2.0.0 --min-release-age-exclude=pkg")

    def test_stale_allowance(self):
        self.allow("pkg@1.0.0")
        self.run_wrapper("install", "pkg@latest")
        self.assertEqual(self.last_call(), "install pkg@1.0.0 --min-release-age-exclude=pkg")
        self.times(40, 40)
        self.run_wrapper("install", "pkg@latest")
        self.assertEqual(self.last_call(), "install pkg@latest")

    def test_other_packages_are_untouched(self):
        self.allow("pkg@2.0.0")
        self.run_wrapper("install", "other@latest")
        self.assertEqual(self.last_call(), "install other@latest")


if __name__ == "__main__":
    unittest.main()
