"""Heeler retirement tests: temporary homes and mocked Herdr only."""
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from lib import retire_heeler as heeler


class Retirement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="heeler-test-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home with spaces"
        self.home.mkdir()
        self.config = self.home / ".config/herdr/plugins/config/heeler"
        self.state = self.home / ".local/state/herdr/plugins/heeler"
        self.helper = self.home / ".local/bin/heeler-setup"
        self.keys = self.home / ".ssh/authorized_keys"
        self.calls = []
        self.installed = True
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": str(self.home),
                               "XDG_CONFIG_HOME": str(self.home / ".config"),
                               "XDG_STATE_HOME": str(self.home / ".local/state")}).start()
        patch.object(heeler.shutil, "which", return_value="/mock/herdr").start()
        patch.object(heeler.subprocess, "run", side_effect=self.native).start()

    def native(self, args, **kwargs):
        self.calls.append(args)
        if args[1:] == ["session", "list", "--json"]:
            return subprocess.CompletedProcess(args, 0, json.dumps({"sessions": [
                {"name": "default", "running": True},
                {"name": "homelab", "running": True},
                {"name": "offline", "running": False},
            ]}), "")
        self.assertEqual(args[1:3], ["--session", args[2]])
        self.assertEqual(args[3:], ["plugin", "uninstall", "heeler"])
        if self.installed:
            self.installed = False
            return subprocess.CompletedProcess(args, 0, "Uninstalled heeler.\n", "")
        return subprocess.CompletedProcess(args, 1, "", "plugin not installed: heeler\n")

    def files(self, body=b"ssh-ed25519 AAAA heeler\n", mode=0o640):
        for path in (self.config, self.state):
            path.mkdir(parents=True)
            (path / "fixture.json").write_text("Heeler state")
            neighbor = path.parent / "unrelated"
            neighbor.mkdir()
            (neighbor / "keep").write_text("unrelated")
        self.helper.parent.mkdir(parents=True)
        self.helper.write_text("old helper")
        self.keys.parent.mkdir(mode=0o700)
        self.keys.write_bytes(body)
        self.keys.chmod(mode)

    def assert_state_present(self):
        for path in (self.config, self.state, self.helper):
            self.assertTrue(path.exists(), str(path))

    def test_missing_home_and_missing_cli_are_noops(self):
        with patch.object(heeler.shutil, "which", return_value=None):
            heeler.retire(self.home)
            heeler.retire(self.home)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertEqual(self.calls, [])

    def test_native_uninstall_all_running_sessions_and_repeat(self):
        self.files()
        cache = self.home / ".config/herdr/plugins/github/heeler-deadbeef/local-work"
        cache.parent.mkdir(parents=True)
        cache.write_text("preserve native-owned checkout")
        heeler.retire(self.home)
        inode = self.keys.stat().st_ino
        heeler.retire(self.home)
        self.assertEqual(self.keys.read_bytes(), b"")
        self.assertEqual(self.keys.stat().st_ino, inode)
        self.assertEqual(stat.S_IMODE(self.keys.stat().st_mode), 0o640)
        for path in (self.config, self.state, self.helper):
            self.assertFalse(path.exists(), str(path))
        for path in (self.config, self.state):
            self.assertEqual((path.parent / "unrelated/keep").read_text(), "unrelated")
        self.assertEqual(cache.read_text(), "preserve native-owned checkout")
        self.assertEqual([call[2] for call in self.calls if "uninstall" in call],
                         ["default", "homelab", "default", "homelab"])

    def test_only_exact_marked_keys_removed_atomically_with_modes(self):
        keep = (b"# ssh-ed25519 AAAA heeler\r\n"
                b"ssh-ed25519 AAAA other phone\r\n"
                b"ssh-rsa BBBB heeler-work\n"
                b"ssh-ed25519 CCCC user@heeler\n"
                b'restrict,command="echo heeler" ssh-ed25519 DDDD other\n'
                b"ssh-ed25519 EEEE herdr-pairing:other:exp:1\n"
                b"ssh-ed25519 FFFF manually-enrolled-without-marker")
        self.files(keep + b"\nssh-ed25519 GGGG heeler\nssh-rsa HHHH heeler rsa\n")
        self.keys.parent.chmod(0o750)
        original_replace = os.replace
        replacements = []

        def replace(source, target):
            self.assertEqual(self.keys.read_bytes(), keep + b"\nssh-ed25519 GGGG heeler\nssh-rsa HHHH heeler rsa\n")
            self.assertEqual(Path(source).parent, self.keys.parent)
            self.assertEqual(Path(source).read_bytes(), keep + b"\n")
            self.assertEqual(stat.S_IMODE(Path(source).stat().st_mode), 0o640)
            replacements.append(target)
            original_replace(source, target)

        owner = (self.keys.stat().st_uid, self.keys.stat().st_gid)
        with patch.object(heeler.os, "replace", side_effect=replace):
            heeler.revoke_keys(self.home)
        self.assertEqual(replacements, [self.keys])
        self.assertEqual((self.keys.stat().st_uid, self.keys.stat().st_gid), owner)
        self.assertEqual(stat.S_IMODE(self.keys.parent.stat().st_mode), 0o750)
        self.assertEqual(list(self.keys.parent.iterdir()), [self.keys])

    def test_bootstrap_requires_identifiable_heeler_command(self):
        entry = self.home / ".config/herdr/plugins/github/heeler-deadbeef/plugin/src/pair-accept.js"
        remove = f'restrict,command="\'/usr/bin/node\' \'{entry}\' --pairing-id p1" ssh-ed25519 AAAA herdr-pairing:p1:exp:1\n'.encode()
        keep = (b'restrict,command="other pair-accept.js" ssh-ed25519 BBBB herdr-pairing:p2:exp:1\n'
                b'restrict,command="echo /Heeler/plugin/src/pair-accept.js" ssh-ed25519 CCCC herdr-pairing:p3:exp:1\n')
        self.files(remove + keep)
        heeler.revoke_keys(self.home)
        self.assertEqual(self.keys.read_bytes(), keep)

    def test_unrelated_keys_keep_bytes_inode_and_permissions(self):
        body = b'ssh-rsa AAAA not-heeler\r\n\n# comment mentioning heeler\nssh-ed25519 BBBB manual'
        self.files(body, 0o600)
        before = self.keys.stat()
        heeler.revoke_keys(self.home)
        self.assertEqual(self.keys.read_bytes(), body)
        self.assertEqual(heeler.signature(self.keys.stat()), heeler.signature(before))

    def test_uninstall_failure_preserves_keys_config_state_helper(self):
        self.files()
        with patch.object(heeler.subprocess, "run", return_value=subprocess.CompletedProcess([], 23, "", "registry permission denied")):
            with self.assertRaisesRegex(heeler.RetirementError, "permission denied"):
                heeler.retire(self.home)
        self.assert_state_present()
        self.assertEqual(self.keys.read_bytes(), b"ssh-ed25519 AAAA heeler\n")

    def test_only_exact_absent_error_is_accepted(self):
        arguments = ["plugin", "uninstall", "heeler"]
        for code, error in ((2, "plugin not installed: heeler"),
                            (1, "plugin not installed: heeler\nregistry failed")):
            with self.subTest(code=code, error=error):
                with patch.object(heeler.subprocess, "run", return_value=subprocess.CompletedProcess([], code, "", error)):
                    with self.assertRaises(heeler.RetirementError):
                        heeler.herdr_command(arguments)

    def test_malformed_session_list_preserves_state(self):
        self.files()
        for data in ("not json", '{}', '{"sessions":[null]}'):
            with self.subTest(data=data):
                with patch.object(heeler.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, data, "")):
                    with self.assertRaises((ValueError, heeler.RetirementError)):
                        heeler.retire(self.home)
                self.assert_state_present()

    def test_missing_cli_with_installed_or_broken_registry_fails(self):
        self.files()
        registry = self.home / ".config/herdr/plugins.json"
        for data in ('[{"plugin_id":"heeler"}]', 'not json', '{}'):
            registry.write_text(data)
            with self.subTest(data=data), patch.object(heeler.shutil, "which", return_value=None):
                with self.assertRaises((ValueError, heeler.RetirementError)):
                    heeler.retire(self.home)
                self.assert_state_present()
                self.assertEqual(registry.read_text(), data)
        registry.write_text('[{"plugin_id":"unrelated"}]')
        with patch.object(heeler.shutil, "which", return_value=None):
            heeler.retire(self.home)
        self.assertEqual(registry.read_text(), '[{"plugin_id":"unrelated"}]')

    def test_atomic_replace_failure_keeps_original_and_cleans_temporary(self):
        self.files()
        before = self.keys.stat()
        with patch.object(heeler.os, "replace", side_effect=PermissionError("fixture replace denied")):
            with self.assertRaises(PermissionError):
                heeler.retire(self.home)
        self.assertEqual(self.keys.read_bytes(), b"ssh-ed25519 AAAA heeler\n")
        self.assertEqual(heeler.signature(self.keys.stat()), heeler.signature(before))
        self.assertEqual(list(self.keys.parent.iterdir()), [self.keys])
        self.assert_state_present()

    def test_concurrent_key_edit_is_not_overwritten(self):
        self.files()
        mkstemp = tempfile.mkstemp

        def create(**kwargs):
            self.keys.write_bytes(b"ssh-ed25519 AAAA concurrent-key\n")
            return mkstemp(**kwargs)

        with patch.object(heeler.tempfile, "mkstemp", side_effect=create):
            with self.assertRaisesRegex(heeler.RetirementError, "changed during cleanup"):
                heeler.retire(self.home)
        self.assertEqual(self.keys.read_bytes(), b"ssh-ed25519 AAAA concurrent-key\n")
        self.assertEqual(list(self.keys.parent.iterdir()), [self.keys])
        self.assert_state_present()

    def test_active_pairing_lock_is_not_stolen(self):
        self.files()
        lock = self.keys.with_name("authorized_keys.herdr-pairing.lock")
        lock.write_text("other editor")
        with self.assertRaises(FileExistsError):
            heeler.retire(self.home)
        self.assertEqual(lock.read_text(), "other editor")
        self.assertEqual(self.keys.read_bytes(), b"ssh-ed25519 AAAA heeler\n")
        self.assert_state_present()

    def test_symlinked_or_hardlinked_authorized_keys_are_refused(self):
        self.files()
        target = self.home / "other-keys"
        self.keys.rename(target)
        for link in (self.keys.symlink_to, lambda p: os.link(p, self.keys)):
            link(target)
            with self.assertRaises(heeler.RetirementError):
                heeler.retire(self.home)
            self.assertEqual(target.read_bytes(), b"ssh-ed25519 AAAA heeler\n")
            self.assert_state_present()
            self.keys.unlink()

    def test_leaf_symlinks_are_unlinked_without_following(self):
        target = self.home / "unrelated-dir"
        target.mkdir()
        (target / "keep").write_text("stay")
        for path in (self.config, self.state, self.helper):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(target, target_is_directory=True)
        heeler.retire(self.home)
        self.assertEqual((target / "keep").read_text(), "stay")
        self.assertTrue(all(not p.is_symlink() for p in (self.config, self.state, self.helper)))

    def test_xdg_roots_are_honored(self):
        self.files()
        config, state = self.home / "xdg-config", self.home / "xdg-state"
        for base, child in ((config, "plugins/config/heeler"), (state, "plugins/heeler")):
            (base / "herdr" / child).mkdir(parents=True)
        with patch.dict(os.environ, XDG_CONFIG_HOME=str(config), XDG_STATE_HOME=str(state)):
            heeler.retire(self.home)
        self.assertTrue(self.config.exists())
        self.assertTrue(self.state.exists())
        self.assertFalse((config / "herdr/plugins/config/heeler").exists())
        self.assertFalse((state / "herdr/plugins/heeler").exists())


if __name__ == "__main__":
    unittest.main()
