"""Bootstrap/converge rendering and archive deployment tests; temporary homes only."""
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
BASH = "/bin/bash" if os.path.exists("/bin/bash") else "bash"


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
        # macOS runs the scripts with /bin/bash 3.2, which is stricter about empty arrays.
        return subprocess.run([BASH, "-c", setup + '\nsource "$1"', "test", str(path)],
                              env=dict(os.environ, HOME=str(self.home)), capture_output=True, text=True)

    CONVERGE = ".chezmoiscripts/run_after_converge.sh.tmpl"
    HOSTS = ("mac-pro", "mac-air", "nuc", "agentbox-box")

    @staticmethod
    def lib(script):
        """The shared helpers at the top of a rendered converge script."""
        start = script.index('STATE="$HOME')
        end = script.index("\n}\n", script.index("digest() {")) + 3
        return script[start:end]

    def section(self, script, name, setup=""):
        """Run one converge section with mocked commands and print its failures."""
        start = script.index("converge_%s() {" % name)
        call = "run converge_%s\n" % name
        body = script[start:script.index(call, start) + len(call)]
        return self.run_script("set -u\n" + self.lib(script) + setup + "\n" + body
                               + 'echo "failed=${failed[*]+${failed[*]}}"\n')

    def test_converge_sections_per_host(self):
        expected = {
            "retired": set(self.HOSTS),
            "brew_bundle": {"mac-pro", "mac-air"},
            "linux_tools": {"nuc", "agentbox-box"},
            "login_shell": {"mac-pro", "mac-air", "agentbox-box"},
            "pi_packages": set(self.HOSTS),
            "herdr_plugins": {"mac-pro", "mac-air", "nuc"},
            "aac_touchid": {"mac-pro", "mac-air"},
            "herdr_menu": {"mac-pro", "mac-air"},
            "paseo": {"mac-pro", "mac-air"},
            "omnigent_host": {"mac-pro", "mac-air"},
            "macos_defaults": {"mac-pro", "mac-air"},
            "lid_sleep_sudoers": {"mac-pro", "mac-air"},
            "project_mcp": set(self.HOSTS),
        }
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.configure(host)
                script = self.render(self.CONVERGE)
                self.assertTrue(script.startswith("#!/bin/bash\n"))
                for name, hosts in expected.items():
                    self.assertEqual("\nrun converge_%s\n" % name in script, host in hosts, name)
                self.assertEqual("paseo-setup" in script, host.startswith("mac-"))

    def test_heeler_retirement_failure_fails_section(self):
        script = self.render(self.CONVERGE)
        invocation = next(line for line in script.splitlines()
                          if line.startswith("python3 ") and "retire_heeler.py" in line)
        self.assertTrue(invocation.endswith(" || return 1"))
        result = self.run_script("f() {\n%s\n}\nf" % invocation, "python3() { return 27; }")
        self.assertEqual(result.returncode, 1)

    def test_pi_packages_act_only_off_pin(self):
        packages = json.loads((ROOT / "private_dot_pi/private_agent/settings.managed.json").read_text())["packages"]
        sources = [p if isinstance(p, str) else p["source"] for p in packages]
        git = dict(s.removeprefix("git:").split("@") for s in sources if s.startswith("git:"))
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.configure(host)
                script = self.render(self.CONVERGE)
                for source in sources:
                    self.assertIn('pi update "%s"' % source, script)
                self.assertNotIn("pi update --extensions", script)
        self.configure("mac-pro")
        script = self.render(self.CONVERGE)
        for source in sources:
            if source.startswith("npm:"):
                spec = source.removeprefix("npm:")
                at = spec.rfind("@")
                name, version = (spec[:at], spec[at + 1:]) if at > 0 else (spec, "1.0.0")
                package = self.home / ".pi/agent/npm/node_modules" / name
                package.mkdir(parents=True)
                (package / "package.json").write_text('{\n  "version": "%s"\n}\n' % version)
        # Every package present at its pin: pi is never called.
        heads = " ".join('*%s) echo %s ;;' % (path, ref) for path, ref in git.items())
        mock = 'git() { case "$2" in %s esac; }; pi() { echo "pi $*"; }' % heads
        result = self.section(script, "pi_packages", mock)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("pi update", result.stdout)
        self.assertIn("failed=\n", result.stdout)
        # Off pin: only the Git packages are updated, and a failing pi fails the section.
        mock = 'git() { echo 0000; }; pi() { echo "pi $*"; return 19; }'
        result = self.section(script, "pi_packages", mock)
        for path in git:
            self.assertIn("pi update git:%s@" % path, result.stdout)
        self.assertNotIn("pi update npm:", result.stdout)
        self.assertIn("failed=pi_packages", result.stdout)

    def test_herdr_plugins_install_only_missing(self):
        pins = json.loads((ROOT / ".chezmoidata/herdr_plugins.json").read_text())["herdrPlugins"]
        for host in ("mac-pro", "nuc"):
            with self.subTest(host=host):
                self.configure(host)
                script = self.render(self.CONVERGE)
                self.assertEqual("herdr plugin install madarco/agentbox" in script, host.startswith("mac-"))
                self.assertEqual("herdr plugin install justmytwospence/herdr-agentbox" in script, host == "nuc")
                mine = [p for p in pins if host in p["hosts"]]
                listed = "\n".join("- x enabled [github:%s@%s]" % (p["spec"], p["ref"]) for p in mine[1:])
                (self.base / "list.txt").write_text(listed + "\n")
                mock = ('herdr() { if [ "$1 $2" = "plugin list" ]; then cat %s; '
                        'else echo "herdr $*"; return 23; fi; }' % (self.base / "list.txt"))
                result = self.section(script, "herdr_plugins", mock)
                installs = [l for l in result.stdout.splitlines() if l.startswith("herdr plugin install")]
                self.assertEqual(installs, ["herdr plugin install %s --ref %s --yes" % (mine[0]["spec"], mine[0]["ref"])])
                self.assertIn("failed=herdr_plugins", result.stdout)

    def test_omnigent_host_reenables_only_a_stale_or_unloaded_service(self):
        script = self.render(self.CONVERGE)
        bindir = self.base / "bin"
        bindir.mkdir()
        python = bindir / "python"
        python.write_text("#!/bin/sh\n")
        python.chmod(0o755)
        omni = bindir / "omni"
        omni.write_text("#!%s\nimport sys\n" % python)
        omni.chmod(0o755)
        plist = self.home / "Library/LaunchAgents/ai.omnigent.host.plist"
        state = self.base / "plist-python"

        def run(recorded, loaded=True, enable_fixes=True):
            state.write_text(recorded)
            mock = "\n".join([
                'PATH=%s:$PATH' % bindir,
                'plutil() { cat %s; }' % state,
                'launchctl() { %s; }' % ("return 0" if loaded else "return 113"),
                'zsh() { echo "zsh $*"; %s }' % (
                    "printf %%s %s >%s;" % (python, state) if enable_fixes else ""),
            ])
            return self.section(script, "omnigent_host", mock)

        # Never registered: no plist, nothing happens.
        result = run(str(python))
        self.assertEqual(result.stdout, "failed=\n", result.stderr)
        plist.parent.mkdir(parents=True)
        plist.write_text("<plist/>")
        # Current and loaded: silent.
        result = run(str(python))
        self.assertEqual(result.stdout, "failed=\n", result.stderr)
        # Stale keg, or current but unloaded: re-enabled without a browser.
        for recorded, loaded in (("/opt/homebrew/Cellar/omnigent/0.17.0/libexec/bin/python", True),
                                 (str(python), False)):
            result = run(recorded, loaded)
            self.assertIn('zsh -c exec "$0" host enable --non-interactive %s' % omni, result.stdout, result.stderr)
            self.assertTrue(result.stdout.endswith("failed=\n"), result.stdout + result.stderr)
        # Enable that leaves the plist stale fails the section.
        result = run("/gone/python", enable_fixes=False)
        self.assertIn("failed=omnigent_host", result.stdout)

    def test_macos_defaults_write_only_differences(self):
        script = self.render(self.CONVERGE)
        helper = script[script.index("defaults_changed=()"):script.index("converge_macos_defaults() {")]
        mock = "\n".join([
            "defaults() {",
            '    case "$1 $3" in',
            '        "read autohide-time-modifier") echo 0.20 ;;',
            '        "read autohide") echo 1 ;;',
            '        "read mineffect") echo scale ;;',
            '        "read tilesize") echo 64 ;;',
            "        read*) return 1 ;;",
            '        write*) echo "write $2 $3 $5" ;;',
            "    esac",
            "}",
        ])
        calls = "\n".join([
            "ensure_default com.apple.dock autohide-time-modifier -float 0.2",
            "ensure_default com.apple.dock autohide -bool true",
            "ensure_default com.apple.dock mineffect -string scale",
            "ensure_default com.apple.dock tilesize -int 48",
            "ensure_default com.apple.dock launchanim -bool false",
            'echo "changed=${defaults_changed[*]}"',
        ])
        result = self.run_script("set -u\nstep() { :; }\n" + mock + "\n" + helper + calls + "\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        writes = [l for l in result.stdout.splitlines() if l.startswith("write")]
        self.assertEqual(writes, ["write com.apple.dock tilesize 48", "write com.apple.dock launchanim false"])
        self.assertIn("changed=com.apple.dock com.apple.dock", result.stdout)

    def test_macos_defaults_converged_is_silent(self):
        # Every value already set: no write, no restart, no failure (under /bin/bash's set -u).
        script = self.render(self.CONVERGE)
        table = script[script.index("<<'EOF'\n") + 8:script.index("\nEOF\n")]
        values = {}
        for line in table.splitlines():
            if line.strip() and not line.startswith("#"):
                domain, key, kind, value = line.split()
                values[key] = {"true": "1", "false": "0"}.get(value, value) if kind == "-bool" else value
        values.update(reduceMotion="1", ReduceMotionEnabled="1")
        (self.base / "values").write_text("".join("%s %s\n" % kv for kv in values.items()))
        mock = ('defaults() { if [ "$1" = read ]; then awk -v k="$3" \'$1 == k { print $2; f = 1 } END { exit !f }\' %s; '
                'else echo "write $*"; fi; }; killall() { echo "killall $*"; }' % (self.base / "values"))
        helper = script[script.index("defaults_changed=()"):script.index("converge_macos_defaults() {")]
        result = self.section(script, "macos_defaults", mock + "\n" + helper)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "failed=\n", result.stderr)

    def test_stamps(self):
        script = self.render(self.CONVERGE)
        result = self.run_script(self.lib(script) + "\n".join([
            "stamped x k1 && echo bad1",
            "stamp x k1",
            "stamped x k1 || echo bad2",
            "stamped x k2 && echo bad3",
            "echo done",
        ]) + "\n")
        self.assertEqual(result.stdout, "done\n", result.stderr)
        self.assertEqual((self.home / ".local/state/dotfiles/converge/x").read_text(), "k1\n")

    def test_all_host_script_and_config_syntax(self):
        self.assertEqual(sorted(p.name for p in (ROOT / ".chezmoiscripts").iterdir()),
                         ["run_after_converge.sh.tmpl", "run_before_bootstrap.sh.tmpl"])
        for host in self.HOSTS:
            self.configure(host)
            for path in sorted((ROOT / ".chezmoiscripts").glob("*.tmpl")):
                with self.subTest(host=host, script=path.name):
                    rendered = self.render(str(path.relative_to(ROOT)))
                    subprocess.run(["bash", "-n"], input=rendered, text=True, check=True)
            with self.subTest(host=host, config="herdr"):
                tomllib.loads(self.render("dot_config/herdr/config.toml.tmpl"))
            if host.startswith("mac-") and shutil.which("ruby"):
                subprocess.run(["ruby", "-c"], input=self.render("dot_Brewfile.tmpl"),
                               text=True, check=True, capture_output=True)

    def test_external_pins(self):
        externals = tomllib.loads(self.render(".chezmoiexternal.toml.tmpl"))
        plugins = {k: v for k, v in externals.items() if k.startswith(".local/share/plugins/")}
        skills = {k: v for k, v in externals.items() if k.startswith(".agents/skills/")}
        self.assertEqual(set(plugins), {".local/share/plugins/" + name for name in (
            "anthropic-billing-guard", "claude-auto-effort", "claude-marimo", "claude-cache-guard",
            "claude-prose-width", "claude-tool-gate", "codex-cache-guard", "agent-scrub", "claude-code-playground")})
        self.assertEqual(set(skills), {".agents/skills/find-skills", ".agents/skills/vercel-cli"})
        for target, external in (plugins | skills).items():
            self.assertEqual(external["type"], "archive")
            self.assertTrue(external["exact"])
            self.assertRegex(external["url"], r"/archive/[0-9a-f]{40}\.tar\.gz$")
            self.assertRegex(external["checksum"]["sha256"], r"^[0-9a-f]{64}$")

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
            for name, content in (("repo/skills/vercel-cli/SKILL.md", b"skill\n"),
                                  ("repo/skills/vercel-cli/scripts/run.sh", b"#!/bin/sh\n"),
                                  ("repo/skills/unwanted/SKILL.md", b"other\n")):
                member = tarfile.TarInfo(name)
                member.size = len(content)
                member.mode = 0o755 if name.endswith(".sh") else 0o644
                out.addfile(member, io.BytesIO(content))
        external = tomllib.loads(self.render(".chezmoiexternal.toml.tmpl"))[".agents/skills/vercel-cli"]
        (source / ".chezmoiexternal.toml").write_text(
            '[".agents/skills/vercel-cli"]\ntype = "archive"\nurl = %s\nchecksum.sha256 = "%s"\n'
            'stripComponents = %d\nexact = true\ninclude = %s\n' % (
                json.dumps(archive.as_uri()), hashlib.sha256(archive.read_bytes()).hexdigest(),
                external["stripComponents"], json.dumps(external["include"])))
        target = self.home / ".agents/skills/vercel-cli"
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
