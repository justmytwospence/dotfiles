"""Native installer rendering and archive deployment tests; temporary homes only."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHEZMOI = shutil.which("chezmoi")


@unittest.skipUnless(CHEZMOI, "chezmoi is not installed")
class Deployment(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.config = self.base / "chezmoi.toml"
        self.configure("mac-pro")

    def configure(self, host):
        self.config.write_text('[data]\nhost = %s\nrole = "pro"\nextras = ""\n' % json.dumps(host))

    def render(self, path):
        return subprocess.check_output([
            CHEZMOI, "--config", str(self.config), "--source", str(ROOT),
            "execute-template", "--file", str(ROOT / path),
        ], text=True)

    def run_script(self, script, setup=""):
        path = self.base / "script.sh"
        path.write_text(script)
        subprocess.run(["bash", "-n", str(path)], check=True)
        return subprocess.run(["bash", "-c", setup + '\nsource "$1"', "test", str(path)],
                              env=dict(os.environ, HOME=str(self.home)), capture_output=True, text=True)

    def test_heeler_retirement_and_phone_setup(self):
        for host in ("mac-pro", "mac-air", "nuc", "agentbox-box"):
            with self.subTest(host=host):
                self.configure(host)
                phone = self.render(".chezmoiscripts/run_once_after_60-phone.sh.tmpl")
                self.assertNotIn("heeler", phone.lower())
                self.assertEqual("paseo-setup" in phone, host.startswith("mac-"))
                self.assertNotIn("orca", phone.lower())
                if phone.strip():
                    self.assertTrue(phone.startswith("#!/bin/bash\n"), repr(phone[:40]))
                subprocess.run(["bash", "-n"], input=phone, text=True, check=True)
                retired = self.render(".chezmoiscripts/run_onchange_after_85-retired.sh.tmpl")
                digest = hashlib.sha256((ROOT / "lib/retire_heeler.py").read_bytes()).hexdigest()
                self.assertIn("# Heeler cleanup " + digest, retired)
                invocation = next(line for line in retired.splitlines() if line.startswith("python3 ") and "retire_heeler.py" in line)
                self.assertTrue(invocation.endswith(" || exit $?"))
                result = self.run_script(invocation, "python3() { return 27; }")
                self.assertEqual(result.returncode, 27)
                subprocess.run(["bash", "-n"], input=retired, text=True, check=True)

    def test_host_branches_and_targeted_pi_updates(self):
        packages = json.loads((ROOT / "private_dot_pi/private_agent/settings.managed.json").read_text())["packages"]
        sources = [p if isinstance(p, str) else p["source"] for p in packages]
        for host in ("mac-pro", "mac-air", "nuc", "agentbox-box"):
            with self.subTest(host=host):
                self.configure(host)
                script = self.render(".chezmoiscripts/run_onchange_after_40-plugins.sh.tmpl")
                for source in sources:
                    if source.startswith("git:"):
                        self.assertIn('pi update "%s"' % source, script)
                self.assertNotIn("pi update --extensions", script)
                self.assertNotIn("plugins sync", script)
                self.assertEqual("herdr plugin install madarco/agentbox" in script, host.startswith("mac-"))
                self.assertEqual("herdr plugin install justmytwospence/herdr-agentbox" in script, host == "nuc")
                self.assertNotIn("Heeler", script)
                result = self.run_script(script, 'pi() { return 0; }; herdr() { return 0; }')
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_all_host_script_and_config_syntax(self):
        for host in ("mac-pro", "mac-air", "nuc", "agentbox-box"):
            self.configure(host)
            for path in sorted((ROOT / ".chezmoiscripts").glob("*.tmpl")):
                with self.subTest(host=host, script=path.name):
                    rendered = self.render(str(path.relative_to(ROOT)))
                    if path.name.endswith(".py.tmpl"):
                        compile(rendered, path.name, "exec")
                    else:
                        subprocess.run(["bash", "-n"], input=rendered, text=True, check=True)
            with self.subTest(host=host, config="herdr"):
                tomllib.loads(self.render("dot_config/herdr/config.toml.tmpl"))
            if host.startswith("mac-") and shutil.which("ruby"):
                subprocess.run(["ruby", "-c"], input=self.render("dot_Brewfile.tmpl"),
                               text=True, check=True, capture_output=True)

    def test_native_installer_failure_is_not_swallowed(self):
        script = self.render(".chezmoiscripts/run_onchange_after_40-plugins.sh.tmpl")
        result = self.run_script(script, 'pi() { return 19; }; herdr() { return 0; }')
        self.assertEqual(result.returncode, 19)
        result = self.run_script(script, 'pi() { return 0; }; herdr() { return 23; }')
        self.assertEqual(result.returncode, 23)

    def test_external_pins_and_archive_migration_guards(self):
        externals = tomllib.loads(self.render(".chezmoiexternal.toml.tmpl"))
        plugins = {k: v for k, v in externals.items() if k.startswith((".local/share/plugins/", ".tmux/plugins/"))}
        skills = {k: v for k, v in externals.items() if k.startswith(".agents/skills/")}
        self.assertEqual(set(plugins), {".tmux/plugins/tmux-agents"} | {".local/share/plugins/" + name for name in (
            "anthropic-billing-guard", "claude-auto-effort", "claude-marimo", "claude-cache-guard",
            "claude-prose-width", "claude-tool-gate", "codex-cache-guard", "agent-scrub", "claude-code-playground")})
        self.assertEqual(set(skills), {".agents/skills/find-skills", ".agents/skills/tmux", ".agents/skills/vercel-cli"})
        for target, external in (plugins | skills).items():
            self.assertEqual(external["type"], "archive")
            self.assertTrue(external["exact"])
            self.assertRegex(external["url"], r"/archive/[0-9a-f]{40}\.tar\.gz$")
            self.assertRegex(external["checksum"]["sha256"], r"^[0-9a-f]{64}$")
        tmux_ref = plugins[".tmux/plugins/tmux-agents"]["url"].split("/")[-1].removesuffix(".tar.gz")
        packages = json.loads((ROOT / "private_dot_pi/private_agent/settings.managed.json").read_text())["packages"]
        self.assertIn("git:github.com/justmytwospence/tmux-agents@" + tmux_ref, packages)
        script = self.render(".chezmoiscripts/run_onchange_before_05-plugin-archives.sh.tmpl")
        path = self.home / ".tmux/plugins/tmux-agents"
        path.mkdir(parents=True)
        (path / ".git").mkdir()
        for status, ref in (("?? local.txt", tmux_ref), ("", "f" * 40)):
            with self.subTest(status=status, ref=ref):
                mock = 'git() { case "$*" in *rev-parse*) echo %s ;; *status*) echo %s ;; esac; }' % (ref, json.dumps(status))
                result = self.run_script(script, mock)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Preserve local work", result.stderr)
        mock = 'git() { case "$*" in *rev-parse*) echo %s ;; esac; }' % tmux_ref
        self.assertEqual(self.run_script(script, mock).returncode, 0)
        shutil.rmtree(path)
        path.symlink_to(self.base, target_is_directory=True)
        result = self.run_script(script)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)

    def test_mod_runtime_files_survive_exact_archives(self):
        source = self.base / "source"
        source.mkdir()
        (source / ".chezmoiignore").write_text(self.render(".chezmoiignore"))
        archive = self.base / "mod.tar.gz"
        with tarfile.open(archive, "w:gz") as out:
            for name, content in (("index.ts", b"code\n"), (".claude-plugin/plugin.json", b"{}")):
                member = tarfile.TarInfo("repo/claude-code/mods/token-weather/" + name)
                member.size = len(content)
                out.addfile(member, io.BytesIO(content))
        target = ".local/share/plugins/claude-code-playground"
        (source / ".chezmoiexternal.toml").write_text(
            '["%s"]\ntype = "archive"\nurl = %s\nchecksum.sha256 = "%s"\n'
            'stripComponents = 1\nexact = true\n' % (
                target, json.dumps(archive.as_uri()), hashlib.sha256(archive.read_bytes()).hexdigest()))
        mod = self.home / target / "claude-code/mods/token-weather"
        types = mod / ".claude-plugin/types"
        types.mkdir(parents=True)
        (types / "tsconfig.json").write_text("runtime types")
        (mod / "tsconfig.json").write_text("runtime config")
        (mod / "stale.txt").write_text("remove")
        cmd = [CHEZMOI, "--config", str(self.config), "--source", str(source),
               "--destination", str(self.home), "--cache", str(self.base / "cache"),
               "--persistent-state", str(self.base / "state.boltdb")]
        subprocess.run(cmd + ["apply"], check=True, capture_output=True)
        self.assertEqual((types / "tsconfig.json").read_text(), "runtime types")
        self.assertEqual((mod / "tsconfig.json").read_text(), "runtime config")
        self.assertFalse((mod / "stale.txt").exists())

    def test_skill_archive_filter_and_exact_deployment(self):
        # Exercise chezmoi's real extraction/filter semantics without network access.
        source = self.base / "source"
        source.mkdir()
        archive = self.base / "skill.tar.gz"
        with tarfile.open(archive, "w:gz") as out:
            for name, content in (("repo/skills/tmux/SKILL.md", b"skill\n"),
                                  ("repo/skills/tmux/scripts/run.sh", b"#!/bin/sh\n"),
                                  ("repo/skills/unwanted/SKILL.md", b"other\n")):
                member = tarfile.TarInfo(name)
                member.size = len(content)
                member.mode = 0o755 if name.endswith(".sh") else 0o644
                out.addfile(member, io.BytesIO(content))
        external = tomllib.loads(self.render(".chezmoiexternal.toml.tmpl"))[".agents/skills/tmux"]
        (source / ".chezmoiexternal.toml").write_text(
            '[".agents/skills/tmux"]\ntype = "archive"\nurl = %s\nchecksum.sha256 = "%s"\n'
            'stripComponents = %d\nexact = true\ninclude = %s\n' % (
                json.dumps(archive.as_uri()), hashlib.sha256(archive.read_bytes()).hexdigest(),
                external["stripComponents"], json.dumps(external["include"])))
        target = self.home / ".agents/skills/tmux"
        target.mkdir(parents=True)
        (target / "stale.txt").write_text("old")
        cmd = [CHEZMOI, "--config", str(self.config), "--source", str(source),
               "--destination", str(self.home), "--cache", str(self.base / "cache"),
               "--persistent-state", str(self.base / "state.boltdb")]
        subprocess.run(cmd + ["apply"], check=True, capture_output=True)
        self.assertEqual((target / "SKILL.md").read_text(), "skill\n")
        self.assertTrue(os.access(target / "scripts/run.sh", os.X_OK))
        self.assertFalse((target / "stale.txt").exists())
        self.assertFalse((self.home / ".agents/skills/unwanted").exists())
        subprocess.run(cmd + ["verify"], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
