"""Deterministic tests for the pi settings merge, the staged suite migration and the pi config
files this repo owns. Fixtures only: nothing reads ~/.pi, runs chezmoi or touches a checkout."""
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "private_dot_pi/private_agent"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "lib"))
import agent_settings as a  # noqa: E402

loader = importlib.machinery.SourceFileLoader("pi_suite_migration", str(ROOT / "lib/pi_suite_migration.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
cli = importlib.util.module_from_spec(spec)
loader.exec_module(cli)

SUITE = "git:github.com/justmytwospence/pi-plugins"
PIN = SUITE + "@e6e4f87cd0c19563741afe70c09f59eb964fdbfd"
STAGED = [
    {"package": "npm:pi-btw", "component": "pi-btw"},
    {"package": "npm:pi-vim", "component": "pi-vim"},
    {"package": "npm:@saadjs/pi-stash", "component": "pi-stash"},
    {"package": "npm:pi-sticky-last-prompt", "component": "pi-sticky-last-prompt"},
]
MIGRATION = {"suite": SUITE, "staged": STAGED, "migrated": []}
AUTORESEARCH = {"source": "npm:pi-autoresearch", "skills": []}
MANAGED_PACKAGES = [
    "npm:@gotgenes/pi-anthropic-auth", "npm:@earendil-works/pi-radius", "npm:pi-web-access",
    "npm:pi-cc-extensions", "npm:pi-btw", "npm:pi-vim", "npm:@saadjs/pi-stash",
    "npm:@juicesharp/rpiv-todo", PIN,
    "git:github.com/justmytwospence/tmux-agents@f7e399ffb85fa0b3e8b6097d3f9af16dce04f0d1",
    "npm:pi-sticky-last-prompt", AUTORESEARCH,
]
RETAINED = ["npm:@gotgenes/pi-anthropic-auth", "npm:@earendil-works/pi-radius", "npm:pi-web-access",
            "npm:pi-cc-extensions", "npm:@juicesharp/rpiv-todo", "npm:pi-autoresearch"]
CURRENT = {"pi-" + n for n in ("ask-user-question plan-mode status-footer rewind clear-screen select-nav "
                               "herdr-scrollbar-width herdr subagents tool-gate bg auto-effort appearance-resync "
                               "copy marimo cache-guard next-prompt diff-review prose-width").split()}
FUTURE = CURRENT | {"pi-btw", "pi-vim", "pi-stash", "pi-sticky-last-prompt"}
# Every tool the suite registers (pi.registerTool names across packages/*/src) plus rpiv-todo's.
SUITE_TOOLS = ["ask_user_question", "bg_kill", "bg_logs", "bg_run", "bg_wait", "herdr_child",
               "plan_ask_planner", "plan_mode_complete", "plan_mode_question", "plan_subagents",
               "plan_submit_merged", "subagent"]


def managed():
    return {"packages": copy.deepcopy(MANAGED_PACKAGES), "defaultModel": "claude-opus-5-5", "theme": "light/dark"}


def live():
    return {"lastChangelogVersion": "1.1.0", "deviceId": "4280ef3d", "theme": "dark",
            "packages": copy.deepcopy(MANAGED_PACKAGES) + ["../../Projects/pi-quiz"]}


class Merge(unittest.TestCase):
    def test_managed_wins_pi_keys_and_local_packages_stay(self):
        out = a.merge_pi_settings(live(), managed())
        self.assertEqual(out["theme"], "light/dark")
        self.assertEqual(out["deviceId"], "4280ef3d")
        self.assertEqual(out["lastChangelogVersion"], "1.1.0")
        self.assertEqual(out["packages"], MANAGED_PACKAGES + ["../../Projects/pi-quiz"])

    def test_absent_live_file_is_the_managed_file(self):
        self.assertEqual(a.merge_pi_settings({}, managed()), managed())

    def test_live_only_package_the_repo_dropped_goes(self):
        current = live()
        current["packages"].append("npm:pi-something-installed-by-hand")
        out = a.merge_pi_settings(current, managed())
        self.assertNotIn("npm:pi-something-installed-by-hand", out["packages"])
        self.assertIn("../../Projects/pi-quiz", out["packages"])

    def test_idempotent(self):
        once = a.merge_pi_settings(live(), managed())
        self.assertEqual(a.merge_pi_settings(copy.deepcopy(once), managed()), once)

    def test_run_json_echoes_unchanged_text_and_rejects_malformed(self):
        text = json.dumps(a.merge_pi_settings(live(), managed()), indent=2) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "x"))
            with open(os.path.join(tmp, "x", "m.json"), "w") as handle:
                json.dump(managed(), handle)
            env = dict(os.environ, CHEZMOI_SOURCE_DIR=tmp)
            code = "import sys; sys.path.insert(0, %r); import agent_settings as a; a.run_json('x/m.json', a.merge_pi_settings)" % str(ROOT / "lib")
            proc = subprocess.run([sys.executable, "-B", "-c", code], input=text, capture_output=True, text=True, env=env)
            self.assertEqual(proc.stdout, text)
            proc = subprocess.run([sys.executable, "-B", "-c", code], input="{not json", capture_output=True, text=True, env=env)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")


class Migration(unittest.TestCase):
    def test_config_file_matches_the_fixture(self):
        config = json.loads((AGENT / "pi-suite-migration.managed.json").read_text())
        self.assertEqual(config["suite"], SUITE)
        staged = config["staged"]
        migrated = [{"package": a.package_source(record["package"]), "component": record["component"]}
                    for record in config["migrated"]]
        self.assertEqual(sorted(staged + migrated, key=lambda entry: entry["package"]),
                         sorted(STAGED, key=lambda entry: entry["package"]))
        settings = json.loads((AGENT / "settings.managed.json").read_text())
        sources = [a.package_source(p) for p in settings["packages"]]
        for entry in staged:
            self.assertIn(entry["package"], sources)
        for entry in migrated:
            self.assertNotIn(entry["package"], sources)
        for source in RETAINED:
            self.assertIn(source, sources)
        self.assertIsNotNone(a.suite_entry(settings["packages"], SUITE))
        # The managed inputs never deploy (.chezmoiignore's **/*.managed.json).
        self.assertIn("**/*.managed.json", (ROOT / ".chezmoiignore").read_text())

    def test_suite_components_reads_the_manifest(self):
        manifest = {"pi": {"extensions": ["./packages/pi-bg/src/index.ts", "./packages/pi-vim/src/index.ts", "./other.ts"]}}
        self.assertEqual(a.suite_components(manifest), {"pi-bg", "pi-vim"})
        self.assertEqual(a.suite_components({}), set())

    def test_suite_entry(self):
        self.assertEqual(a.suite_entry(MANAGED_PACKAGES, SUITE), (8, PIN, PIN.split("@")[1]))
        self.assertIsNone(a.suite_entry(["npm:pi-btw"], SUITE))
        self.assertEqual(a.suite_entry([{"source": SUITE}], SUITE), (0, SUITE, None))

    def test_staged_is_a_no_op_until_the_suite_provides_the_components(self):
        self.assertEqual(a.suite_duplicates(MANAGED_PACKAGES, CURRENT, STAGED), [])
        packages, moved, pending = a.migrate_to_suite(copy.deepcopy(MANAGED_PACKAGES), CURRENT, MIGRATION)
        self.assertEqual(packages, MANAGED_PACKAGES)
        self.assertEqual(moved, [])
        self.assertEqual(pending, STAGED)

    def test_duplicates_are_the_staged_externals_the_suite_now_provides(self):
        self.assertEqual([d["package"] for d in a.suite_duplicates(MANAGED_PACKAGES, FUTURE, STAGED)],
                         ["npm:pi-btw", "npm:pi-vim", "npm:@saadjs/pi-stash", "npm:pi-sticky-last-prompt"])
        partial = CURRENT | {"pi-vim"}
        self.assertEqual([d["package"] for d in a.suite_duplicates(MANAGED_PACKAGES, partial, STAGED)], ["npm:pi-vim"])
        # Already migrated: nothing to report.
        without = [p for p in MANAGED_PACKAGES if a.package_source(p) != "npm:pi-vim"]
        self.assertEqual(a.suite_duplicates(without, partial, STAGED), [])

    def test_apply_drops_only_the_provided_ones_and_keeps_order(self):
        packages, moved, pending = a.migrate_to_suite(copy.deepcopy(MANAGED_PACKAGES), CURRENT | {"pi-vim", "pi-btw"}, MIGRATION)
        self.assertEqual(packages, [p for p in MANAGED_PACKAGES if p not in ("npm:pi-vim", "npm:pi-btw")])
        self.assertEqual([(m["package"], m["component"], m["index"], m["suite"]) for m in moved],
                         [("npm:pi-btw", "pi-btw", 4, PIN), ("npm:pi-vim", "pi-vim", 5, PIN)])
        self.assertEqual([p["package"] for p in pending], ["npm:@saadjs/pi-stash", "npm:pi-sticky-last-prompt"])
        self.assertIn(AUTORESEARCH, packages)
        self.assertIn(PIN, packages)

    def test_apply_of_the_future_revision_leaves_the_six_retained_dependencies(self):
        packages, moved, pending = a.migrate_to_suite(copy.deepcopy(MANAGED_PACKAGES), FUTURE, MIGRATION)
        self.assertEqual([a.package_source(p) for p in packages if a.package_source(p).startswith("npm:")], RETAINED)
        self.assertEqual(len(moved), 4)
        self.assertEqual(pending, [])
        self.assertEqual(a.suite_duplicates(packages, FUTURE, STAGED), [])
        # Idempotent.
        again, moved_again, _ = a.migrate_to_suite(copy.deepcopy(packages), FUTURE, MIGRATION)
        self.assertEqual(again, packages)
        self.assertEqual(moved_again, [])

    def test_apply_requires_the_suite_pin(self):
        with self.assertRaises(ValueError):
            a.migrate_to_suite(["npm:pi-btw"], FUTURE, MIGRATION)

    def test_rollback_restores_the_exact_original_list(self):
        for components in (FUTURE, CURRENT | {"pi-vim"}, CURRENT | {"pi-btw", "pi-sticky-last-prompt"}):
            packages, moved, _ = a.migrate_to_suite(copy.deepcopy(MANAGED_PACKAGES), components, MIGRATION)
            self.assertEqual(a.rollback_from_suite(packages, moved), MANAGED_PACKAGES)
            # Twice is once.
            self.assertEqual(a.rollback_from_suite(a.rollback_from_suite(packages, moved), moved), MANAGED_PACKAGES)

    def test_rollback_with_a_shorter_list_appends(self):
        moved = [{"package": "npm:pi-btw", "component": "pi-btw", "index": 9, "suite": PIN}]
        self.assertEqual(a.rollback_from_suite(["npm:a"], moved), ["npm:a", "npm:pi-btw"])

    def test_live_state_survives_migration_and_rollback_through_the_merge(self):
        current = live()
        current["packages"].append({"source": "/Users/me/Projects/pi-local", "extensions": []})
        before = a.merge_pi_settings(copy.deepcopy(current), managed())
        packages, moved, _ = a.migrate_to_suite(copy.deepcopy(MANAGED_PACKAGES), FUTURE, MIGRATION)
        migrated = dict(managed(), packages=packages)
        after = a.merge_pi_settings(copy.deepcopy(before), migrated)
        for key in ("deviceId", "lastChangelogVersion"):
            self.assertEqual(after[key], before[key])
        self.assertEqual(after["packages"][-2:], before["packages"][-2:])  # pi-quiz and the local checkout
        for entry in STAGED:
            self.assertNotIn(entry["package"], [a.package_source(p) for p in after["packages"]])
        restored = dict(managed(), packages=a.rollback_from_suite(packages, moved))
        back = a.merge_pi_settings(copy.deepcopy(after), restored)
        self.assertEqual(back, before)


class MigrationCli(unittest.TestCase):
    """The command against a copy of the two managed files; the real source tree is never written."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        src = Path(self.tmp.name) / "private_dot_pi/private_agent"
        src.mkdir(parents=True)
        (src / "settings.managed.json").write_text(json.dumps(managed(), indent=2, ensure_ascii=False) + "\n")
        (src / "pi-suite-migration.managed.json").write_text(json.dumps(MIGRATION, indent=2) + "\n")
        self.src = src
        self.old = os.environ.get("CHEZMOI_SOURCE_DIR")
        os.environ["CHEZMOI_SOURCE_DIR"] = self.tmp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("CHEZMOI_SOURCE_DIR", None)
        else:
            os.environ["CHEZMOI_SOURCE_DIR"] = self.old
        self.tmp.cleanup()

    def settings(self):
        return json.loads((self.src / "settings.managed.json").read_text())

    def migration(self):
        return json.loads((self.src / "pi-suite-migration.managed.json").read_text())

    def run_cli(self, *argv):
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_check_pending_then_duplicates(self):
        code, out = self.run_cli("check", "--components", ",".join(sorted(CURRENT)))
        self.assertEqual(code, 0)
        self.assertEqual(out.count("pending:"), 4)
        self.assertNotIn("duplicate:", out)
        code, out = self.run_cli("check", "--components", ",".join(sorted(FUTURE)))
        self.assertEqual(code, 1)
        self.assertEqual(out.count("duplicate:"), 4)

    def test_apply_then_rollback_round_trips_both_files(self):
        before_settings, before_migration = self.settings(), self.migration()
        code, out = self.run_cli("apply", "--dry-run", "--components", ",".join(FUTURE))
        self.assertEqual(code, 0)
        self.assertEqual(self.settings(), before_settings)
        code, out = self.run_cli("apply", "--components", ",".join(FUTURE))
        self.assertEqual(code, 0)
        self.assertEqual(self.settings()["packages"][4:], ["npm:@juicesharp/rpiv-todo", PIN, MANAGED_PACKAGES[9], AUTORESEARCH])
        self.assertEqual(self.settings()["defaultModel"], "claude-opus-5-5")
        self.assertEqual(self.migration()["staged"], [])
        self.assertEqual([m["package"] for m in self.migration()["migrated"]], [s["package"] for s in STAGED])
        code, out = self.run_cli("check", "--components", ",".join(FUTURE))
        self.assertEqual(code, 0)
        self.assertEqual(out.count("migrated:"), 4)
        code, out = self.run_cli("apply", "--components", ",".join(FUTURE))
        self.assertIn("nothing to migrate", out)
        code, out = self.run_cli("rollback")
        self.assertEqual(code, 0)
        self.assertEqual(self.settings(), before_settings)
        self.assertEqual(self.migration(), before_migration)
        self.assertEqual((self.src / "settings.managed.json").read_text(),
                         json.dumps(before_settings, indent=2, ensure_ascii=False) + "\n")

    def test_partial_revision_migrates_part_and_keeps_the_rest_staged(self):
        code, _ = self.run_cli("apply", "--components", ",".join(CURRENT | {"pi-stash"}))
        self.assertEqual(code, 0)
        self.assertNotIn("npm:@saadjs/pi-stash", self.settings()["packages"])
        self.assertIn("npm:pi-btw", self.settings()["packages"])
        self.assertEqual([s["package"] for s in self.migration()["staged"]], ["npm:pi-btw", "npm:pi-vim", "npm:pi-sticky-last-prompt"])
        code, out = self.run_cli("check", "--components", ",".join(CURRENT | {"pi-stash"}))
        self.assertEqual(code, 0)
        self.assertEqual(out.count("pending:"), 3)


class PiConfigFiles(unittest.TestCase):
    def test_keybindings_select_model_on_alt_p_and_alt_m_with_cycling_off(self):
        keys = json.loads((AGENT / "keybindings.json").read_text())
        self.assertEqual(keys["app.model.select"], ["alt+p", "alt+m"])
        self.assertEqual(keys["app.model.cycleForward"], [])
        self.assertEqual(keys["app.model.cycleBackward"], [])
        # The other assignments stay as they were.
        self.assertEqual(keys["app.thinking.cycle"], "alt+t")
        self.assertEqual(keys["tui.editor.historyPrevious"], "ctrl+p")
        self.assertEqual(keys["tui.select.up"], ["up", "ctrl+k"])
        self.assertEqual(keys["tui.select.down"], ["down", "ctrl+j"])
        # No global half-page scroll on ctrl+u/ctrl+d: they stay the editor's and pi-vim's.
        bound = {k for v in keys.values() for k in ([v] if isinstance(v, str) else v)}
        self.assertNotIn("ctrl+u", bound)
        self.assertNotIn("ctrl+d", bound)
        self.assertNotIn("tui.altScreen.halfPageUp", keys)
        self.assertNotIn("tui.altScreen.halfPageDown", keys)

    def test_cc_extensions_leaves_suite_tools_the_footer_and_subagent_mentions_alone(self):
        config = json.loads((AGENT / "pi-cc-extensions.json").read_text())
        self.assertIs(config["enableCustomFooter"], False)
        self.assertIs(config["enableSubagentAutocomplete"], False)
        self.assertEqual(config["inputClip"], 500)
        self.assertEqual(config["excludeRenderers"], sorted(SUITE_TOOLS + ["todo"]))

    @unittest.skipUnless(os.path.isdir(os.path.join(cli.CHECKOUT, "packages")), "no suite checkout to cross-check")
    def test_suite_tools_list_matches_the_checkout(self):
        """Read-only cross-check of SUITE_TOOLS against the development checkout, when present."""
        names = set()
        for path in Path(cli.CHECKOUT, "packages").glob("*/src/**/*.ts"):
            text = path.read_text()
            for match in re.finditer(r"registerTool\(\{\s*name:\s*([A-Za-z_\"']+)", text):
                token = match.group(1)
                if token.startswith(("'", '"')):
                    names.add(token.strip("'\""))
                else:
                    const = re.search(r"(?:const|export const)\s+%s\s*=\s*[\"']([a-z_]+)[\"']" % re.escape(token), text)
                    if const is None:
                        for other in Path(cli.CHECKOUT, "packages", path.relative_to(Path(cli.CHECKOUT, "packages")).parts[0], "src").rglob("*.ts"):
                            const = re.search(r"(?:const|export const)\s+%s\s*=\s*[\"']([a-z_]+)[\"']" % re.escape(token), other.read_text())
                            if const:
                                break
                    self.assertIsNotNone(const, "could not resolve tool name %s in %s" % (token, path))
                    names.add(const.group(1))
        self.assertEqual(names, set(SUITE_TOOLS))


if __name__ == "__main__":
    unittest.main()
