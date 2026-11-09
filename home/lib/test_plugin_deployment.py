"""Bootstrap/converge rendering and archive deployment tests; temporary homes only."""
import hashlib
import io
import json
import os
import plistlib
import re
import shlex
import socket
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

    def render(self, path, override=None):
        extra = ["--override-data", json.dumps(override)] if override else []
        return subprocess.check_output([
            CHEZMOI, "--config", str(self.config), "--source", str(ROOT), *extra,
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
            "uv_tools": set(self.HOSTS),
            "login_shell": {"mac-pro", "mac-air", "agentbox-box"},
            "pi_packages": set(self.HOSTS),
            "herdr_plugins": {"mac-pro", "mac-air", "nuc"},
            "aac_touchid": {"mac-pro", "mac-air"},
            "herdr_menu": {"mac-pro", "mac-air"},
            "paseo": {"mac-pro", "mac-air"},
            "omnigent_host": {"mac-pro", "mac-air"},
            "macos_defaults": {"mac-pro", "mac-air"},
            "codexbar": {"mac-pro", "mac-air"},
            "rex_server": {"nuc"},
            "rex_tunnel": {"mac-pro", "mac-air"},
            "rex_preferences": {"mac-pro", "mac-air"},
            "lid_sleep_sudoers": {"mac-pro", "mac-air"},
            "project_mcp": set(self.HOSTS),
            "dotfiles_repo": {"mac-pro", "mac-air", "nuc"},
        }
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.configure(host)
                script = self.render(self.CONVERGE)
                self.assertTrue(script.startswith("#!/bin/bash\n"))
                for name, hosts in expected.items():
                    self.assertEqual("\nrun converge_%s\n" % name in script, host in hosts, name)
                self.assertEqual("paseo-setup" in script, host.startswith("mac-"))

    def test_git_conflict_style_supports_nuc_git(self):
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.configure(host)
                config = self.base / "gitconfig"
                config.write_text(self.render("dot_gitconfig.tmpl"))
                style = subprocess.check_output([
                    "git", "config", "--file", str(config), "--get", "merge.conflictStyle",
                ], text=True).strip()
                self.assertEqual(style, "zdiff3")

    REX = ".chezmoitemplates/converge/rex.sh"
    REX_PLIST = "private_Library/private_LaunchAgents/com.spencerboucher.rex-nuc-tunnel.plist.tmpl"
    REX_SSH = "private_dot_ssh/private_config.d/private_00-rex-nuc.tmpl"
    REX_WRAPPER = "dot_local/bin/executable_rex-nuc-tunnel.tmpl"

    def test_rex_rendered_transport_and_host_exclusions(self):
        data = json.loads((ROOT / ".chezmoidata/rex.json").read_text())["rex"]
        common = None
        marker = "-- Host-specific navigation endpoint"
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.configure(host)
                mac = host.startswith("mac-")
                override = {"chezmoi": {"homeDir": str(self.home)}}
                lua = self.render("dot_config/rex/init.lua.tmpl", override)
                self.assertEqual(lua.count(marker), 1)
                prefix, tail = lua.split(marker)
                if common is None:
                    common = prefix
                else:
                    self.assertEqual(prefix, common)
                self.assertEqual(lua.count("rex.host{"), int(mac))
                if mac:
                    cli = self.home / "Library/Application Support/com.superlogical.rex/RexServer/Versions/Current/Rex Server.app/Contents/MacOS/rex"
                    socket_path = self.home / data["macSocket"]
                    self.assertIn('rex.host{ label = "nuc", endpoint = %s }' %
                                  json.dumps("unix://" + str(self.home / data["localSocket"])), tail)
                elif host == "nuc":
                    cli = self.home / ".local/bin/rex"
                    socket_path = Path(data["nuc"]["remoteSocket"])
                else:
                    cli = socket_path = None
                assignments = [line.strip() for line in tail.splitlines()
                               if line.strip().startswith(("navigation_cli =", "navigation_home_socket ="))]
                expected = [] if cli is None else [
                    "navigation_cli = " + json.dumps(str(cli)),
                    "navigation_home_socket = " + json.dumps(str(socket_path)),
                ]
                self.assertEqual(assignments, expected)
                ignores = set(self.render(".chezmoiignore").splitlines())
                self.assertEqual(".local/bin/rex-nuc-tunnel" in ignores, not mac)
                self.assertEqual(".ssh/config.d/00-rex-nuc" in ignores, not mac)
                self.assertEqual("Library" in ignores, not mac)
                self.assertEqual(".config/systemd/user/rex.service" in ignores, host != "nuc")
                self.assertEqual(".config/systemd/user/default.target.wants/rex.service" in ignores,
                                 host != "nuc")
                self.assertEqual(".config/rex" in ignores, host == "agentbox-box")
                rendered = self.render(self.REX)
                self.assertEqual("rex_reload_config()" in rendered, host != "agentbox-box")

    def test_rex_navigation_helper_is_embedded_source_only(self):
        source = self.base / "source"
        for path in (".chezmoidata/rex.json", ".chezmoitemplates/rex-navigation-helper.lua",
                     "dot_config/rex/init.lua.tmpl"):
            destination = source / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, destination)
        helper = source / ".chezmoitemplates/rex-navigation-helper.lua"
        init = source / "dot_config/rex/init.lua.tmpl"
        args = [CHEZMOI, "--config", str(self.config), "--source", str(source),
                "--destination", str(self.home)]
        def render():
            return subprocess.check_output(args + ["execute-template", "--file", str(init)], text=True)
        before = render()
        self.assertIn(helper.read_text(), before)
        managed = subprocess.check_output(args + ["managed", "--path-style", "relative"], text=True)
        self.assertIn(".config/rex/init.lua", managed.splitlines())
        self.assertFalse(any("rex-navigation-helper" in path for path in managed.splitlines()))
        sentinel = "-- isolated helper regression marker"
        helper.write_text(helper.read_text() + "\n" + sentinel + "\n")
        after = render()
        self.assertNotEqual(before, after)
        self.assertNotIn(sentinel, before)
        self.assertIn(sentinel, after)

    def rex_bindings(self):
        lua = self.render("dot_config/rex/init.lua.tmpl")
        bindings = {}
        for line in lua.splitlines():
            if not line.strip().startswith("rex.bind("):
                continue
            match = re.fullmatch(r'\s*rex\.bind\("([^"]+)",\s*"([^"]+)"(?:,\s*\{(.*?)\})?\)\s*', line)
            self.assertIsNotNone(match, "unparsed binding: " + line)
            key, action, fields = match.groups()
            self.assertNotIn(key, bindings, "duplicate binding: " + key)
            args = {}
            if fields:
                for field in fields.split(","):
                    arg = re.fullmatch(r'\s*(\w+)\s*=\s*(?:"([^"]*)"|(\d+))\s*', field)
                    self.assertIsNotNone(arg, "unparsed argument: " + field)
                    name, string, number = arg.groups()
                    self.assertNotIn(name, args)
                    args[name] = string if string is not None else int(number)
            bindings[key] = (action, args)
        return lua, bindings

    def assert_rex_mappings(self, bindings, expected):
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(bindings.get(key), value)

    def test_rex_herdr_navigation_bindings(self):
        _, bindings = self.rex_bindings()
        expected = {}
        def add(keys, action, **args):
            for key in keys.split():
                expected["ctrl+b>" + key] = (action, args)
        add("c", "session.new")
        add("shift+;", "client.palette.toggle")
        add("s f", "pane.go_to")
        add("w", "session.switch")
        add("n", "session.next")
        add("p", "session.previous")
        add("j ctrl+j", "client.tab.next")
        add("k ctrl+k", "client.tab.previous")
        add("enter", "next_program")
        add("ctrl+enter", "next_attention")
        add("ctrl+o ctrl+l", "pane.focus_next")
        add("ctrl+h shift+tab", "pane.focus_previous")
        add("shift+c", "client.tab.new")
        add("shift+t", "client.tab.rename")
        add("shift+x", "client.tab.close")
        add("shift+right alt+l ctrl+n", "client.tab.next")
        add("shift+left alt+h ctrl+p", "client.tab.previous")
        add("shift+'", "pane.split", direction="right")
        add("shift+5", "pane.split", direction="down")
        for key, direction in (("h", "left"), ("l", "right")):
            add(key, "pane.focus", direction=direction)
        for key, direction in zip("hjkl", ("left", "down", "up", "right")):
            add("shift+" + key, "pane.move", direction=direction)
        self.assert_rex_mappings(bindings, expected)

    def test_rex_navigation_repeat_mode(self):
        lua, bindings = self.rex_bindings()
        self.assertRegex(lua, r'rex\.mode\("repeat",\s*\{\s*exclusive\s*=\s*true\s*\}\)')
        expected = {"ctrl+b>ctrl+r": ("client.mode.enter", {"name": "repeat"})}
        for keys, action in (
            ("n", "session.next"), ("p", "session.previous"),
            ("j ctrl+j ctrl+n shift+right alt+l", "client.tab.next"),
            ("k ctrl+k ctrl+p shift+left alt+h", "client.tab.previous"),
            ("ctrl+o ctrl+l", "pane.focus_next"),
            ("ctrl+h shift+tab", "pane.focus_previous"),
            ("enter escape", "client.mode.exit"),
        ):
            expected.update({"repeat/" + key: (action, {}) for key in keys.split()})
        for key, direction in (("h", "left"), ("l", "right")):
            expected["repeat/" + key] = ("pane.focus", {"direction": direction})
        self.assert_rex_mappings(bindings, expected)
        repeat = {key: value for key, value in bindings.items() if key.startswith("repeat/")}
        self.assertEqual(set(repeat), {key for key in expected if key.startswith("repeat/")})
        self.assertFalse(any(action == "pane.resize" or action.endswith((".close", ".delete"))
                             for action, _ in repeat.values()))

    def test_rex_resize_mode(self):
        lua, bindings = self.rex_bindings()
        self.assertRegex(lua, r'rex\.mode\("resize",\s*\{\s*exclusive\s*=\s*true\s*\}\)')
        expected = {"ctrl+b>r": ("client.mode.enter", {"name": "resize"})}
        for key in ("enter", "escape"):
            expected["resize/" + key] = ("client.mode.exit", {})
        for key, direction in zip("hjkl", ("left", "down", "up", "right")):
            for chord, amount in ((direction, 1), (key, 1), ("ctrl+" + key, 5)):
                expected["resize/" + chord] = ("pane.resize", {"direction": direction, "amount": amount})
        self.assert_rex_mappings(bindings, expected)
        self.assertEqual({key for key in bindings if key.startswith("resize/")},
                         {key for key in expected if key.startswith("resize/")})
        self.assert_rex_mappings(bindings, {
            "ctrl+b>ctrl+h": ("pane.focus_previous", {}),
            "ctrl+b>ctrl+j": ("client.tab.next", {}),
            "ctrl+b>ctrl+k": ("client.tab.previous", {}),
            "ctrl+b>ctrl+l": ("pane.focus_next", {}),
            "repeat/ctrl+h": ("pane.focus_previous", {}),
            "repeat/ctrl+j": ("client.tab.next", {}),
            "repeat/ctrl+k": ("client.tab.previous", {}),
            "repeat/ctrl+l": ("pane.focus_next", {}),
        })

    def test_rex_sidebar_navigation_bindings_consistent_across_hosts(self):
        for host in ("mac-pro", "mac-air", "nuc"):
            with self.subTest(host=host):
                self.configure(host)
                _, bindings = self.rex_bindings()
                expected = {}
                for prefix in ("ctrl+b>", "repeat/"):
                    for key in ("j", "ctrl+j"):
                        expected[prefix + key] = ("client.tab.next", {})
                    for key in ("k", "ctrl+k"):
                        expected[prefix + key] = ("client.tab.previous", {})
                    expected[prefix + "n"] = ("session.next", {})
                    expected[prefix + "p"] = ("session.previous", {})
                for key, direction in (("j", "down"), ("k", "up")):
                    for chord, amount in ((key, 1), ("ctrl+" + key, 5)):
                        expected["resize/" + chord] = ("pane.resize", {"direction": direction, "amount": amount})
                self.assert_rex_mappings(bindings, expected)

    def test_rex_external_pin_is_immutable_and_nuc_only(self):
        pin = json.loads((ROOT / ".chezmoidata/linux.json").read_text())["linux"]["releases"]["rex"]
        self.assertEqual(pin["provider"], "superlogical")
        self.assertEqual(pin["hosts"], ["nuc"])
        self.assertEqual(pin["tag"], "01d6c4fe68668db3521570d7fbc9b6b112b1e572")
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.configure(host)
                os_name = "darwin" if host.startswith("mac-") else "linux"
                externals = tomllib.loads(self.render(".chezmoiexternal.toml.tmpl",
                                                     {"chezmoi": {"arch": "amd64", "os": os_name}}))
                if host != "nuc":
                    self.assertNotIn(".local/bin/rex", externals)
                    continue
                entry = externals[".local/bin/rex"]
                self.assertEqual(entry, {
                    "type": "archive-file", "executable": True, "path": "rex",
                    "url": "https://blob.superlogical.com/download/rex/snapshot/"
                           + pin["tag"] + "/rex-linux-amd64.tar.gz",
                    "checksum": {"sha256": "2874bb64dacb120eac8cae71ff9b6660479a654a9f89c6cd29cdc88372b7ee2d"},
                })
                self.assertEqual(pin["sha256"]["amd64"], entry["checksum"]["sha256"])
                self.assertEqual(pin["members"]["amd64"], {"rex": entry["path"]})

    def test_rex_mac_plist_and_ssh_syntax(self):
        data = json.loads((ROOT / ".chezmoidata/rex.json").read_text())["rex"]
        for host in ("mac-pro", "mac-air"):
            with self.subTest(host=host):
                self.configure(host)
                # SSH checks Unix socket path length even with -G; keep this synthetic path short.
                home = "/tmp/Rex home & fixtures"
                override = {"chezmoi": {"homeDir": home}}
                rendered = self.render(self.REX_PLIST, override)
                plist = plistlib.loads(rendered.encode())
                self.assertEqual(plist, {
                    "Label": "com.spencerboucher.rex-nuc-tunnel",
                    "ProgramArguments": [home + "/.local/bin/rex-nuc-tunnel"],
                    "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 30,
                    "StandardErrorPath": home + "/Library/Logs/rex-nuc-tunnel.log",
                })
                fixture = self.base / "rex.plist"
                fixture.write_text(rendered)
                if shutil.which("plutil"):
                    subprocess.run(["plutil", "-lint", "--", str(fixture)],
                                   check=True, capture_output=True)
                stanza = self.render(self.REX_SSH, override)
                self.assertTrue(stanza.rstrip().endswith("Host *"))
                self.assertEqual(stanza.count("LocalForward "), 1)
                self.assertNotIn("RemoteForward", stanza)
                fixture = self.base / "ssh_config"
                fixture.write_text(stanza)
                # -G only parses this standalone fixture; it never connects or reads ~/.ssh/config.
                if not shutil.which("ssh"):
                    continue
                parsed = subprocess.run(["ssh", "-F", str(fixture), "-G", "rex-nuc"],
                                        text=True, capture_output=True)
                self.assertEqual(parsed.returncode, 0, parsed.stderr)
                values = dict(l.split(" ", 1) for l in parsed.stdout.splitlines())
                for key, expected in {
                    "hostname": data["nuc"]["destination"], "user": data["nuc"]["user"],
                    "identityfile": "~/.ssh/nuc_ed25519", "identitiesonly": "yes",
                    "identityagent": "none", "batchmode": "yes", "stricthostkeychecking": "true",
                    "controlmaster": "false", "exitonforwardfailure": "yes", "connecttimeout": "10",
                    "serveraliveinterval": "15", "serveralivecountmax": "3",
                    "streamlocalbindunlink": "yes", "streamlocalbindmask": "0177",
                }.items():
                    self.assertEqual(values[key], expected, key)
                self.assertNotIn("controlpath", values)
                self.assertNotIn("remoteforward", values)
                self.assertEqual(values["localforward"], home + "/" + data["localSocket"]
                                 + " " + data["nuc"]["remoteSocket"])

    def test_rex_wrapper_quotes_home_and_uses_manifest(self):
        self.home = self.base / "home with spaces"
        self.home.mkdir()
        data = json.loads((ROOT / ".chezmoidata/rex.json").read_text())["rex"]
        data["localSocket"] = ".local/state/rex custom/ssh/nuc.sock"
        data["nuc"]["alias"] = "rex-fixture"
        wrapper = self.render(self.REX_WRAPPER, {"rex": data})
        self.assertIn('exec /usr/bin/ssh -NT "rex-fixture"', wrapper)
        self.assertIn("umask 077", wrapper)
        ssh = self.base / "fake ssh"
        ssh.write_text('#!/bin/sh\nprintf "%s\\n" "$@" >"$HOME/ssh-args"\n'
                       'umask >"$HOME/ssh-umask"\n')
        ssh.chmod(0o755)
        # Replace only the absolute executable in a fixture copy, never run a real tunnel.
        result = self.run_script(wrapper.replace("/usr/bin/ssh", shlex.quote(str(ssh))))
        self.assertEqual(result.returncode, 0, result.stderr)
        directory = self.home / Path(data["localSocket"]).parent
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.home / "ssh-args").read_text().splitlines(), ["-NT", "rex-fixture"])
        self.assertEqual(int((self.home / "ssh-umask").read_text().strip(), 8), 0o077)
        self.assertNotIn("StrictHostKeyChecking", wrapper)

    def test_rex_nuc_unit_and_enablement_link(self):
        self.configure("nuc")
        unit = self.render("dot_config/systemd/user/rex.service")
        for line in (
            "Type=simple", "RuntimeDirectory=rex", "RuntimeDirectoryMode=0700", "Restart=on-failure",
            "RestartSec=5", "KillMode=mixed", "TimeoutStopSec=30", "WantedBy=default.target",
        ):
            self.assertIn(line, unit.splitlines())
        command = next(l.split("=", 1)[1] for l in unit.splitlines() if l.startswith("ExecStart="))
        argv = shlex.split(command)
        self.assertEqual(argv[:2], ["/usr/bin/zsh", "-c"])
        self.assertEqual(len(argv), 3)
        self.assertEqual(argv[2], 'exec "$HOME/.local/bin/rex" server run --listen '
                         'unix://%t/rex/server.sock --socket-mode 0600 --log-format text')
        subprocess.run(["bash", "-n"], input=argv[2], text=True, check=True)
        link = self.render("dot_config/systemd/user/default.target.wants/symlink_rex.service.tmpl",
                           {"chezmoi": {"homeDir": str(self.home)}})
        self.assertEqual(link.strip(), str(self.home / ".config/systemd/user/rex.service"))

    def rex_file(self, path, content="fixture\n", executable=False):
        target = self.home / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        if executable:
            target.chmod(0o755)
        return target

    def rex_socket(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        sock = socket.socket(socket.AF_UNIX)
        self.addCleanup(sock.close)
        sock.bind(str(path))

    def rex_fixture(self, host="nuc", active=True, local_socket=True, terminfo=True):
        self.configure(host)
        self.rex_file(".config/rex/init.lua")
        self.rex_file(".config/systemd/user/rex.service")
        self.rex_file(".local/bin/rex", executable=True)
        self.rex_file(".ssh/nuc_ed25519")
        self.rex_file("Library/LaunchAgents/com.spencerboucher.rex-nuc-tunnel.plist")
        self.rex_file(".local/bin/rex-nuc-tunnel", executable=True)
        self.rex_file(".ssh/config.d/00-rex-nuc")
        if active:
            self.rex_file("active")
        if terminfo:
            self.rex_file("terminfo")
        data = json.loads((ROOT / ".chezmoidata/rex.json").read_text())["rex"]
        data["nuc"]["remoteSocket"] = str(self.home / "server.sock")
        # Keep the test socket below the Unix-domain path-length limit on macOS.
        data["macSocket"] = "mac.sock"
        if local_socket:
            self.rex_socket(self.home / ("server.sock" if host == "nuc" else "mac.sock"))
        self.rex_data = data

    REX_MOCKS = r'''
log() { printf '%s\n' "$*" >>"$HOME/calls"; }
id() { echo 1000; }
sleep() { log "sleep $*"; }
loginctl() { log "loginctl $*"; echo "${LINGER-yes}"; }
sudo() { log "FORBIDDEN sudo $*"; return 99; }
ssh() { log "FORBIDDEN ssh $*"; return 99; }
defaults() { log "FORBIDDEN defaults $*"; return 99; }
killall() { log "FORBIDDEN killall $*"; return 99; }
python3() { log "python3 $*"; return "${PREFERENCES_FAIL-0}"; }
systemctl() {
    log "systemctl $*"
    case "$*" in
        '--user daemon-reload') return "${DAEMON_FAIL-0}" ;;
        '--user is-active --quiet rex.service') [ -f "$HOME/active" ] ;;
        '--user start rex.service')
            [ "${START_FAIL-0}" = 0 ] || return 1
            touch "$HOME/active"
            [ ! -S "$HOME/staged.sock" ] || mv "$HOME/staged.sock" "$HOME/server.sock" ;;
        *) log "FORBIDDEN systemctl $*"; return 99 ;;
    esac
}
infocmp() { log "infocmp $*"; [ -f "$HOME/terminfo" ]; }
rex() {
    log "rex $*"
    case "$*" in
        'config check '*) return "${CHECK_FAIL-0}" ;;
        *' config reload') return "${RELOAD_FAIL-0}" ;;
        *' server status --json')
            [ "${STATUS_FAIL-0}" = 0 ] || return 1
            if [ "${STATUS_DELAY-0}" -gt 0 ]; then STATUS_DELAY=$((STATUS_DELAY-1)); return 1; fi ;;
        'terminfo setup --entry-only')
            [ "${TERMINFO_FAIL-0}" = 0 ] || return 1
            [ "${TERMINFO_STALE-0}" = 1 ] || touch "$HOME/terminfo" ;;
        *) log "FORBIDDEN rex $*"; return 99 ;;
    esac
}
launchctl() {
    log "launchctl $*"
    case "$1" in
        print) [ -f "$HOME/loaded" ] ;;
        bootout)
            [ "${BOOTOUT_FAIL-0}" = 0 ] || return 1
            [ "${BOOTOUT_STALE-0}" = 1 ] || rm -f "$HOME/loaded" ;;
        bootstrap)
            [ ! -f "$HOME/loaded" ] || return 1
            [ "${BOOTSTRAP_FAIL-0}" = 0 ] || return 1
            if [ "${BOOTSTRAP_ONCE-0}" = 1 ] && [ ! -f "$HOME/bootstrap-attempt" ]; then
                touch "$HOME/bootstrap-attempt"; return 1
            fi
            [ "${BOOTSTRAP_STALE-0}" = 1 ] || touch "$HOME/loaded" ;;
        *) log "FORBIDDEN launchctl $*"; return 99 ;;
    esac
}
'''

    def run_rex(self, setup="", call=None):
        """Source the whole Rex template so the real reload helper participates."""
        script = self.render(self.REX, {"rex": self.rex_data})
        if call is not None:
            script = re.sub(r"^run converge_rex_\w+\n", "", script, flags=re.MULTILINE)
            script += "\n" + call + "\n"
        self.rex_file("calls", "")
        result = self.run_script("set -u\n" + self.render(".chezmoitemplates/converge/lib.sh")
                                 + self.REX_MOCKS + "\n" + setup + "\n" + script
                                 + '\necho "failed=${failed[*]+${failed[*]}}"\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("FORBIDDEN", self.rex_calls())
        return result

    def rex_calls(self):
        return (self.home / "calls").read_text()

    def assert_rex_success(self, result, silent=False):
        self.assertEqual(result.stderr, "")
        if silent:
            self.assertEqual(result.stdout, "failed=\n")
        else:
            self.assertTrue(result.stdout.endswith("failed=\n"), result.stdout)

    def test_rex_nuc_first_start_then_silent_noop_and_definition_changes(self):
        self.rex_fixture(active=False, local_socket=False, terminfo=False)
        self.rex_socket(self.home / "staged.sock")
        first = self.run_rex("STATUS_DELAY=2")
        self.assert_rex_success(first)
        calls = self.rex_calls()
        for command in ("systemctl --user daemon-reload", "systemctl --user start rex.service",
                        "rex terminfo setup --entry-only", " config reload"):
            self.assertEqual(calls.count(command), 1, calls)
        self.assertEqual(calls.count("sleep 0.25"), 2)
        self.assertTrue((self.home / ".local/state/dotfiles/converge/rex-config").exists())
        self.assert_rex_success(self.run_rex(), silent=True)
        self.assertNotIn("daemon-reload", self.rex_calls())
        self.assertNotIn(" start ", self.rex_calls())
        self.assertNotIn("terminfo setup", self.rex_calls())
        self.assertNotIn("config reload", self.rex_calls())
        self.assertNotIn("config check", self.rex_calls())
        # A new pin must not touch the live server; a new unit only reloads systemd metadata.
        for path, reloads in ((".local/bin/rex", 0), (".config/systemd/user/rex.service", 1)):
            with self.subTest(path=path):
                with (self.home / path).open("a") as out:
                    out.write("changed\n")
                result = self.run_rex()
                self.assert_rex_success(result)
                calls = self.rex_calls()
                self.assertEqual(calls.count("daemon-reload"), reloads)
                self.assertNotIn(" start ", calls)
                self.assertNotIn("restart", calls)
                self.assertNotIn("config reload", calls)

    def test_rex_nuc_unmanaged_socket_guard(self):
        self.rex_fixture(active=False)
        result = self.run_rex()
        self.assertIn("failed=rex_server", result.stdout)
        self.assertIn("unmanaged socket exists", result.stderr)
        self.assertNotIn("systemctl --user start", self.rex_calls())
        self.assertNotIn("rex --", self.rex_calls())
        self.assertNotIn("restart", self.rex_calls())

    def test_rex_nuc_missing_linger_is_actionable_without_mutation(self):
        self.rex_fixture()
        result = self.run_rex("LINGER=no")
        self.assertIn("failed=rex_server", result.stdout)
        self.assertIn("loginctl enable-linger", result.stderr)
        self.assertEqual(self.rex_calls(), "loginctl show-user 1000 -p Linger --value\n")
        self.assertFalse((self.home / ".local/state/dotfiles/converge").exists())

    def test_rex_nuc_failed_start_and_readiness_retry(self):
        self.rex_fixture(active=False, local_socket=False)
        self.rex_socket(self.home / "staged.sock")
        result = self.run_rex("START_FAIL=1")
        self.assertIn("failed=rex_server", result.stdout)
        self.assertNotIn("server status", self.rex_calls())
        result = self.run_rex("STATUS_FAIL=1")
        self.assertIn("failed=rex_server", result.stdout)
        self.assertIn("did not become ready", result.stderr)
        self.assertEqual(self.rex_calls().count("server status --json"), 20)
        self.assertEqual(self.rex_calls().count("sleep 0.25"), 20)
        self.assertNotIn("config reload", self.rex_calls())
        self.assertFalse((self.home / ".local/state/dotfiles/converge/rex-config").exists())
        self.assert_rex_success(self.run_rex())
        self.assertNotIn("systemctl --user start", self.rex_calls())

    def test_rex_nuc_daemon_reload_failure_is_not_stamped(self):
        self.rex_fixture()
        result = self.run_rex("DAEMON_FAIL=1")
        self.assertIn("failed=rex_server", result.stdout)
        self.assertFalse((self.home / ".local/state/dotfiles/converge/rex-unit").exists())
        self.assertNotIn("is-active", self.rex_calls())
        self.assert_rex_success(self.run_rex())
        self.assertIn("daemon-reload", self.rex_calls())

    def test_rex_nuc_terminfo_failure_and_readback_failure_retry(self):
        self.rex_fixture(terminfo=False)
        for setup in ("TERMINFO_FAIL=1", "TERMINFO_STALE=1"):
            with self.subTest(setup=setup):
                result = self.run_rex(setup)
                self.assertIn("failed=rex_server", result.stdout)
                self.assertIn("rex terminfo setup --entry-only", self.rex_calls())
                self.assertNotIn("config reload", self.rex_calls())
                self.assertFalse((self.home / "terminfo").exists())
        self.assertIn("did not converge", result.stderr)
        self.assert_rex_success(self.run_rex())
        self.assertTrue((self.home / "terminfo").exists())
        self.assert_rex_success(self.run_rex(), silent=True)
        self.assertNotIn("terminfo setup", self.rex_calls())

    def test_rex_nuc_lua_failures_propagate_without_restarting_server(self):
        self.rex_fixture()
        for setup in ("CHECK_FAIL=1", "RELOAD_FAIL=1"):
            with self.subTest(setup=setup):
                result = self.run_rex(setup)
                self.assertIn("failed=rex_server", result.stdout)
                self.assertNotIn("systemctl --user start", self.rex_calls())
                self.assertNotIn("restart", self.rex_calls())
                self.assertFalse((self.home / ".local/state/dotfiles/converge/rex-config").exists())
        self.assert_rex_success(self.run_rex())
        self.assertEqual(self.rex_calls().count("config reload"), 1)
        self.assert_rex_success(self.run_rex(), silent=True)

    def test_rex_lua_real_helper_validates_reloads_and_only_stamps_success(self):
        self.rex_fixture("mac-pro")
        call = 'run_config() { rex_reload_config "$HOME/mac.sock"; }; run run_config'
        # Use the real helper, not a stub that would conceal failed validation/reload/status.
        for setup in ("CHECK_FAIL=1", "STATUS_FAIL=1", "RELOAD_FAIL=1"):
            with self.subTest(setup=setup):
                result = self.run_rex(setup, call)
                self.assertIn("failed=run_config", result.stdout)
                self.assertFalse((self.home / ".local/state/dotfiles/converge/rex-config").exists())
                if setup == "CHECK_FAIL=1":
                    self.assertNotIn("server status", self.rex_calls())
                    self.assertNotIn("config reload", self.rex_calls())
                elif setup == "STATUS_FAIL=1":
                    self.assertIn("socket exists but its server is unavailable", result.stderr)
                    self.assertNotIn("config reload", self.rex_calls())
        self.assert_rex_success(self.run_rex(call=call))
        self.assertIn('rex --autostart=false -S %s --timeout 3s server status --json' %
                      (self.home / "mac.sock"), self.rex_calls())
        self.assertIn('rex --autostart=false -S %s config reload' %
                      (self.home / "mac.sock"), self.rex_calls())
        self.assert_rex_success(self.run_rex(call=call), silent=True)
        self.assertEqual(self.rex_calls(), "")
        self.rex_file(".config/rex/init.lua", "changed Lua\n")
        self.assert_rex_success(self.run_rex(call=call))
        self.assertEqual(self.rex_calls().count("config reload"), 1)
        self.assertNotIn("restart", self.rex_calls())

    def test_rex_lua_stopped_app_is_validated_but_not_started_or_stamped(self):
        self.rex_fixture("mac-pro", local_socket=False)
        call = 'run_config() { rex_reload_config "$HOME/mac.sock"; }; run run_config'
        for _ in range(2):
            self.assert_rex_success(self.run_rex(call=call), silent=True)
            self.assertEqual(self.rex_calls(), 'rex config check %s\n' %
                             (self.home / ".config/rex/init.lua"))
            self.assertFalse((self.home / ".local/state/dotfiles/converge/rex-config").exists())

    def test_rex_mac_tunnel_first_noop_and_each_definition_change(self):
        self.rex_fixture("mac-pro")
        result = self.run_rex()
        self.assert_rex_success(result)
        self.assertEqual(self.rex_calls().count("launchctl bootstrap "), 1)
        self.assertNotIn("bootout", self.rex_calls())
        self.assert_rex_success(self.run_rex(), silent=True)
        self.assertNotIn("bootstrap", self.rex_calls())
        self.assertNotIn("bootout", self.rex_calls())
        self.assertNotIn("config reload", self.rex_calls())
        for path in ("Library/LaunchAgents/com.spencerboucher.rex-nuc-tunnel.plist",
                     ".local/bin/rex-nuc-tunnel", ".ssh/config.d/00-rex-nuc"):
            with self.subTest(path=path):
                with (self.home / path).open("a") as out:
                    out.write("changed\n")
                self.assert_rex_success(self.run_rex())
                calls = self.rex_calls()
                self.assertEqual(calls.count("launchctl bootout gui/1000/com.spencerboucher.rex-nuc-tunnel"), 1)
                self.assertEqual(calls.count("launchctl bootstrap gui/1000 "), 1)
                self.assertNotIn("config reload", calls)
                self.assertNotIn("restart", calls)
                self.assert_rex_success(self.run_rex(), silent=True)
                self.assertNotIn("bootstrap", self.rex_calls())
        # A stamp alone is insufficient when launchd lost the job.
        (self.home / "loaded").unlink()
        self.assert_rex_success(self.run_rex())
        self.assertEqual(self.rex_calls().count("launchctl bootstrap "), 1)
        self.assertNotIn("bootout", self.rex_calls())

    def test_rex_mac_lua_drift_reloads_only_local_server_not_tunnel(self):
        self.rex_fixture("mac-pro")
        self.assert_rex_success(self.run_rex())
        self.rex_file(".config/rex/init.lua", "changed Lua\n")
        result = self.run_rex("RELOAD_FAIL=1")
        self.assertIn("failed=rex_tunnel", result.stdout)
        self.assertNotIn("bootstrap", self.rex_calls())
        self.assertNotIn("bootout", self.rex_calls())
        self.assert_rex_success(self.run_rex())
        self.assertEqual(self.rex_calls().count("config reload"), 1)
        self.assertNotIn("bootstrap", self.rex_calls())
        self.assertNotIn("bootout", self.rex_calls())
        self.assertNotIn(self.rex_data["localSocket"], self.rex_calls())
        self.assert_rex_success(self.run_rex(), silent=True)

    def test_rex_mac_tunnel_bootstrap_failure_readback_and_bounded_retry(self):
        self.rex_fixture("mac-air", local_socket=False)
        for setup in ("BOOTSTRAP_FAIL=1", "BOOTSTRAP_STALE=1"):
            with self.subTest(setup=setup):
                result = self.run_rex(setup)
                self.assertIn("failed=rex_tunnel", result.stdout)
                self.assertFalse((self.home / ".local/state/dotfiles/converge/rex-tunnel").exists())
                self.assertIn("python3 -B", self.rex_calls())  # Other sections still run.
        result = self.run_rex("BOOTSTRAP_ONCE=1")
        self.assert_rex_success(result)
        self.assertEqual(self.rex_calls().count("launchctl bootstrap "), 2)
        self.assertIn("sleep 2", self.rex_calls())
        self.assertTrue((self.home / ".local/state/dotfiles/converge/rex-tunnel").exists())

    def test_rex_mac_tunnel_bootout_failure_keeps_old_stamp_and_retries(self):
        self.rex_fixture("mac-pro", local_socket=False)
        self.assert_rex_success(self.run_rex())
        stamp = self.home / ".local/state/dotfiles/converge/rex-tunnel"
        old = stamp.read_text()
        self.rex_file(".ssh/config.d/00-rex-nuc", "new definition\n")
        result = self.run_rex("BOOTOUT_FAIL=1")
        self.assertIn("failed=rex_tunnel", result.stdout)
        self.assertEqual(stamp.read_text(), old)
        self.assertNotIn("bootstrap", self.rex_calls())
        self.assert_rex_success(self.run_rex())
        self.assertNotEqual(stamp.read_text(), old)

    def test_rex_mac_tunnel_stale_bootout_is_bounded_and_does_not_stamp(self):
        self.rex_fixture("mac-air", local_socket=False)
        self.assert_rex_success(self.run_rex())
        stamp = self.home / ".local/state/dotfiles/converge/rex-tunnel"
        old = stamp.read_text()
        self.rex_file(".ssh/config.d/00-rex-nuc", "new definition\n")
        result = self.run_rex("BOOTOUT_STALE=1")
        self.assertIn("failed=rex_tunnel", result.stdout)
        self.assertEqual(stamp.read_text(), old)
        self.assertEqual(self.rex_calls().count("sleep 0.5"), 20)
        self.assertEqual(self.rex_calls().count("launchctl bootstrap "), 2)
        self.assert_rex_success(self.run_rex())
        self.assertNotEqual(stamp.read_text(), old)

    def test_rex_prerequisite_failures_do_not_mutate_services(self):
        self.rex_fixture()
        for path in (".local/bin/rex", ".config/systemd/user/rex.service"):
            with self.subTest(path=path):
                target = self.home / path
                target.unlink()
                result = self.run_rex()
                self.assertIn("failed=rex_server", result.stdout)
                self.assertIn("pinned binary or user unit missing", result.stderr)
                self.assertEqual(self.rex_calls(), "")
                self.rex_file(path, executable=path.endswith("/rex"))
        self.configure("mac-pro")
        for path in (".ssh/nuc_ed25519", "Library/LaunchAgents/com.spencerboucher.rex-nuc-tunnel.plist",
                     ".local/bin/rex-nuc-tunnel", ".ssh/config.d/00-rex-nuc"):
            with self.subTest(path=path):
                (self.home / path).unlink()
                result = self.run_rex()
                self.assertIn("failed=rex_tunnel", result.stdout)
                self.assertIn("tunnel definition or ~/.ssh/nuc_ed25519 missing", result.stderr)
                self.assertNotIn("launchctl", self.rex_calls())
                self.assertNotIn("rex ", self.rex_calls())
                self.rex_file(path, executable=path.endswith("rex-nuc-tunnel"))

    def test_rex_lua_missing_cli_or_config_is_not_silently_accepted(self):
        self.rex_fixture("mac-pro", local_socket=False)
        call = 'run_config() { rex_reload_config "$HOME/mac.sock"; }; run run_config'
        setup = 'have() { [ "$1" != rex ] && command -v "$1" >/dev/null 2>&1; }'
        result = self.run_rex(setup, call)
        self.assertIn("failed=run_config", result.stdout)
        self.assertIn("CLI or Lua config missing", result.stderr)
        self.assertEqual(self.rex_calls(), "")
        (self.home / ".config/rex/init.lua").unlink()
        result = self.run_rex(call=call)
        self.assertIn("failed=run_config", result.stdout)
        self.assertIn("CLI or Lua config missing", result.stderr)
        self.assertEqual(self.rex_calls(), "")

    def test_rex_mac_offline_tunnel_is_supervised_not_connectivity_checked(self):
        self.rex_fixture("mac-air", local_socket=False)
        # No local Rex app or forwarded endpoint; remote connectivity is not apply drift.
        self.assert_rex_success(self.run_rex("STATUS_FAIL=1"))
        self.assertTrue((self.home / "loaded").exists())
        self.assert_rex_success(self.run_rex("STATUS_FAIL=1"), silent=True)
        self.assertNotIn("server status", self.rex_calls())
        self.assertNotIn("bootstrap", self.rex_calls())
        self.assertNotIn("bootout", self.rex_calls())

    def test_rex_mac_preferences_helper_arguments_and_failure_recording(self):
        for host in ("mac-pro", "mac-air"):
            with self.subTest(host=host):
                self.configure(host)
                script = self.render(self.CONVERGE)
                source = self.base / "source with spaces"
                script = script.replace(str(ROOT), str(source))
                setup = 'python3() { printf "%s\\n" "$@" >"$HOME/args"; return 2; }'
                result = self.section(script, "rex_preferences", setup)
                self.assertEqual(result.stdout, "failed=rex_preferences\n")
                self.assertEqual(result.stderr, "")
                self.assertEqual((self.home / "args").read_text().splitlines(), [
                    "-B", str(source / "lib/rex_settings.py"),
                    "--settings", str(source / ".chezmoidata/rex.json"),
                ])
        self.rex_fixture("mac-pro", local_socket=False)
        result = self.run_rex("BOOTSTRAP_FAIL=1; PREFERENCES_FAIL=2")
        self.assertIn("failed=rex_tunnel rex_preferences", result.stdout)

    def test_dotfiles_repo_sets_hooks_path_and_rerere_once(self):
        repo = self.base / "dotfiles"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        self.configure("nuc")
        script = self.render(self.CONVERGE).replace(str(ROOT.parent), str(repo))
        result = self.section(script, "dotfiles_repo")
        self.assertEqual(result.stdout, "==> dotfiles repo: git config core.hooksPath .githooks\n"
                         "==> dotfiles repo: git config rerere.enabled true\nfailed=\n", result.stderr)
        config = lambda key: subprocess.run(["git", "-C", str(repo), "config", "--local", key],
                                            capture_output=True, text=True).stdout.strip()
        self.assertEqual((config("core.hooksPath"), config("rerere.enabled")), (".githooks", "true"))
        self.assertEqual(self.section(script, "dotfiles_repo").stdout, "failed=\n")

    def test_uv_tools_passes_cooldown_data_and_fails_on_error(self):
        data = json.loads((ROOT / ".chezmoidata/cooldown.json").read_text())
        maintained = ",".join(data["cooldownExempt"]["uv"])
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.configure(host)
                script = self.render(self.CONVERGE)
                line = next(l for l in script.splitlines() if l.strip().startswith("python3 ") and "lib/uv_tools.py" in l)
                self.assertIn("--maintained '%s'" % maintained, line)
                self.assertNotIn("--declared", line)
                self.assertNotIn("--allow", line)
        self.configure("nuc")
        script = self.render(self.CONVERGE)
        result = self.section(script, "uv_tools", "have() { return 0; }; python3() { return 3; }")
        self.assertIn("failed=uv_tools", result.stdout)
        result = self.section(script, "uv_tools", "have() { return 0; }; python3() { return 0; }")
        self.assertIn("failed=\n", result.stdout)
        self.assertEqual(result.stdout, "failed=\n")

    def test_codexbar_section_uses_source_paths_and_propagates_failure(self):
        # A source checkout with spaces must still pass each path as one argument.
        source = self.base / "source with spaces"
        expected = ["-B", str(source / "lib/codexbar_settings.py"),
                    "--settings", str(source / ".chezmoidata/codexbar.json")]
        for host in ("mac-pro", "mac-air"):
            with self.subTest(host=host):
                self.configure(host)
                script = self.render(self.CONVERGE).replace(str(ROOT), str(source))
                setup = 'python3() { printf "%s\\n" "$@" >"$HOME/codexbar-args"; }'
                result = self.section(script, "codexbar", setup)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "failed=\n")
                self.assertEqual((self.home / "codexbar-args").read_text().splitlines(), expected)
                result = self.section(script, "codexbar", "python3() { return 2; }")
                self.assertEqual(result.stdout, "failed=codexbar\n")
                self.assertEqual(result.stderr, "")

    def test_cooldown_configs_render_exemptions_and_allowances(self):
        exempt = json.loads((ROOT / ".chezmoidata/cooldown.json").read_text())["cooldownExempt"]["npm"]
        allow = ["left-pad@1.3.0"]
        override = {"cooldownAllow": allow}
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.configure(host)
                pnpm = self.render(".chezmoitemplates/pnpm-config.yaml", override)
                self.assertIn("minimumReleaseAge: 10080", pnpm)
                for entry in exempt + allow:
                    self.assertIn("\n  - '%s'\n" % entry, pnpm)
                yarn = self.render("dot_yarnrc.yml.tmpl", override)
                self.assertIn("npmMinimalAgeGate: 10080", yarn)
                listed = next(l for l in yarn.splitlines() if l.startswith("npmPreapprovedPackages: "))
                self.assertEqual(json.loads(listed.split(": ", 1)[1]), exempt + allow)
                bun = tomllib.loads(self.render("dot_bunfig.toml.tmpl", override))
                self.assertEqual(bun["install"]["minimumReleaseAge"], 604800)
                self.assertEqual(bun["install"]["minimumReleaseAgeExcludes"],
                                 [n for n in exempt if "*" not in n] + allow)
                self.assertEqual(json.loads(self.render("dot_config/npm-cooldown/allow.json.tmpl", override)), allow)

    def test_nuc_git_installer_manifest_and_render(self):
        data = json.loads((ROOT / ".chezmoidata/linux.json").read_text())["linux"]
        self.assertTrue({"libssl-dev", "libcurl4-openssl-dev", "gettext"} <= set(data["apt"]["nuc"]))
        installer = next(i for i in data["installers"]["nuc"] if i["bin"] == "git-2.56.0")
        cmd = installer["cmd"]
        self.assertIn("26c56c296b38c0695b26fa95f475f1d01704d2d38e73465ca30b0b2f5dc789d3", cmd)
        self.assertLess(cmd.index("sha256sum -c"), cmd.index("tar -xJf"))
        self.assertLess(cmd.index("--version"), cmd.index("ln -sfn"))
        self.assertIn('"$HOME/.local/bin/git" --version', installer["check"])
        self.assertIn("git version 2.56.0", installer["check"])
        self.assertIn("NO_TCLTK=YesPlease NO_RUST=YesPlease all", cmd)
        self.assertIn("NO_TCLTK=YesPlease NO_RUST=YesPlease install", cmd)
        bindir = self.home / ".local/bin"
        bindir.mkdir(parents=True)
        sentinel = bindir / "git-2.56.0"
        sentinel.write_text("#!/bin/sh\necho git version 2.56.0\n")
        sentinel.chmod(0o755)
        env = dict(os.environ, HOME=str(self.home))
        def check():
            return subprocess.run([BASH, "-c", installer["check"]], env=env).returncode
        self.assertNotEqual(check(), 0)  # The sentinel alone cannot mask a partial install.
        git = bindir / "git"
        git.write_text("#!/bin/sh\necho git version 2.30.2\n")
        git.chmod(0o755)
        self.assertNotEqual(check(), 0)
        git.write_text("#!/bin/sh\necho git version 2.56.0\n")
        self.assertEqual(check(), 0)
        git.unlink()
        self.configure("nuc")
        setup = '''have() { return 0; }
npm() { echo 11.21.0; }
bash() { printf '%s' "$2" >"$HOME/installer-command"; }'''
        result = self.section(self.render(self.CONVERGE), "linux_tools", setup)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / "installer-command").read_text(), cmd)
        for host, expected in (("nuc", True), ("agentbox-box", False), ("mac-pro", False)):
            self.configure(host)
            self.assertEqual(installer["check"] in self.render(self.CONVERGE), expected)
            self.assertNotIn('have "git-2.56.0"', self.render(self.CONVERGE))

    def test_linux_tools_installs_cli_with_pnpm(self):
        self.configure("nuc")
        script = self.render(self.CONVERGE)
        git = self.home / ".local/bin/git"
        git.parent.mkdir(parents=True)
        git.write_text("#!/bin/sh\necho git version 2.56.0\n")
        git.chmod(0o755)
        setup = """have() { case $1 in pi-acp|codex|opencode|paseo|vercel) return 1;; *) return 0;; esac; }
npm() { [ "$1" = --version ] && echo 11.21.0; }
pnpm() { echo "pnpm $*" >>"$HOME/calls"; }"""
        result = self.section(script, "linux_tools", setup)
        self.assertTrue(result.stdout.endswith("\nfailed=\n"), result.stdout + result.stderr)
        self.assertEqual((self.home / "calls").read_text().splitlines(), [
            "pnpm add -g pi-acp",
            "pnpm add -g @openai/codex",
            "pnpm add -g --allow-build=@opencode/cli @opencode/cli",
            "pnpm add -g @getpaseo/cli",
            "pnpm add -g vercel",
        ])
        self.assertNotIn('npm install -g --no-fund --no-audit "@openai/codex"', script)

    def test_npm_cli_migration_retires_npm_copies(self):
        loop = "for pkg in pi-acp @openai/codex @opencode/cli @getpaseo/cli vercel; do"
        for host, expected in (("nuc", True), ("mac-pro", False)):
            with self.subTest(host=host):
                self.configure(host)
                self.assertEqual(loop in self.render(self.CONVERGE), expected)

    def retire_plan_obsidian(self):
        script = self.render(self.CONVERGE)
        marker = "# 2026-11-09: retire plan-to-Obsidian auto-save"
        start = script.index(marker)
        end = script.index("\nPY\n", start) + len("\nPY\n")
        return self.run_script("f() {\n" + script[start:end] + "}\nf")

    def test_plan_obsidian_retirement_on_every_host(self):
        path = self.home / ".pi/agent/pi-plan-mode.json"
        path.parent.mkdir(parents=True)
        for host in self.HOSTS:
            self.configure(host)
            for prefix in ("$HOME", "~", str(self.home)):
                with self.subTest(host=host, prefix=prefix):
                    data = {"planCompleteCommand": ["bash", prefix + "/.claude/hooks/save-plan-to-obsidian.sh"],
                            "planners": ["personal"], "other": {"keep": True}}
                    path.write_text(json.dumps(data))
                    path.chmod(0o600)
                    result = self.retire_plan_obsidian()
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "retired: plan-to-Obsidian auto-save command\n")
                    self.assertEqual(json.loads(path.read_text()), {"planners": ["personal"], "other": {"keep": True}})
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                    once = path.read_bytes()
                    result = self.retire_plan_obsidian()
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(path.read_bytes(), once)

    def test_plan_obsidian_retirement_preserves_absent_custom_and_invalid_inputs(self):
        path = self.home / ".pi/agent/pi-plan-mode.json"
        result = self.retire_plan_obsidian()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertFalse(path.exists())
        path.parent.mkdir(parents=True)
        for data in ({}, {"planCompleteCommand": []},
                     {"planCompleteCommand": ["bash", "/custom/save.sh", 42]},
                     {"planCompleteCommand": "save-plan-to-obsidian.sh"},
                     {"planCompleteCommand": None}, {"planCompleteCommand": {}},
                     [], None, 7, "custom"):
            with self.subTest(data=data):
                original = json.dumps(data) + "  \n"
                path.write_text(original)
                result = self.retire_plan_obsidian()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(path.read_text(), original)
        for original in ("", "{not json"):
            with self.subTest(original=original):
                path.write_text(original)
                result = self.retire_plan_obsidian()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(path.read_text(), original)

    def retire_plan_settings(self):
        script = self.render(self.CONVERGE)
        start = script.rindex('python3 -B - "$HOME/.pi/agent/pi-plan-mode.json"', 0, script.index('legacy = {'))
        end = script.index("\nPY\n", start) + len("\nPY\n")
        return self.run_script("f() {\n" + script[start:end] + "}\nf")

    def test_plan_retirement_removes_only_matching_legacy_values(self):
        legacy = {
            "anthropic/claude-fable-5-1": "anthropic/claude-opus-5-5:high",
            "anthropic/claude-opus-5-5": "anthropic/claude-sonnet-5-5:high",
            "openai-codex/gpt-6-astra": "openai-codex/gpt-6.1-terra:high",
            "openai-codex/gpt-6.1-sol": "openai-codex/gpt-6.1-terra:high",
        }
        path = self.home / ".pi/agent/pi-plan-mode.json"
        path.parent.mkdir(parents=True)
        for host in self.HOSTS:
            self.configure(host)
            for model, value in legacy.items():
                with self.subTest(host=host, model=model):
                    data = {"implementationModelMap": dict(legacy, unrelated=value),
                            "scoutModelMap": {model: value}, "planners": ["personal"]}
                    # Exercise each custom override at every legacy key, alongside
                    # matching values at the other keys.
                    for custom in (value, "personal:model:low", [], [value], ["personal:model:high"]):
                        data["implementationModelMap"][model] = custom
                        path.write_text(json.dumps(data))
                        path.chmod(0o600)
                        result = self.retire_plan_settings()
                        self.assertEqual(result.returncode, 0, result.stderr)
                        expected = {"unrelated": value}
                        if custom != value:
                            expected[model] = custom
                        self.assertEqual(json.loads(path.read_text()),
                                         dict(data, implementationModelMap=expected))
                        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                        once = path.read_bytes()
                        result = self.retire_plan_settings()
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout, "")
                        self.assertEqual(path.read_bytes(), once)

    def test_plan_retirement_absent_and_invalid_inputs(self):
        path = self.home / ".pi/agent/pi-plan-mode.json"
        result = self.retire_plan_settings()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertFalse(path.exists())
        path.parent.mkdir(parents=True)
        for data in ({}, {"implementationModelMap": {}},
                     {"implementationModelMap": []}, {"implementationModelMap": None},
                     {"implementationModelMap": "custom"}, [], None, 7):
            with self.subTest(data=data):
                original = json.dumps(data) + "  \n"
                path.write_text(original)
                result = self.retire_plan_settings()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(path.read_text(), original)
        # Malformed JSON fails closed and retries on the next apply, never
        # replacing settings that cannot safely be inspected.
        for original in ("", "{not json"):
            path.write_text(original)
            result = self.retire_plan_settings()
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(path.read_text(), original)

    def retire_codex_plan_models(self):
        script = self.render(self.CONVERGE)
        marker = 'old, new = "openai-codex/", "openai/"'
        start = script.rindex('python3 -B - "$HOME/.pi/agent/pi-plan-mode.json"', 0, script.index(marker))
        end = script.index("\nPY\n", start) + len("\nPY\n")
        return self.run_script("f() {\n" + script[start:end] + "}\nf")

    def test_plan_retirement_moves_openai_codex_models(self):
        path = self.home / ".pi/agent/pi-plan-mode.json"
        result = self.retire_codex_plan_models()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(path.exists())
        path.parent.mkdir(parents=True)
        self.configure(self.HOSTS[0])
        data = {
            "planners": ["openai-codex/gpt-6-astra:xhigh", "anthropic/claude-fable-5-1:xhigh",
                         "openai/gpt-6-astra:xhigh"],
            "scoutModelMap": {
                "anthropic/claude-opus-5-5": "anthropic/claude-sonnet-5-5:medium",
                "openai-codex/gpt-6-astra": "openai-codex/gpt-6.1-terra:low",
                "openai/gpt-6-astra": "openai/gpt-6.1-terra:medium",
                "openai-codex/gpt-6.1-sol": "openai-codex/gpt-6.1-terra:medium",
            },
            "implementationModelMap": {},
            "plannerTimeoutSeconds": 5400,
        }
        path.write_text(json.dumps(data))
        path.chmod(0o600)
        result = self.retire_codex_plan_models()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(path.read_text()), {
            "planners": ["openai/gpt-6-astra:xhigh", "anthropic/claude-fable-5-1:xhigh"],
            "scoutModelMap": {
                "anthropic/claude-opus-5-5": "anthropic/claude-sonnet-5-5:medium",
                # The live legacy value wins over the seeded default.
                "openai/gpt-6-astra": "openai/gpt-6.1-terra:low",
                "openai/gpt-6.1-sol": "openai/gpt-6.1-terra:medium",
            },
            "implementationModelMap": {},
            "plannerTimeoutSeconds": 5400,
        })
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        once = path.read_bytes()
        result = self.retire_codex_plan_models()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(path.read_bytes(), once)
        for original in ("[]", "{}", '{"planners": null}'):
            path.write_text(original)
            result = self.retire_codex_plan_models()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(path.read_text(), original)
        path.write_text("{not json")
        self.assertNotEqual(self.retire_codex_plan_models().returncode, 0)

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
        commits = json.loads((ROOT / ".chezmoidata/pi_tag_commits.json").read_text())["piTagCommits"]
        git = {}
        for s in sources:
            if s.startswith("git:"):
                path, ref = s.removeprefix("git:").split("@")
                git[path] = ref if re.fullmatch("[0-9a-f]{40}", ref) else commits[s]
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.configure(host)
                script = self.render(self.CONVERGE)
                for source in sources:
                    verb = "update" if source.startswith("git:") else "install"
                    self.assertIn('pi %s "%s"' % (verb, source), script)
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
        self.assertNotIn("pi install", result.stdout)
        self.assertIn("failed=\n", result.stdout)
        request = self.home / ".pi/agent/reload-request"
        self.assertFalse(request.exists(), "nothing installed, nothing to reload")
        # Off pin and installed: running sessions are asked to reload (pi-reload-all).
        mock = 'git() { echo 0000; }; pi() { echo "pi $*"; }'
        result = self.section(script, "pi_packages", mock)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(request.read_text())["id"].startswith("converge-"))
        request.unlink()
        # Off pin: only the Git packages are updated, and a failing pi fails the section.
        mock = 'git() { echo 0000; }; pi() { echo "pi $*"; return 19; }'
        result = self.section(script, "pi_packages", mock)
        for path in git:
            self.assertIn("pi update git:%s@" % path, result.stdout)
        self.assertNotIn("pi update npm:", result.stdout)
        self.assertNotIn("pi install npm:", result.stdout)
        self.assertIn("failed=pi_packages", result.stdout)
        # An npm package off its pin is installed at the pin with `pi install`.
        pinned = next(s for s in sources if s.startswith("npm:") and s.rfind("@") > 4)
        spec = pinned.removeprefix("npm:")
        (self.home / ".pi/agent/npm/node_modules" / spec[:spec.rfind("@")] / "package.json").write_text(
            '{\n  "version": "0.0.1"\n}\n')
        heads = " ".join('*%s) echo %s ;;' % (path, ref) for path, ref in git.items())
        mock = 'git() { case "$2" in %s esac; }; pi() { echo "pi $*"; }' % heads
        result = self.section(script, "pi_packages", mock)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pi install %s" % pinned, result.stdout)
        self.assertNotIn("pi update", result.stdout)

    def test_pi_tag_pins_have_commits(self):
        packages = json.loads((ROOT / "private_dot_pi/private_agent/settings.managed.json").read_text())["packages"]
        sources = [p if isinstance(p, str) else p["source"] for p in packages]
        tags = [s for s in sources if s.startswith("git:") and not re.fullmatch("[0-9a-f]{40}", s.split("@")[1])]
        commits = json.loads((ROOT / ".chezmoidata/pi_tag_commits.json").read_text())["piTagCommits"]
        for source in tags:
            self.assertRegex(commits.get(source, ""), "^[0-9a-f]{40}$", source)
        self.assertEqual(set(commits), set(tags), "stale or missing tag commits")

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
            "codex-cache-guard", "agent-scrub", "claude-code-playground")})
        self.assertEqual(set(skills), {".agents/skills/find-skills", ".agents/skills/slackcli", ".agents/skills/vercel-cli"})
        for target, external in (plugins | skills).items():
            self.assertEqual(external["type"], "archive")
            self.assertTrue(external["exact"])
            self.assertRegex(external["url"], r"/archive/[0-9a-f]{40}\.tar\.gz$")
            self.assertRegex(external["checksum"]["sha256"], r"^[0-9a-f]{64}$")

    RETIRED_CLAUDE = ("claude-auto-effort", "claude-cache-guard", "claude-marimo",
                      "claude-prose-width", "claude-tool-gate")

    def test_retired_plugin_loading_per_host(self):
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.configure(host)
                config = self.render("dot_config/opencode/opencode.jsonc.tmpl")
                # JSONC comments occupy whole lines; preserve URL strings.
                config = json.loads("\n".join(l for l in config.splitlines()
                                              if not l.lstrip().startswith("//")))
                self.assertEqual(config["plugins"], [
                    "@ex-machina/opencode-anthropic-auth@2.0.0-next.5",
                    "@cortexkit/opencode-antigravity-auth@3.0.0",
                ])
                cli = json.loads(self.render("dot_config/opencode/cli.json.tmpl"))
                self.assertEqual(cli["plugins"], ["./herdr-opencode"])
                shell = self.render("dot_zshenv.tmpl")
                externals = self.render(".chezmoiexternal.toml.tmpl")
                for name in self.RETIRED_CLAUDE:
                    self.assertNotIn(name, shell)
                    self.assertNotIn(name, externals)
                self.assertIn("claude-code-playground/claude-code/mods/token-weather", shell)

    @unittest.skipUnless(shutil.which("zsh"), "zsh is not installed")
    def test_claude_loads_only_existing_token_weather(self):
        shell = self.render("dot_zshenv.tmpl")
        start = shell.index("() {\n")
        loader = shell[start:shell.index("\n}\n", start) + 3]
        for name in self.RETIRED_CLAUDE:
            (self.home / ".local/share/plugins" / name).mkdir(parents=True)
        token = self.home / ".local/share/plugins/claude-code-playground/claude-code/mods/token-weather"
        env = dict(os.environ, HOME=str(self.home))
        env.pop("CLAUDE_CODE_PLUGIN_DIRS", None)
        for exists in (False, True):
            if exists:
                token.mkdir(parents=True)
            result = subprocess.run([shutil.which("zsh"), "-f", "-c",
                                     loader + '\nprint -r -- "${CLAUDE_CODE_PLUGIN_DIRS-unset}"'],
                                    env=env, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, (str(token) if exists else "unset") + "\n")

    def retired_claude_script(self):
        script = self.render(self.CONVERGE)
        start = script.index("for plugin in claude-auto-effort ")
        end = script.index("\ndone\n", start) + len("\ndone\n")
        return 'gone() { echo "retired: $*"; }\nf() {\n' + script[start:end] + "}\nf\n"

    def test_retired_claude_archives_removed_once(self):
        plugins = self.home / ".local/share/plugins"
        for name in self.RETIRED_CLAUDE:
            archive = plugins / name
            archive.mkdir(parents=True)
            (archive / "index.ts").write_text("archive")
        for name in ("unrelated", "claude-code-playground"):
            (plugins / name).mkdir()
        for host in self.HOSTS:
            self.configure(host)
            result = self.run_script(self.retired_claude_script())
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = ["retired: " + str(plugins / n) for n in self.RETIRED_CLAUDE]
            self.assertEqual(result.stdout.splitlines(), expected if host == self.HOSTS[0] else [])
            for name in self.RETIRED_CLAUDE:
                self.assertFalse((plugins / name).exists())
            self.assertTrue((plugins / "unrelated").is_dir())
            self.assertTrue((plugins / "claude-code-playground").is_dir())
            result = self.run_script(self.retired_claude_script())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")

    def test_retired_claude_preserves_checkouts_and_symlinks(self):
        plugins = self.home / ".local/share/plugins"
        plugins.mkdir(parents=True)
        (plugins / self.RETIRED_CLAUDE[0] / ".git").mkdir(parents=True)
        worktree = plugins / self.RETIRED_CLAUDE[1]
        worktree.mkdir()
        (worktree / ".git").write_text("gitdir: elsewhere")
        target = self.home / "local-work"
        target.mkdir()
        (plugins / self.RETIRED_CLAUDE[2]).symlink_to(target, target_is_directory=True)
        (plugins / self.RETIRED_CLAUDE[3]).symlink_to(self.home / "missing")
        archive = plugins / self.RETIRED_CLAUDE[4]
        archive.mkdir()
        (archive / ".git").symlink_to(self.home / "missing-git")
        result = self.run_script(self.retired_claude_script())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        for name in self.RETIRED_CLAUDE:
            self.assertTrue(os.path.lexists(plugins / name))
        self.assertTrue(target.is_dir())

    def test_retired_claude_removal_failure_propagates(self):
        archive = self.home / ".local/share/plugins" / self.RETIRED_CLAUDE[0]
        archive.mkdir(parents=True)
        result = self.run_script(self.retired_claude_script(), "rm() { return 1; }")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertTrue(archive.is_dir())

    RETIRED_ZINIT = (
        "Aloxaf---fzf-tab",
        "chriskempson---base16-shell",
        "matheusml---zsh-ai",
        "starship---starship",
        "termoshtt---zaw-systemd",
        "zdharma-continuum---null",
        "zsh-users---zaw",
        "zsh-users---zsh-autosuggestions",
    )

    def retired_zinit_script(self):
        script = self.render(self.CONVERGE)
        start = script.index('zinit_plugins="${XDG_DATA_HOME:-$HOME/.local/share}/zinit/plugins"')
        end = script.index("\ndone\n", start) + len("\ndone\n")
        return 'gone() { echo "retired: $*"; }\nf() {\n' + script[start:end] + "}\nf\n"

    def test_retired_zinit_plugins_removed_once(self):
        plugins = self.home / ".local/share/zinit/plugins"
        for name in self.RETIRED_ZINIT:
            (plugins / name).mkdir(parents=True)
        active = ("zdharma-continuum---fast-syntax-highlighting",
                  "zsh-users---zsh-completions", "oknowton---zsh-dwim", "_local---zinit")
        for name in active:
            (plugins / name).mkdir(parents=True)
        for host in self.HOSTS:
            self.configure(host)
            result = self.run_script(self.retired_zinit_script())
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = ["retired: zinit plugin " + n for n in self.RETIRED_ZINIT]
            self.assertEqual(result.stdout.splitlines(), expected if host == self.HOSTS[0] else [])
            for name in self.RETIRED_ZINIT:
                self.assertFalse((plugins / name).exists())
            for name in active:
                self.assertTrue((plugins / name).is_dir())
            result = self.run_script(self.retired_zinit_script())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
        target = plugins / self.RETIRED_ZINIT[0]
        target.mkdir(parents=True)
        result = self.run_script(self.retired_zinit_script(), "rm() { return 1; }")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(target.is_dir())

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
