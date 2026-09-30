"""Run: python3 -B -m unittest discover -s tests -p test_herdr_navigation.py -v."""

import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

try:
    import tomllib
except ImportError:
    tomllib = None  # NUC's Python 3.9: use `herdr config check` there.

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("picker", str(ROOT / "shell/.local/bin/herdr-space-picker"))
spec = importlib.util.spec_from_loader(loader.name, loader)
picker = importlib.util.module_from_spec(spec)
loader.exec_module(picker)


def spaces(*entries):
    return {"workspaces": list(entries)}


def space(wid, label="same", **extra):
    return {"workspace_id": wid, "label": label, **extra}


class PickerTest(unittest.TestCase):
    def test_duplicate_labels_child_agentless_and_layout_order(self):
        mapping, lines = picker.rows(spaces(space("w9"), space("w1", worktree={
            "repo_name": "project", "checkout_path": "/repo/.worktrees/child"}),
            space("w2", "no agents", pane_count=1)))
        self.assertEqual(list(mapping.values()), ["w9", "w1", "w2"])
        self.assertIn("project", lines[1])
        self.assertIn(".worktrees/child", lines[1])
        with patch.object(picker, "call", side_effect=[spaces(space("w9"), space("w1")),
                                                     spaces(space("w9"), space("w1")), {}]) as call:
            with patch.object(picker, "choose", return_value="1"):
                picker.run()
        self.assertEqual(call.call_args.args, ("workspace", "focus", "w1"))

    def test_unicode_whitespace_control_and_shell_text(self):
        text = 'é space $(touch /tmp/no) "\t\n\x1b[31m\u202e'
        _, lines = picker.rows(spaces(space("w1", text, worktree={"checkout_path": text})))
        self.assertEqual(lines[0].count("\t"), 1)
        self.assertNotIn("\n", lines[0])
        self.assertNotIn("\x1b", lines[0])
        self.assertNotIn("\u202e", lines[0])
        self.assertIn("é space $(touch /tmp/no)", lines[0])

    def test_malformed_and_duplicate_ids(self):
        for result in ({}, spaces(None), spaces(space("")), spaces({"workspace_id": "w1"}),
                       spaces(space("w1"), space("w1"))):
            with self.subTest(result=result), self.assertRaises(picker.PickerError):
                picker.rows(result)

    def test_cancel_and_empty_do_not_focus(self):
        with patch.object(picker, "call", return_value=spaces(space("w1"))) as call:
            with patch.object(picker, "choose", return_value=None):
                self.assertEqual(picker.run(), 0)
            self.assertEqual(call.call_count, 1)
        with patch.object(picker, "call", return_value=spaces()), self.assertRaisesRegex(
                picker.PickerError, "No open spaces"):
            picker.run()

    def test_vanished_selection_does_not_substitute(self):
        with patch.object(picker, "call", side_effect=[spaces(space("w1")), spaces(space("w2"))]) as call:
            with patch.object(picker, "choose", return_value="0"), self.assertRaisesRegex(
                    picker.PickerError, "closed"):
                picker.run()
            self.assertEqual(call.call_count, 2)

    def test_fzf_dependency_cancellation_errors_and_inherited_overrides(self):
        with patch.object(picker.shutil, "which", return_value=None), self.assertRaisesRegex(
                picker.PickerError, "Install fzf"):
            picker.choose(["0\tspace"])
        for rc in (1, 130, 2, 0):
            with patch.object(picker.shutil, "which", return_value="/bin/fzf"), patch.dict(
                    os.environ, {"FZF_DEFAULT_OPTS": "--bind enter:execute(bad)",
                                 "FZF_DEFAULT_OPTS_FILE": "/tmp/bad"}), patch.object(
                    picker.subprocess, "run", return_value=subprocess.CompletedProcess([], rc, "0\tspace\n")) as run:
                if rc == 2:
                    with self.assertRaises(picker.PickerError):
                        picker.choose(["0\tspace"])
                else:
                    self.assertEqual(picker.choose(["0\tspace"]), "0" if rc == 0 else None)
                self.assertFalse(any(k.startswith("FZF_") for k in run.call_args.kwargs["env"]))
                argv = run.call_args.args[0]
                self.assertIn("--no-select-1", argv)
                self.assertIn("--no-exit-0", argv)
                self.assertIn("--tiebreak=index", argv)
                # --nth addresses the transformed (--with-nth) display, not
                # the original opaque-ID field. Search every displayed field.
                self.assertIn("--nth=1..", argv)

    def test_invalid_selection(self):
        with patch.object(picker.shutil, "which", return_value="fzf"), patch.object(
                picker.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "bogus\n")), self.assertRaises(
                picker.PickerError):
            picker.choose(["0\tspace"])

    def test_cli_argv_socket_context_api_errors_and_timeouts(self):
        with patch.dict(os.environ, {"HERDR_BIN_PATH": "/some path/herdr", "HERDR_SOCKET_PATH": "/named/socket"}), patch.object(
                picker.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, '{"result":{}}')) as run:
            picker.call("workspace", "focus", "opaque;$(bad)")
            self.assertEqual(run.call_args.args[0], ["/some path/herdr", "workspace", "focus", "opaque;$(bad)"])
            self.assertNotIn("shell", run.call_args.kwargs)
            self.assertNotIn("env", run.call_args.kwargs)  # selected-server context inherited
        for stdout in ("not json", '[]', '{"error":{}}', '{"result":[]}'):
            with patch.object(picker.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout)), self.assertRaises(
                    picker.PickerError):
                picker.call("workspace", "list")
        with patch.object(picker.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "socket missing")), self.assertRaisesRegex(
                picker.PickerError, "socket missing"):
            picker.call("workspace", "list")
        with patch.object(picker.subprocess, "run", side_effect=subprocess.TimeoutExpired("herdr", 10)), self.assertRaises(
                picker.PickerError):
            picker.call("workspace", "list")

    def test_errors_remain_visible_and_ctrl_c_cancels(self):
        with patch.object(picker, "run", side_effect=picker.PickerError("problem")), patch(
                "builtins.input", return_value="") as wait, patch("builtins.print") as message:
            self.assertEqual(picker.main(), 1)
            wait.assert_called_once()
            self.assertIn("problem", message.call_args.args[0])
        with patch.object(picker, "run", side_effect=KeyboardInterrupt):
            self.assertEqual(picker.main(), 0)


@unittest.skipIf(tomllib is None, "tomllib requires Python 3.11+")
class ConfigTest(unittest.TestCase):
    def test_parity_and_nonconflicting_keys(self):
        maps = []
        for host in ("osx", "nuc", "exe"):
            with (ROOT / host / ".config/herdr/config.toml").open("rb") as f:
                keys = tomllib.load(f)["keys"]
            maps.append(keys)
            expanded = []
            for name, values in keys.items():
                if name in ("prefix", "command"):
                    continue
                for value in values if isinstance(values, list) else [values]:
                    if value:
                        expanded += [value.replace("1..9", str(i)) for i in range(1, 10)] if "1..9" in value else [value]
            commands = {c["key"]: c for c in keys["command"]}
            expanded += [c["key"] for c in keys["command"]]
            self.assertEqual(len(expanded), len(set(expanded)), host)
            self.assertEqual(keys["prefix"], "ctrl+b")
            self.assertEqual(commands["prefix+alt+n"]["command"], "attention-queue.next-attention")
            self.assertEqual(commands["prefix+alt+p"]["command"], "attention-queue.previous-attention")
            self.assertEqual(commands["prefix+f"]["type"], "popup")
            self.assertEqual(commands["prefix+f"]["width"], "80%")
            self.assertEqual(commands["prefix+f"]["height"], "60%")
        self.assertEqual(maps[0], maps[1])
        self.assertEqual(maps[0], maps[2])


if __name__ == "__main__":
    unittest.main()
