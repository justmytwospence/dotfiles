"""Opt-in real Herdr client + popup smoke, with isolated config/state.

HERDR_FZF_LIVE=1 python3 -m unittest discover -s tests -p test_herdr_palette_server.py -v
"""
import codecs
import fcntl
import json
import re
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


class Screen:
    """Minimal VT screen for Herdr's absolute-positioned, incremental redraws."""
    def __init__(self, rows=35, columns=140):
        self.cells = [[" "] * columns for _ in range(rows)]
        self.row = self.column = 0
        self.pending = ""
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def feed(self, data):
        self.pending += self.decoder.decode(data)
        while self.pending:
            text = self.pending
            if text[0] == "\x1b":
                if len(text) < 2:
                    return
                if text[1] == "[":
                    match = re.match(r"\x1b\[([0-?]*)([ -/]*)([@-~])", text)
                    if not match:
                        return
                    self.pending = text[match.end():]
                    params, _, command = match.groups()
                    if params.startswith(("?", ">", "<")):
                        continue
                    numbers = [int(p or "0") for p in params.split(";") if p.isdigit() or not p]
                    n = numbers[0] if numbers else 0
                    if command in ("H", "f"):
                        self.row = min(len(self.cells)-1, max(0, (n or 1)-1))
                        self.column = min(len(self.cells[0])-1, max(0, (numbers[1] if len(numbers)>1 else 1)-1))
                    elif command == "G":
                        self.column = min(len(self.cells[0])-1, max(0, (n or 1)-1))
                    elif command == "J":
                        if n in (2, 3):
                            self.cells = [[" "] * len(self.cells[0]) for _ in self.cells]
                        elif n == 0:
                            self.cells[self.row][self.column:] = [" "] * (len(self.cells[0])-self.column)
                            for row in range(self.row+1, len(self.cells)):
                                self.cells[row] = [" "] * len(self.cells[0])
                    elif command == "K":
                        start, end = (0, len(self.cells[0])) if n == 2 else ((0, self.column+1) if n == 1 else (self.column, len(self.cells[0])))
                        self.cells[self.row][start:end] = [" "] * (end-start)
                    continue
                if text[1] == "]":
                    match = re.search(r"\x07|\x1b\\", text)
                    if not match:
                        return
                    self.pending = text[match.end():]
                    continue
                self.pending = text[2:]
                continue
            self.pending = text[1:]
            if text[0] == "\r":
                self.column = 0
            elif text[0] == "\n":
                self.row = min(len(self.cells)-1, self.row+1)
            elif text[0] == "\b":
                self.column = max(0, self.column-1)
            elif ord(text[0]) >= 32 and text[0] != "\x7f":
                self.cells[self.row][self.column] = text[0]
                self.column = min(len(self.cells[0])-1, self.column+1)

    def text(self):
        return "\n".join("".join(row) for row in self.cells)


class ScreenTest(unittest.TestCase):
    def test_split_redraws_preserve_unchanged_spaces_and_characters(self):
        screen = Screen()
        screen.feed(b"\x1b[6;34HName\x1b[6;39H(blank\x1b[6;46Hcancels):")
        self.assertIn("Name (blank cancels):", screen.text())
        screen.feed(b"\x1b[6;34HName (blank cancels):")
        screen.feed(b"\x1b[6;46Hca\x1b[6;49Hcels):")
        self.assertIn("Name (blank cancels):", screen.text())


@unittest.skipUnless(os.environ.get("HERDR_FZF_LIVE") == "1" and shutil.which("herdr") and shutil.which("fzf"),
                     "set HERDR_FZF_LIVE=1 for real isolated client/popup smoke")
class HerdrPopupTest(unittest.TestCase):
    def test_space_tab_and_command_palette_in_real_popups(self):
        with tempfile.TemporaryDirectory(prefix="herdr-fzf-", dir="/tmp") as directory:
            config = Path(directory) / "config/herdr"
            config.mkdir(parents=True)
            command = shlex.join([sys.executable, "-B", str(PICKER)])
            marker = Path(directory) / "attention-key"
            marker_command = "printf bound > " + shlex.quote(str(marker))
            # These fields are JSON-compatible TOML; avoid a tomllib dependency
            # so the native-key acceptance test also runs on NUC's Python 3.9.
            fields = {"next_workspace", "previous_workspace", "next_tab", "previous_tab",
                      "cycle_pane_next", "cycle_pane_previous", "resize_mode"}
            fields.update("resize_pane_" + d for d in ("left", "down", "up", "right"))
            navigation_keys = []
            for line in (ROOT / "osx/.config/herdr/config.toml").read_text().splitlines():
                name, _, value = line.partition("=")
                if name.strip() in fields:
                    value = json.loads(value.split("#", 1)[0].strip())
                    navigation_keys.append(name.strip() + " = " + json.dumps(value))
            self.assertEqual(len(navigation_keys), len(fields))
            (config / "config.toml").write_text('''onboarding = false
[ui.toast]
delivery = "off"
[ui.sound]
enabled = false
[keys]
prefix = "ctrl+b"
%s
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
[[keys.command]]
key = "prefix+enter"
type = "shell"
command = %s
''' % ("\n".join(navigation_keys), json.dumps(command), json.dumps(command + " everything"),
       json.dumps(marker_command)))
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
                checked = subprocess.run(["herdr", "config", "check"], env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
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
                screen = Screen()
                def pump(timeout=0.1):
                    nonlocal output
                    if select.select([master], [], [], timeout)[0]:
                        chunk = os.read(master, 65536)
                        output += chunk
                        screen.feed(chunk)
                        if b"\x1b[6n" in chunk:
                            os.write(master, b"\x1b[1;1R")
                def see(text):
                    nonlocal output
                    deadline = time.monotonic() + 10
                    while text.decode() not in screen.text() and time.monotonic() < deadline:
                        pump()
                    self.assertIn(text.decode(), screen.text(), screen.text())
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
                # Focus is visible before the popup process exits/reaps. Do
                # not send the next shortcut during that modal-close interval.
                settling = time.monotonic() + 0.7
                while time.monotonic() < settling:
                    pump()
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
                def focus_after(keys, **expected):
                    send(keys)
                    deadline = time.monotonic() + 8
                    snapshot = {}
                    while time.monotonic() < deadline:
                        pump()
                        snapshot = cli("api", "snapshot")["snapshot"]
                        if all(snapshot.get(key) == value for key, value in expected.items()):
                            break
                    self.assertTrue(all(snapshot.get(k) == v for k, v in expected.items()),
                                    (expected, snapshot))
                    for _ in range(3):
                        pump()

                # Cycle through a vertical split as well as across spaces/tabs.
                base = tab["root_pane"]["pane_id"]
                split = cli("pane", "split", base, "--direction", "down", "--no-focus")
                pane = split["pane"]["pane_id"]
                # Rename's popup can still be reaping, and the client must
                # receive the new split before its local cycle action runs.
                settling = time.monotonic() + 0.7
                while time.monotonic() < settling:
                    pump()
                # CSI-u disambiguates Ctrl-h/j from Backspace/Enter, as the
                # negotiated keyboard protocol does in the live terminal.
                focus_after(b"\x02\x1b[108;5u", focused_pane_id=pane)
                focus_after(b"\x02\x1b[104;5u", focused_pane_id=base)
                focus_after(b"\x02\x1b[107;5u", focused_workspace_id=first["workspace"]["workspace_id"])
                focus_after(b"\x02\x1b[106;5u", focused_workspace_id=target["workspace"]["workspace_id"],
                            focused_tab_id=tid)
                focus_after(b"\x02\x1b[104;3u", focused_tab_id=target["tab"]["tab_id"])
                focus_after(b"\x02\x1b[108;3u", focused_tab_id=tid)
                send(b"\x02\r")
                deadline = time.monotonic() + 8
                while not marker.exists() and time.monotonic() < deadline:
                    pump()
                self.assertTrue(marker.exists(), "Ctrl-b Enter did not dispatch its custom command")
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
