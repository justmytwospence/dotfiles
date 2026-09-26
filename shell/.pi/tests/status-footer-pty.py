#!/usr/bin/env python3
"""Exercise the real Pi TUI in a disposable HOME. No prompts or model calls."""

import contextlib
import fcntl
import json
import os
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import tempfile
import termios
import time
from pathlib import Path

ENTRY = Path(__file__).resolve().parent.parent / "agent/extensions/agent-status.ts"
CC_CONFIG = ENTRY.parent.parent / "pi-cc-extensions.json"
CC_PACKAGE = Path(os.environ.get("PI_CC_PACKAGE_DIR", Path.home() / ".pi/agent/npm/node_modules/pi-cc-extensions"))
CC_ENTRY = CC_PACKAGE / "extensions/index.ts"
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def wait_for(predicate, poll, pump, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        if poll() is not None:
            break
        pump()
    # Exit can occur between predicate() and poll(). Recheck before reporting a
    # failure, especially when the predicate itself is waiting for process exit.
    return predicate()


def check_wait_race():
    states = iter([None, 0, 0])

    def poll():
        return next(states)

    assert wait_for(lambda: poll() is not None, poll, lambda: None, 1)
    assert not wait_for(lambda: False, lambda: 0, lambda: None, 1)
    assert not wait_for(lambda: False, lambda: None, lambda: None, 0)
    print("PASS: exit-between-polls, premature-exit and deadline regression checks")


def exercise(theme):
    baseline = os.environ.get("STATUS_FOOTER_BASELINE") == "1"
    marker = b"(auto)" if baseline else b"limits unavailable"
    pi = shutil.which("pi")
    assert pi, "pi must be on PATH"
    assert CC_ENTRY.is_file(), "Install pi-cc-extensions or set PI_CC_PACKAGE_DIR to test the real footer conflict"
    with tempfile.TemporaryDirectory(prefix="pi-footer-pty-") as tmp:
        home = Path(tmp)
        agent = home / "agent"
        agent.mkdir()
        shutil.copyfile(CC_CONFIG, agent / "pi-cc-extensions.json")
        trace = home / "lifecycle.log"
        probe = home / "probe.ts"
        probe.write_text(
            'import { appendFileSync } from "node:fs";\n'
            f'import footer from {json.dumps(str(ENTRY))};\n'
            f'const log = (s) => appendFileSync({json.dumps(str(trace))}, s + "\\n");\n'
            'if (!globalThis.__footerExitProbe) {\n'
            '  globalThis.__footerExitProbe = true;\n'
            '  const exit = process.exit.bind(process);\n'
            '  process.exit = (code) => { log(`exit ${code}`); return exit(code); };\n'
            '}\n'
            'export default function (pi) {\n'
            '  pi.on("session_start", (_event, ctx) => {\n'
            '    log("start");\n'
            '    log(`ccstyle ${pi.getCommands().some((command) => command.name === "ccstyle")}`);\n'
            '    ctx.ui.setStatus("mcp", ctx.ui.theme.fg("dim", "\\u{1f50c} MCP: 5 servers enabled"));\n'
            '  });\n'
            '  pi.on("session_shutdown", (event) => log(`before ${event.reason}`));\n'
            f'  {"// Native-only control; do not initialize the footer." if baseline else "footer(pi);"}\n'
            '  pi.on("session_shutdown", (event) => log(`after ${event.reason}`));\n'
            '}\n'
        )
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
        # Load only the footer and its real CC-style companion, plus a fake MCP
        # status. Do not inherit API keys, real auth, other packages or hooks.
        env = {
            "PATH": os.environ["PATH"], "HOME": tmp, "TERM": "xterm-256color",
            "COLORTERM": "truecolor", "LANG": "en_US.UTF-8",
            "PI_CODING_AGENT_DIR": str(agent), "PI_OFFLINE": "1", "PI_TELEMETRY": "0",
        }
        def establish_terminal():
            # A new session alone leaves the child without a controlling tty.
            # Match an actual terminal emulator, including foreground job control.
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        process = subprocess.Popen([
            pi, "--offline", "--no-session", "--no-extensions", "-e", str(probe), "-e", str(CC_ENTRY),
            "--no-skills", "--no-prompt-templates", "--no-context-files", "--no-tools",
            "--provider", "openai-codex", "--model", "gpt-6-astra",
            "--use-theme", theme, "--tui-mode", "fullscreen",
        ], cwd=tmp, env=env, stdin=slave, stdout=slave, stderr=slave, preexec_fn=establish_terminal)
        os.close(slave)
        captured = bytearray()

        def pump(timeout=0.1):
            ready, _, _ = select.select([master], [], [], timeout)
            if ready:
                with contextlib.suppress(OSError):
                    captured.extend(os.read(master, 65536))

        def until(predicate, label, seconds=15):
            if wait_for(predicate, process.poll, pump, seconds):
                return
            lifecycle = trace.read_text() if trace.exists() else "(no lifecycle trace)"
            raise AssertionError(f"Failed waiting for {label} (exit code: {process.returncode})\n{lifecycle}\n{captured[-5000:].decode(errors='replace')}")

        def command(text, acknowledgment=None):
            captured.clear()
            os.write(master, (text + "\r").encode())
            if acknowledgment:
                until(lambda: acknowledgment.encode() in captured, acknowledgment)

        def debug():
            log = agent / "pi-debug.log"
            if log.exists():
                log.unlink()
            command("/debug", "Debug log written")
            until(log.exists, "debug dump")
            data = log.read_text()
            lines = []
            for row in data.splitlines():
                match = re.match(r"\[\d+\] \(w=(\d+)\) (.*)", row)
                if match:
                    lines.append((int(match[1]), ANSI.sub("", json.loads(match[2]))))
            assert not data.split("=== Agent messages (JSONL) ===")[1].strip(), "Unexpected model conversation"
            return data, lines

        try:
            until(lambda: marker in captured, "footer startup")
            data, lines = debug()
            assert "Terminal: 120x40" in data
            if not baseline:
                assert any("Context" in row and "Est. session cost $0.00" in row for _, row in lines)
                assert any("Codex" in row and "limits unavailable" in row for _, row in lines)
                assert any("\uf1e6 MCP: 5 servers enabled" in row for _, row in lines), "Flat MCP plug missing"
            assert all(width <= 120 for width, _ in lines)
            print(f"{theme}, 120 columns:")
            for _, row in lines:
                if "Context" in row or "gpt-6-astra" in row or "Codex" in row or "MCP:" in row:
                    print(row)

            if not baseline:
                command("/status native", "Native footer restored")
                _, lines = debug()
                assert not any("limits unavailable" in row for _, row in lines), "Native fallback retained custom quota row"
                assert any("(auto)" in row for _, row in lines), "Native footer missing"
                command("/status on", "Custom footer enabled")
            captured.clear()
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 40, 0, 0))
            os.kill(process.pid, signal.SIGWINCH)
            until(lambda: marker in captured, "resized footer repaint")
            data, lines = debug()
            assert "Terminal: 40x40" in data
            if not baseline:
                assert any("Context" in row for _, row in lines)
            assert all(width <= 40 for width, _ in lines)

            command("/reload", "Reloaded")
            _, lines = debug()
            if not baseline:
                assert sum("limits unavailable" in row for _, row in lines) == 1, "Reload duplicated the quota row"
                assert any("\uf1e6 MCP:" in row for _, row in lines), "Reload lost the flat MCP plug"
            command("/quit")
            until(lambda: process.poll() is not None, "clean exit", seconds=10)
            assert process.returncode == 0
            lifecycle = trace.read_text()
            assert lifecycle.count("ccstyle true") == 2, "CC-style extension must be active before and after reload"
            assert "before reload\nafter reload" in lifecycle, lifecycle
            assert "before quit\nafter quit\nexit 0" in lifecycle, lifecycle
            print(f"PASS: {theme} {'native control' if baseline else 'custom footer'} with CC-style loaded: startup, resize, reload, clean exit; no model messages")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                deadline = time.monotonic() + 5
                while process.poll() is None and time.monotonic() < deadline:
                    pump()  # Pi may need its final transcript drained to exit.
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            os.close(master)


if __name__ == "__main__":
    check_wait_race()
    for name in ["light", "dark"]:
        exercise(name)
