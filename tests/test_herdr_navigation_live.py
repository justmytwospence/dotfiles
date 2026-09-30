"""Real fzf PTY acceptance, isolated from live Herdr and user fzf overrides."""

import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shutil
import struct
import subprocess
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PICKER = ROOT / "shell/.local/bin/herdr-space-picker"


@unittest.skipUnless(shutil.which("fzf"), "fzf not installed")
class FzfPtyTest(unittest.TestCase):
    def exercise(self, keys, expected):
        with tempfile.TemporaryDirectory(prefix="space-picker-") as directory:
            log = Path(directory) / "focus.json"
            fake = Path(directory) / "herdr"
            fake.write_text('''#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:] == ['workspace', 'list']:
    print(json.dumps({'result': {'workspaces': [
        {'workspace_id': 'opaque1', 'label': 'apple'},
        {'workspace_id': 'opaque2', 'label': 'banana'}]}}))
elif sys.argv[1:3] == ['workspace', 'focus']:
    with open(os.environ['TEST_FOCUS_LOG'], 'w') as f:
        json.dump(sys.argv[3:], f)
    print('{"result": {}}')
else:
    sys.exit(2)
''')
            fake.chmod(0o755)
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
            def controlling_tty():
                os.setsid()
                fcntl.ioctl(0, termios.TIOCSCTTY, 0)
            env = dict(os.environ, TERM="xterm-256color", HERDR_BIN_PATH=str(fake),
                       TEST_FOCUS_LOG=str(log), FZF_DEFAULT_OPTS="--select-1 --bind enter:execute(false)")
            proc = subprocess.Popen([str(PICKER)], stdin=slave, stdout=slave, stderr=slave,
                                    env=env, preexec_fn=controlling_tty)
            os.close(slave)
            output = b""
            try:
                deadline = time.monotonic() + 8
                while b"banana" not in output and time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        output += os.read(master, 65536)
                self.assertIn(b"banana", output, output.decode(errors="replace"))
                # fzf draws before completing its terminal initialization. A
                # real terminal answers CPR; this PTY needs to emulate it.
                if b"\x1b[6n" in output:
                    os.write(master, b"\x1b[1;1R")
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        chunk = os.read(master, 65536)
                        output += chunk
                        if b"\x1b[6n" in chunk:
                            os.write(master, b"\x1b[1;1R")
                    elif not termios.tcgetattr(master)[3] & termios.ICANON:
                        break
                os.write(master, keys)
                # Typing a sole match must not auto-select it. Wait for the
                # rendered query before Enter; cancellation needs no Enter.
                if expected is not None:
                    time.sleep(0.25)
                    self.assertIsNone(proc.poll(), "sole match auto-selected")
                    self.assertFalse(log.exists())
                    os.write(master, b"\r")
                deadline = time.monotonic() + 8
                while proc.poll() is None and time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        try:
                            output += os.read(master, 65536)
                        except OSError:
                            break
                self.assertEqual(proc.wait(timeout=2), 0, output.decode(errors="replace"))
                if expected is None:
                    self.assertFalse(log.exists())
                else:
                    self.assertTrue(log.exists(), output.decode(errors="replace"))
                    self.assertEqual(json.loads(log.read_text()), [expected], output.decode(errors="replace"))
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                os.close(master)

    def test_type_immediately_and_enter_exact_space(self):
        self.exercise(b"banana", "opaque2")

    def test_escape_and_ctrl_c_leave_focus_unchanged(self):
        for key in (b"\x1b", b"\x03"):
            with self.subTest(key=key):
                self.exercise(key, None)


if __name__ == "__main__":
    unittest.main()
