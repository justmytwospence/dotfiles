"""Unit/safety/config checks for the navigation and everything fzf popups."""
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
try:
    import tomllib
except ImportError:
    tomllib = None

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("picker", str(ROOT / "shell/.local/bin/herdr-space-picker"))
spec = importlib.util.spec_from_loader(loader.name, loader)
picker = importlib.util.module_from_spec(spec)
loader.exec_module(picker)


def snapshot():
    return {"workspaces": [
        {"workspace_id": "w9", "label": "same"},
        {"workspace_id": "w1", "label": "same", "worktree": {"repo_name": "project", "checkout_path": "/repo/.worktrees/child"}},
        {"workspace_id": "w2", "label": "no agents"}],
        "tabs": [{"workspace_id": "w9", "tab_id": "w9:t1", "label": "navigation"},
                 {"workspace_id": "w9", "tab_id": "w9:t2", "label": "logs"},
                 {"workspace_id": "w1", "tab_id": "w1:t1", "label": "logs"}],
        "panes": [{"workspace_id": "w9", "tab_id": "w9:t1", "pane_id": "w9:p1", "terminal_id": "terminal1", "cwd": "/repo"},
                  {"workspace_id": "w9", "tab_id": "w9:t2", "pane_id": "w9:p2", "terminal_id": "terminal2"}],
        "agents": [{"workspace_id": "w9", "tab_id": "w9:t1", "pane_id": "w9:p1", "terminal_id": "terminal1", "agent": "pi",
                    "agent_session": {"value": "session1"}, "name": "reviewer", "tokens": {"attn": "blocked"}}]}


def action(name="next-attention", plugin="attention-queue", contexts=None):
    return {"plugin_id": plugin, "action_id": name, "title": name, "contexts": contexts or ["global"], "command": [name]}


class PickerTest(unittest.TestCase):
    def setUp(self):
        self.snap = snapshot()
        self.context = {"workspace_id": "w9", "tab_id": "w9:t1", "focused_pane_id": "w9:p1", "invocation_source": "cli"}

    def commands(self, actions=None):
        return picker.command_entries(self.context, actions or [], {})

    def test_grouped_space_tabs_duplicate_names_agentless_child_and_layout(self):
        entries = picker.navigation_entries(self.snap)
        self.assertEqual([e["id"] for e in entries], ["w9", "w9:t1", "w9:t2", "w1", "w1:t1", "w2"])
        mapping, lines = picker.rows(entries)
        self.assertIn("project", lines[3])
        self.assertIn(".worktrees/child", lines[3])
        self.assertIn("same / logs", lines[4])
        self.assertEqual(mapping["4"]["id"], "w1:t1")
        with patch.object(picker, "read_snapshot", return_value=self.snap), patch.object(picker, "choose", return_value="4"), patch.object(picker, "api") as api:
            picker.run()
            api.assert_called_once_with("tab.focus", {"tab_id": "w1:t1"})

    def test_everything_includes_exact_agent_pane_and_searchable_paths(self):
        entries = picker.navigation_entries(self.snap, True)
        self.assertEqual([e["kind"] for e in entries[:5]], ["space", "tab", "agent", "tab", "pane"])
        self.assertIn("reviewer", entries[2]["label"])
        self.assertIn("blocked", entries[2]["label"])
        self.assertIn("/repo", entries[2]["label"])
        with patch.object(picker, "read_snapshot", return_value=self.snap), patch.object(picker, "api") as api:
            picker.execute(entries[2], self.snap)
            api.assert_called_once_with("agent.focus", {"target": "w9:p1"})

    def test_unicode_whitespace_controls_and_shell_text_are_display_only(self):
        text = 'é $(touch /tmp/no) "\t\n\x1b[31m\u202e'
        self.snap["workspaces"][0]["label"] = text
        _, lines = picker.rows(picker.navigation_entries(self.snap))
        self.assertEqual(lines[0].count("\t"), 1)
        for control in ("\n", "\x1b", "\u202e"):
            self.assertNotIn(control, lines[0])
        self.assertIn("é $(touch /tmp/no)", lines[0])

    def test_malformed_and_duplicate_entities(self):
        for name, key in (("workspaces", "workspace_id"), ("tabs", "tab_id"), ("panes", "pane_id"), ("agents", "pane_id")):
            for bad in (None, [None], [{key: ""}], [{key: "same"}, {key: "same"}]):
                snap = copy.deepcopy(self.snap)
                snap[name] = bad
                with self.subTest(name=name, bad=bad), self.assertRaises(picker.PickerError):
                    picker.navigation_entries(snap)

    def test_cancel_empty_and_no_source_do_not_mutate(self):
        with patch.object(picker, "read_snapshot", return_value=self.snap), patch.object(picker, "choose", return_value=None), patch.object(picker, "api") as api:
            self.assertEqual(picker.run(), 0)
            api.assert_not_called()
        empty = {k: [] for k in self.snap}
        with patch.object(picker, "read_snapshot", return_value=empty), self.assertRaisesRegex(picker.PickerError, "No open spaces"):
            picker.run()
        entries = picker.command_entries({}, [], {})
        self.assertFalse(any(e.get("method") == "pane.close" for e in entries))

    def test_closed_moved_replaced_destinations_never_substitute(self):
        entries = picker.navigation_entries(self.snap, True)
        for target, change in ((entries[0], "closed"), (entries[1], "moved"), (entries[2], "replaced")):
            current = copy.deepcopy(self.snap)
            if change == "closed":
                current["workspaces"] = []
            elif change == "moved":
                current["tabs"][0]["workspace_id"] = "w2"
            else:
                current["agents"][0]["agent_session"] = {"value": "other"}
            with patch.object(picker, "read_snapshot", return_value=current), patch.object(picker, "api") as api, self.assertRaises(picker.PickerError):
                picker.execute(target, self.snap)
            api.assert_not_called()

    def test_invocation_is_explicit_popup_context_not_server_focus(self):
        with patch.dict(os.environ, {"HERDR_ACTIVE_PANE_ID": "w9:p1", "HERDR_PANE_ID": "unrelated"}, clear=True):
            context = picker.invocation(self.snap)
            self.assertEqual(context["focused_pane_id"], "w9:p1")
            self.assertEqual(context["tab_id"], "w9:t1")
        with patch.dict(os.environ, {}, clear=True):
            self.assertNotIn("focused_pane_id", picker.invocation(self.snap))

    def test_commands_prompt_for_names_preserve_argv_and_require_confirmation(self):
        rename = next(e for e in self.commands() if e.get("method") == "tab.rename")
        text = 'new $(touch /tmp/no); "name"'
        with patch.object(picker, "read_snapshot", return_value=self.snap), patch("builtins.input", return_value=text), patch.object(picker, "api") as api:
            picker.execute(rename, self.snap)
            api.assert_called_once_with("tab.rename", {"tab_id": "w9:t1", "label": text})
        close = next(e for e in self.commands() if e.get("method") == "pane.close")
        for answer in ("no", "", "yes"):
            with patch.object(picker, "read_snapshot", return_value=self.snap), patch("builtins.input", return_value=answer), patch("builtins.print"), patch.object(picker, "api") as api:
                picker.execute(close, self.snap)
                self.assertEqual(api.call_count, int(answer == "yes"))
        with patch("builtins.input", return_value=""), patch.object(picker, "api") as api:
            picker.execute(rename, self.snap)
            api.assert_not_called()

    def test_context_identity_is_revalidated_after_confirmation(self):
        close = next(e for e in self.commands() if e.get("method") == "pane.close")
        current = copy.deepcopy(self.snap)
        current["agents"][0]["agent_session"] = {"value": "replacement"}
        with patch("builtins.input", return_value="yes"), patch("builtins.print"), patch.object(picker, "read_snapshot", return_value=current), patch.object(picker, "api") as api, self.assertRaises(picker.PickerError):
            picker.execute(close, self.snap)
        api.assert_not_called()

    def test_plugin_discovery_context_confirmation_and_revalidation(self):
        actions = [action(), action("clear"), action("pair", "heeler"), action("selection", contexts=["selection"])]
        entries = picker.command_entries(self.context, actions, {})
        plugins = [e for e in entries if e["kind"] == "plugin"]
        self.assertEqual(len(plugins), 3)
        self.assertFalse(plugins[0]["confirm"])
        self.assertTrue(plugins[1]["confirm"])
        self.assertTrue(any("context unavailable" in e["label"] for e in entries))
        with patch.object(picker, "read_snapshot", return_value=self.snap), patch.object(picker, "call", return_value={"actions": actions}), patch.object(picker, "api") as api:
            picker.execute(plugins[0], self.snap)
            self.assertEqual(api.call_args.args[1]["context"], self.context)
        with patch.object(picker, "read_snapshot", return_value=self.snap), patch.object(picker, "call", return_value={"actions": []}), patch.object(picker, "api") as api, self.assertRaises(picker.PickerError):
            picker.execute(plugins[0], self.snap)
        api.assert_not_called()

    def test_native_hints_do_not_inject_keys_and_cycle_commands_target_exact_ids(self):
        commands = self.commands()
        hint = next(e for e in commands if e["kind"] == "hint" and "Settings" in e["label"])
        with patch("builtins.input", return_value=""), patch("builtins.print"), patch.object(picker, "api") as api:
            picker.execute(hint, self.snap)
            api.assert_not_called()
        cycle = next(e for e in commands if e["kind"] == "cycle" and e["scope"] == "tab" and e["direction"] == 1)
        with patch.object(picker, "read_snapshot", return_value=self.snap), patch.object(picker, "api") as api:
            picker.execute(cycle, self.snap)
            api.assert_called_once_with("tab.focus", {"tab_id": "w9:t2"})

    def test_everything_mode_catalog_and_native_bindings(self):
        with patch.object(picker, "read_snapshot", return_value=self.snap), patch.object(picker, "call", return_value={"actions": [action()]}), patch.object(picker, "bindings", return_value={"settings": "prefix+shift+s"}), patch.object(picker, "choose", return_value=None) as choose:
            picker.run("everything")
            lines = choose.call_args.args[0]
            self.assertEqual(choose.call_args.args[1], "everything")
            self.assertTrue(any("reviewer" in x for x in lines))
            self.assertTrue(any("Command  New space" in x for x in lines))
            self.assertTrue(any("attention-queue.next-attention" in x for x in lines))
        with patch.dict(os.environ, {"HERDR_CONFIG_PATH": str(ROOT / "osx/.config/herdr/config.toml")}):
            self.assertEqual(picker.bindings()["settings"], "prefix+shift+s")

    def test_fzf_safe_options_cancellation_and_output_validation(self):
        with patch.object(picker.shutil, "which", return_value=None), self.assertRaisesRegex(picker.PickerError, "Install fzf"):
            picker.choose(["0\tspace"])
        for rc in (0, 1, 130, 2):
            with patch.object(picker.shutil, "which", return_value="fzf"), patch.dict(os.environ, {"FZF_DEFAULT_OPTS": "--bind enter:execute(bad)", "FZF_DEFAULT_OPTS_FILE": "/tmp/bad"}), patch.object(picker.subprocess, "run", return_value=subprocess.CompletedProcess([], rc, "0\tspace\n")) as run:
                if rc == 2:
                    with self.assertRaises(picker.PickerError):
                        picker.choose(["0\tspace"])
                else:
                    self.assertEqual(picker.choose(["0\tspace"]), "0" if rc == 0 else None)
                self.assertFalse(any(k.startswith("FZF_") for k in run.call_args.kwargs["env"]))
                for option in ("--no-select-1", "--no-exit-0", "--nth=1..", "--tiebreak=index"):
                    self.assertIn(option, run.call_args.args[0])
        with patch.object(picker.shutil, "which", return_value="fzf"), patch.object(picker.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "invalid")), self.assertRaises(picker.PickerError):
            picker.choose(["0\tspace"])

    def test_cli_context_and_api_failures(self):
        with patch.dict(os.environ, {"HERDR_BIN_PATH": "/some path/herdr"}), patch.object(picker.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, '{"result":{}}')) as run:
            picker.call("api", "snapshot")
            self.assertEqual(run.call_args.args[0], ["/some path/herdr", "api", "snapshot"])
            self.assertNotIn("shell", run.call_args.kwargs)
        for reply in ("invalid", "[]", '{"error":{}}', '{"result":[]}'):
            with patch.object(picker.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, reply)), self.assertRaises(picker.PickerError):
                picker.call("api", "snapshot")
        with patch.object(picker.subprocess, "run", side_effect=subprocess.TimeoutExpired("herdr", 10)), self.assertRaises(picker.PickerError):
            picker.call("api", "snapshot")
        with patch.dict(os.environ, {"HERDR_SOCKET_PATH": "/tmp/no-picker-socket"}), self.assertRaisesRegex(picker.PickerError, "not retrying"):
            picker.api("pane.focus", {"pane_id": "one"})

    def test_errors_visible_and_usage_validation(self):
        with patch.object(picker.sys, "argv", ["picker"]), patch.object(picker, "run", side_effect=picker.PickerError("problem")), patch("builtins.input", return_value="") as wait, patch("builtins.print"):
            self.assertEqual(picker.main(), 1)
            wait.assert_called_once()
        with patch.object(picker.sys, "argv", ["picker", "bad"]), patch("builtins.print"):
            self.assertEqual(picker.main(), 2)


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
            self.assertEqual(keys["next_workspace"], "prefix+n")
            self.assertEqual(keys["previous_workspace"], "prefix+p")
            self.assertEqual(commands["prefix+ctrl+n"]["command"], "attention-queue.next-attention")
            self.assertEqual(commands["prefix+ctrl+p"]["command"], "attention-queue.previous-attention")
            self.assertIn("everything", commands["prefix+space"]["command"])
            self.assertEqual(commands["prefix+f"]["type"], "popup")
            self.assertEqual(keys["prefix"], "ctrl+b")
        self.assertEqual(maps[0], maps[1])
        self.assertEqual(maps[0], maps[2])


if __name__ == "__main__":
    unittest.main()
