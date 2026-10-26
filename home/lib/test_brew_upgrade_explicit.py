"""Exercise the explicit cask upgrade helper without invoking Homebrew."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("zsh"), "zsh is required")
class BrewUpgradeExplicitTests(unittest.TestCase):
    def run_helper(self, args, pinned="google-chrome", upgrade_status=0, unpin_status=0, pin_status=0):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mock = root / "brew"
            mock.write_text(
                '#!/bin/sh\n'
                'echo "$*" >> "$CALL_LOG"\n'
                'case "$1" in\n'
                'list) printf "%s\\n" "$PINNED" ;;\n'
                'upgrade) exit "$UPGRADE_STATUS" ;;\n'
                'unpin) exit "$UNPIN_STATUS" ;;\n'
                'pin) exit "$PIN_STATUS" ;;\n'
                'esac\n'
            )
            mock.chmod(0o755)
            log = root / "calls"
            env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}",
                       CALL_LOG=str(log), PINNED=pinned,
                       UPGRADE_STATUS=str(upgrade_status),
                       UNPIN_STATUS=str(unpin_status), PIN_STATUS=str(pin_status))
            source = Path(__file__).resolve().parents[1] / "dot_zsh/functions.zsh"
            result = subprocess.run(
                ["zsh", "-f", "-c", 'source "$1"; shift; brew-upgrade-explicit "$@"',
                 "test", str(source), *args], env=env, capture_output=True, text=True)
            return result.returncode, log.read_text().splitlines() if log.exists() else []

    def test_pinned_success(self):
        self.assertEqual(self.run_helper(["google-chrome"]), (0, [
            "list --cask --pinned", "unpin --cask google-chrome",
            "upgrade --cask google-chrome", "pin --cask google-chrome"]))

    def test_failed_upgrade_restores_pin(self):
        code, calls = self.run_helper(["google-chrome"], upgrade_status=7)
        self.assertEqual(code, 7)
        self.assertEqual(calls[-1], "pin --cask google-chrome")

    def test_failed_unpin_does_not_upgrade(self):
        code, calls = self.run_helper(["google-chrome"], unpin_status=8)
        self.assertEqual(code, 8)
        self.assertFalse(any(call.startswith("upgrade") for call in calls))
        self.assertEqual(calls[-1], "pin --cask google-chrome")

    def test_failed_repin_is_reported(self):
        self.assertEqual(self.run_helper(["google-chrome"], pin_status=9)[0], 9)

    def test_unpinned_cask_stays_unpinned(self):
        self.assertEqual(self.run_helper(["docker-desktop"]), (0, [
            "list --cask --pinned", "upgrade --cask docker-desktop"]))

    def test_pin_matching_is_exact(self):
        self.assertEqual(self.run_helper(["google-chrome"], pinned="google-chrome-beta")[1], [
            "list --cask --pinned", "upgrade --cask google-chrome"])

    def test_multiple_pins(self):
        self.assertEqual(self.run_helper(["google-chrome"], pinned="firefox\ngoogle-chrome")[1][-1],
                         "pin --cask google-chrome")

    def test_invalid_arguments(self):
        for args in ([], ["--greedy"], [""], ["google-chrome", "docker-desktop"]):
            with self.subTest(args=args):
                self.assertEqual(self.run_helper(args), (2, []))


if __name__ == "__main__":
    unittest.main()
