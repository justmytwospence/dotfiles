"""Tests for dot_local/bin/executable_fresh, the one-command cooldown bypass."""
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "dot_local/bin/executable_fresh"

# Prints its arguments, then the cooldown overrides it sees.
FAKE = """#!/bin/sh
echo "args: $*"
env | grep -E '^(npm_config_min_release_age|pnpm_config_minimum_release_age|YARN_NPM_MINIMAL_AGE_GATE|UV_EXCLUDE_NEWER|PIP_UPLOADED_PRIOR_TO)=' | sort
"""


class Fresh(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        bindir = Path(self.tmp.name)
        for name in ("bun", "bunx", "npm"):
            path = bindir / name
            path.write_text(FAKE)
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        self.env = dict(os.environ, PATH="%s:%s" % (bindir, os.environ["PATH"]))

    def run_fresh(self, *args):
        return subprocess.run(["sh", str(SCRIPT), *args], env=self.env, capture_output=True, text=True)

    def test_sets_every_override(self):
        out = self.run_fresh("npm", "install", "pkg@1.0.0")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("args: install pkg@1.0.0", out.stdout)
        for line in ("npm_config_min_release_age=0", "pnpm_config_minimum_release_age=0", "YARN_NPM_MINIMAL_AGE_GATE=0"):
            self.assertIn(line, out.stdout)
        self.assertRegex(out.stdout, r"UV_EXCLUDE_NEWER=\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
        self.assertRegex(out.stdout, r"PIP_UPLOADED_PRIOR_TO=\d{4}-\d\d-\d\dT")

    def test_bun_gets_the_flag_after_its_subcommand(self):
        self.assertIn("args: add --minimum-release-age=0 lib", self.run_fresh("bun", "add", "lib").stdout)
        self.assertIn("args: x --minimum-release-age=0 tool", self.run_fresh("bun", "x", "tool").stdout)
        self.assertIn("args: --minimum-release-age=0 tool", self.run_fresh("bunx", "tool").stdout)
        # Not a package-manager subcommand: passed through untouched.
        self.assertIn("args: run build", self.run_fresh("bun", "run", "build").stdout)

    def test_no_command_prints_usage(self):
        out = self.run_fresh()
        self.assertEqual(out.returncode, 2)
        self.assertIn("fresh: run one command", out.stdout)


if __name__ == "__main__":
    unittest.main()
