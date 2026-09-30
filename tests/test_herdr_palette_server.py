"""Opt-in real Herdr client + popup smoke, with isolated config/state.

HERDR_FZF_LIVE=1 python3 -m unittest discover -s tests -p test_herdr_palette_server.py -v
"""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PICKER = ROOT / "shell/.local/bin/herdr-space-picker"


@unittest.skipUnless(os.environ.get("HERDR_FZF_LIVE") == "1" and shutil.which("herdr") and shutil.which("fzf"),
                     "set HERDR_FZF_LIVE=1 for real isolated client/popup smoke")
class HerdrPopupTest(unittest.TestCase):
    def test_space_tab_and_command_palette_in_real_popups(self):
        with tempfile.TemporaryDirectory(prefix="herdr-fzf-", dir="/tmp") as directory:
            config = Path(directory) / "config/herdr"
            config.mkdir(parents=True)
            command = shlex.join([sys.executable, "-B", str(PICKER)])
            (config / "config.toml").write_text('''onboarding = false
[ui.toast]
delivery = "off"
[ui.sound]
enabled = false
[keys]
prefix = "ctrl+b"
[[keys.command]]
key = "prefix+f"
type = "popup"
command = %s
width = "90%%"
height = "80%%"
[[keys.command]]
key = "prefix+space"
type = "popup"
command = %s
width = "90%%"
height = "80%%"
''' % (json.dumps(command), json.dumps(command + " everything")))
            env = {k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}
            env.update(XDG_CONFIG_HOME=str(Path(directory) / "config"), XDG_STATE_HOME=str(Path(directory) / "state"),
                       TERM="xterm-256color", HERDR_DISABLE_SOUND="1")
            session = "picker-smoke"
            socket_path = config / "sessions" / session / "herdr.sock"
            log = open(Path(directory) / "server.log", "w+")
            server = subprocess.Popen(["herdr", "--session", session, "server"], env=env,
                                      stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            client = None
            master = None
            def cli(*args):
                p = subprocess.run(["herdr", "--session", session, *args], env=env,
                                   capture_output=True, text=True, timeout=10)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                return json.loads(p.stdout)["result"] if p.stdout.strip() else {}
            try:
                deadline = time.monotonic() + 12
                while not socket_path.exists() and server.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.05)
                if not socket_path.exists():
                    log.seek(0)
                    self.fail(log.read())
                first = cli("workspace", "create", "--cwd", directory, "--label", "source", "--focus")
                target = cli("workspace", "create", "--cwd", directory, "--label", "target", "--no-focus")
                tab = cli("tab", "create", "--workspace", target["workspace"]["workspace_id"],
                          "--cwd", directory, "--label", "named-window", "--no-focus")
                tid = tab["tab"]["tab_id"]
                master, slave = pty.openpty()
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 35, 140, 0, 0))
                def tty():
                    os.setsid()
                    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
                client = subprocess.Popen(["herdr", "--session", session], env=env, stdin=slave, stdout=slave,
                                          stderr=slave, preexec_fn=tty)
                os.close(slave)
                output = b""
                def pump(timeout=0.1):
                    nonlocal output
                    if select.select([master], [], [], timeout)[0]:
                        chunk = os.read(master, 65536)
                        output += chunk
                        if b"\x1b[6n" in chunk:
                            os.write(master, b"\x1b[1;1R")
                def see(text):
                    nonlocal output
                    deadline = time.monotonic() + 10
                    while text not in output and time.monotonic() < deadline:
                        pump()
                    self.assertIn(text, output, output.decode(errors="replace")[-5000:])
                    # Let the terminal state transition finish before typing.
                    for _ in range(3):
                        pump()
                def send(data):
                    nonlocal output
                    output = b""
                    os.write(master, data)
                see(b"source")
                send(b"\x02f")
                see(b"named-window")
                send(b"named-window")
                for _ in range(3):
                    pump()
                send(b"\r")
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    pump()
                    if cli("api", "snapshot")["snapshot"].get("focused_tab_id") == tid:
                        break
                self.assertEqual(cli("api", "snapshot")["snapshot"].get("focused_tab_id"), tid)
                send(b"\x02 ")
                see(b"Everything>")
                send(b"Rename current tab/window")
                for _ in range(3):
                    pump()
                send(b"\r")
                see(b"Name (blank cancels)")
                send(b"palette-renamed\r")
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    pump()
                    tabs = cli("tab", "list", "--workspace", target["workspace"]["workspace_id"])["tabs"]
                    if any(t["tab_id"] == tid and t["label"] == "palette-renamed" for t in tabs):
                        break
                self.assertTrue(any(t["tab_id"] == tid and t["label"] == "palette-renamed" for t in tabs),
                                output.decode(errors="replace")[-5000:])
            finally:
                # Close the PTY first: macOS can block terminal teardown while
                # its output queue is full if we wait without draining it.
                if master is not None:
                    os.close(master)
                    master = None
                if client is not None:
                    client.terminate()
                    try:
                        client.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        client.kill()  # Only this test's isolated client.
                        client.wait(timeout=3)
                subprocess.run(["herdr", "--session", session, "server", "stop"], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.terminate()
                    try:
                        server.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        server.kill()  # Only this test's isolated server.
                        server.wait(timeout=3)
                log.close()
