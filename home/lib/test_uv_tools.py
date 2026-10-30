"""Tests for uv_tools.py: receipt convergence for the release cooldown."""
import datetime
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import uv_tools  # noqa: E402

LIST = """\
cowsay v6.0 [required: ==6.0] [with: six, packaging>=20,<30]
- cowsay
marimo v0.25.1 [with: marimo-lens]
- marimo
httpie v3.2.4 [extras: socks]
- http
coral v0.7.21 [required: git+https://github.com/Human-Agent-Society/CORAL.git@v0.7.21]
- coral
tool v1.0 [with: six==1.16]
- tool
"""

CLEAN = 'exclude-newer = "2026-10-17T00:00:00Z"\nexclude-newer-span = "P7D"\n'
MAINTAINED = {"agent-plugins", "marimo", "marimo-lens"}
NOW = datetime.datetime(2026, 10, 30, tzinfo=datetime.timezone.utc)


def receipt(exemptions=""):
    return CLEAN + ("exclude-newer-package = { %s }\n" % exemptions if exemptions else "")


class Parse(unittest.TestCase):
    def test_list(self):
        tools = {t["name"]: t for t in uv_tools.parse_list(LIST)}
        self.assertEqual(set(tools), {"cowsay", "marimo", "httpie", "coral", "tool"})
        self.assertEqual(tools["cowsay"]["required"], "==6.0")
        self.assertEqual(tools["cowsay"]["with"], ["six", "packaging>=20,<30"])
        self.assertEqual(tools["httpie"]["extras"], "socks")
        self.assertEqual(uv_tools.requirement(tools["coral"], tools["coral"]["required"]),
                         "coral @ git+https://github.com/Human-Agent-Society/CORAL.git@v0.7.21")
        self.assertEqual(uv_tools.requirement(tools["httpie"], ""), "httpie[socks]")

    def test_receipt_exemptions(self):
        got = uv_tools.receipt_exemptions(receipt(
            'cowsay = { timestamp = "2025-01-01T00:00:00Z", span = "P300D" }, marimo = false, '
            'six = "2026-01-01T00:00:01Z"'))
        self.assertEqual(got["marimo"], "false")
        self.assertEqual(got["six"], '"2026-01-01T00:00:01Z"')
        self.assertIn("cowsay", got)
        self.assertEqual(uv_tools.receipt_exemptions(CLEAN), {})


class Plan(unittest.TestCase):
    def tools(self):
        return {t["name"]: t for t in uv_tools.parse_list(LIST)}

    def plan(self, name, text):
        return uv_tools.plan(self.tools()[name], text, MAINTAINED, NOW)

    def test_converged_is_silent(self):
        self.assertEqual(self.plan("httpie", receipt()), (None, []))
        exempt = "agent-plugins = false, marimo = false, marimo-lens = false"
        self.assertEqual(self.plan("marimo", receipt(exempt)), (None, []))
        # A deliberate pin stays.
        self.assertEqual(self.plan("cowsay", receipt()), (None, []))
        # An active cutoff keeps its pin.
        self.assertEqual(self.plan("cowsay", receipt('cowsay = "2026-10-28T00:00:01Z"')), (None, []))

    def test_exempts_maintained(self):
        cmd, reasons = self.plan("marimo", receipt("marimo = false"))
        self.assertEqual(cmd, ["uv", "tool", "install", "marimo", "--with", "marimo-lens",
                               "--exclude-newer-package", "agent-plugins=false",
                               "--exclude-newer-package", "marimo=false",
                               "--exclude-newer-package", "marimo-lens=false"])
        self.assertEqual(reasons, ["exempt maintained packages"])

    def test_unpins_lapsed_fast_forward(self):
        cmd, reasons = self.plan("cowsay", receipt('cowsay = "2026-10-01T00:00:01Z"'))
        self.assertEqual(cmd, ["uv", "tool", "install", "cowsay", "--with", "six", "--with", "packaging>=20,<30"])
        self.assertEqual(reasons, ["cooldown fast-forward lapsed: cowsay"])
        cmd, _ = self.plan("cowsay", receipt('cowsay = "2026-10-01T00:00:01.123456789Z"'))
        self.assertEqual(cmd[3], "cowsay")

    def test_keeps_active_cutoff_on_other_reinstall(self):
        cmd, reasons = self.plan("cowsay", receipt('marimo = "2999-01-01T00:00:00Z", six = "2026-10-28T00:00:01Z"'))
        self.assertEqual(reasons, ["drop retired 2999 sentinels"])
        self.assertEqual(cmd[3], "cowsay==6.0")
        self.assertEqual(cmd[-2:], ["--exclude-newer-package", "six=2026-10-28T00:00:01Z"])
        self.assertFalse(any("2999" in c for c in cmd))

    def test_lapsed_with_pin_is_unpinned(self):
        cmd, _ = self.plan("tool", receipt('six = "2026-10-01T00:00:01Z"'))
        self.assertEqual(cmd, ["uv", "tool", "install", "tool", "--with", "six"])

    def test_drops_retired_sentinels(self):
        cmd, reasons = self.plan("httpie", receipt('marimo = "2999-01-01T00:00:00Z"'))
        self.assertEqual(cmd, ["uv", "tool", "install", "httpie[socks]"])
        self.assertEqual(reasons, ["drop retired 2999 sentinels"])


class Main(unittest.TestCase):
    def test_runs_only_needed_reinstalls(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            tools = tmp / "tools"
            for name, text in {"cowsay": receipt('cowsay = "2026-01-01T00:00:01Z"'), "marimo": receipt(), "httpie": receipt(),
                               "coral": receipt()}.items():
                (tools / name).mkdir(parents=True)
                (tools / name / "uv-receipt.toml").write_text(text)
            (tmp / "list.txt").write_text(LIST)
            uv = tmp / "bin" / "uv"
            uv.parent.mkdir()
            uv.write_text('#!/bin/sh\ncase "$2" in\n  list) cat "%s" ;;\n  dir) echo "%s" ;;\n'
                          '  install) echo "$@" >>"%s"; [ "$3" != marimo ] ;;\nesac\n'
                          % (tmp / "list.txt", tools, tmp / "calls"))
            uv.chmod(uv.stat().st_mode | stat.S_IEXEC)
            env = dict(os.environ, PATH="%s:%s" % (uv.parent, os.environ["PATH"]))
            script = Path(__file__).resolve().parent / "uv_tools.py"
            r = subprocess.run([sys.executable, str(script), "--maintained", ",".join(sorted(MAINTAINED))],
                               env=env, capture_output=True, text=True)
            calls = (tmp / "calls").read_text().splitlines()
            # cowsay is unpinned, marimo exempted (its reinstall fails), the rest untouched.
            self.assertEqual(len(calls), 2, calls)
            self.assertTrue(calls[0].startswith("tool install cowsay --with six"))
            self.assertTrue(calls[1].startswith("tool install marimo --with marimo-lens"))
            self.assertEqual(r.returncode, 1)
            self.assertIn("==> uv tool marimo: exempt maintained packages", r.stdout)


if __name__ == "__main__":
    unittest.main()
