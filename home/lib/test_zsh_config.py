"""Unit tests for Zsh configuration, directory tracking, caching, and gencmd."""
import json
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHEZMOI = shutil.which("chezmoi")
ZSH = shutil.which("zsh")


@unittest.skipUnless(ZSH and CHEZMOI, "zsh and chezmoi are required")
class ZshConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        self.config = self.base / "chezmoi.toml"
        self.config.write_text('[data]\nhost = "mac-pro"\nrole = "pro"\nextras = ""\n')

    def render(self, path):
        return subprocess.check_output([
            CHEZMOI, "--config", str(self.config), "--source", str(ROOT),
            "execute-template", "--file", str(ROOT / path),
        ], text=True)

    def test_path_order_preserved_across_zshenv_and_zprofile(self):
        zshenv = self.base / ".zshenv"
        zshenv.write_text(self.render("dot_zshenv.tmpl"))
        zprofile = ROOT / "dot_zprofile"
        cargo_bin = self.home / ".cargo/bin"
        cargo_bin.mkdir(parents=True)
        nvm_bin = self.home / ".nvm/versions/node/v24.1.0/bin"
        nvm_bin.mkdir(parents=True)
        alias_dir = self.home / ".nvm/alias"
        alias_dir.mkdir(parents=True)
        (alias_dir / "default").write_text("lts/*\n")
        (alias_dir / "lts").mkdir()
        (alias_dir / "lts/*" if False else alias_dir / "default").write_text("24.1.0\n")

        script = (
            'export HOME="$1"\n'
            'export PATH="/usr/bin:/bin:/usr/sbin:/sbin"\n'
            'source "$2"\n'
            '# Simulate /etc/zprofile path_helper moving /usr/bin to the front\n'
            'export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"\n'
            'source "$3"\n'
            'print -l -- "${path[@]}"\n'
        )
        res = subprocess.run(
            [ZSH, "-f", "-c", script, "test", str(self.home), str(zshenv), str(zprofile)],
            capture_output=True, text=True, check=True,
        )
        entries = res.stdout.splitlines()
        self.assertEqual(len(entries), len(set(entries)), "path entries must be unique")
        idx = lambda p: entries.index(p)
        self.assertLess(idx(str(cargo_bin)), idx("/usr/bin"))
        self.assertLess(idx(str(nvm_bin)), idx("/usr/bin"))
        self.assertLess(idx(str(self.home / ".local/bin")), idx("/usr/bin"))
        self.assertLess(idx("/usr/local/bin"), idx("/usr/bin"))

    def test_keybindings_order_and_widgets(self):
        keybindings = ROOT / "dot_zsh/keybindings.zsh"
        pid, fd = pty.fork()
        if pid == 0:
            os.execvp(ZSH, [ZSH, "-f", "-i"])
        try:
            cmd = (
                f"source {str(keybindings)!r}; "
                "print -r -- \"MAIN=$(bindkey -lL main)\"; "
                "for k in '^g' '^z' '^h' '^w' '^p' '^n' '^[[A' '^[OA' '^[[B' '^[OB' '^x^e'; do "
                "  print -r -- \"VIINS:$k=$(bindkey -M main $k)\"; "
                "done; "
                "for k in '^g' '^k' '^[[A' '^[OA' '^[[B' '^[OB' '^x^e'; do "
                "  print -r -- \"VICMD:$k=$(bindkey -M vicmd $k)\"; "
                "done; "
                "exit\r"
            )
            os.write(fd, cmd.encode())
            out = b""
            while True:
                r, _, _ = select.select([fd], [], [], 2.0)
                if not r:
                    break
                try:
                    chunk = os.read(fd, 4096)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
            os.waitpid(pid, 0)

        text = out.decode("utf-8", "replace")
        self.assertIn("MAIN=bindkey -A viins main", text)
        self.assertIn('VIINS:^g="^G" gencmd-widget', text)
        self.assertIn('VIINS:^z="^Z" fancy-ctrl-z', text)
        self.assertIn('VIINS:^h="^H" backward-kill-word', text)
        self.assertIn('VIINS:^w="^W" backward-delete-word', text)
        self.assertIn('VIINS:^p="^P" history-beginning-search-backward', text)
        self.assertIn('VIINS:^n="^N" history-beginning-search-forward', text)
        self.assertIn('VIINS:^[[A="^[[A" history-beginning-search-backward', text)
        self.assertIn('VIINS:^[OA="^[OA" history-beginning-search-backward', text)
        self.assertIn('VIINS:^[[B="^[[B" history-beginning-search-forward', text)
        self.assertIn('VIINS:^[OB="^[OB" history-beginning-search-forward', text)
        self.assertIn('VIINS:^x^e="^X^E" edit-command-line', text)
        self.assertIn('VICMD:^g="^G" gencmd-widget', text)
        self.assertIn('VICMD:^k="^K" kill-line', text)
        self.assertIn('VICMD:^[[A="^[[A" history-beginning-search-backward', text)
        self.assertIn('VICMD:^[[B="^[[B" history-beginning-search-forward', text)

    def test_directory_tracking_updates_prompt_pwd_and_window(self):
        repo = self.base / "projects/sample-repo"
        sub = repo / "src/pkg"
        sub.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)

        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        tmux_log = self.base / "tmux.log"
        tmux_mock = bin_dir / "tmux"
        tmux_mock.write_text('#!/bin/sh\necho "$*" >> "$TMUX_LOG"\n')
        tmux_mock.chmod(0o755)

        dt = ROOT / "dot_zsh/directory_tracking.zsh"
        prompt = ROOT / "dot_zsh/prompt.zsh"
        script = (
            'cd "$1"\n'
            'export TMUX=1 SSH_CONNECTION="1.2.3.4 1234 5.6.7.8 22"\n'
            'unset SSH_TTY\n'
            'source "$2"\n'
            'source "$3"\n'
            'print -r -- "PWD1=$_prompt_pwd"\n'
            'print -r -- "HOST=$_prompt_host"\n'
            'print -r -- "PRECMD=${precmd_functions[*]}"\n'
            'cd "$4"\n'
            'print -r -- "PWD2=$_prompt_pwd"\n'
        )
        env = dict(
            os.environ,
            HOME=str(self.home),
            PATH=f"{bin_dir}:{os.environ['PATH']}",
            TMUX_LOG=str(tmux_log),
        )
        res = subprocess.run(
            [ZSH, "-f", "-c", script, "test", str(sub), str(dt), str(prompt), str(self.home)],
            env=env, capture_output=True, text=True, check=True,
        )
        lines = dict(l.split("=", 1) for l in res.stdout.splitlines() if "=" in l)
        self.assertEqual(lines["PWD1"], "sample-repo/src/pkg")
        self.assertEqual(lines["PWD2"], "%~")
        self.assertEqual(lines["HOST"], "%F{red}@%m%f")
        self.assertNotIn("update-pwd-prompt", lines["PRECMD"])
        self.assertEqual(tmux_log.read_text().splitlines(), [
            "rename-window sample-repo",
            "rename-window home",
        ])

    def test_vivid_ls_colors_cached(self):
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        calls = self.base / "vivid.calls"
        vivid = bin_dir / "vivid"
        vivid.write_text(
            '#!/bin/sh\n'
            'echo "$*" >> "$VIVID_CALLS"\n'
            'echo "di=01;34:theme=$2"\n'
        )
        vivid.chmod(0o755)
        defaults = bin_dir / "defaults"
        defaults.write_text('#!/bin/sh\necho "Dark"\n')
        defaults.chmod(0o755)
        uname = bin_dir / "uname"
        uname.write_text('#!/bin/sh\necho "Darwin"\n')
        uname.chmod(0o755)

        comp = ROOT / "dot_zsh/completion.zsh"
        env = dict(
            os.environ,
            HOME=str(self.home),
            XDG_CACHE_HOME=str(self.base / "cache"),
            PATH=f"{bin_dir}:{os.environ['PATH']}",
            VIVID_CALLS=str(calls),
        )
        for _ in range(2):
            res = subprocess.run(
                [ZSH, "-f", "-c", 'source "$1"; print -r -- "$LS_COLORS"', "test", str(comp)],
                env=env, capture_output=True, text=True, check=True,
            )
            self.assertEqual(res.stdout.strip(), "di=01;34:theme=snazzy")
        self.assertEqual(calls.read_text().splitlines(), ["generate snazzy"])
        self.assertTrue((self.base / "cache/zsh/ls_colors.snazzy").is_file())

    def test_gencmd_uses_host_uname(self):
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        args_file = self.base / "claude_args.json"
        claude = bin_dir / "claude"
        claude.write_text(
            '#!/usr/bin/env python3\n'
            'import json, os, sys\n'
            'with open(os.environ["CLAUDE_ARGS"], "w") as f:\n'
            '    json.dump(sys.argv[1:], f)\n'
            'print("ls -la")\n'
        )
        claude.chmod(0o755)

        gencmd = ROOT / "dot_local/bin/executable_gencmd"
        env = dict(
            os.environ,
            PATH=f"{bin_dir}:{os.environ['PATH']}",
            CLAUDE_ARGS=str(args_file),
        )
        res = subprocess.run(
            ["bash", str(gencmd), "list files"],
            env=env, capture_output=True, text=True, check=True,
        )
        self.assertEqual(res.stdout.strip(), "ls -la")
        recorded = json.loads(args_file.read_text())
        sys_prompt = recorded[recorded.index("--system-prompt") + 1]
        expected_os = subprocess.check_output(["uname", "-s"], text=True).strip()
        self.assertIn(f"for zsh on {expected_os}.", sys_prompt)

    def test_vi_text_objects_bound(self):
        keybindings = ROOT / "dot_zsh/keybindings.zsh"
        pid, fd = pty.fork()
        if pid == 0:
            os.execvp(ZSH, [ZSH, "-f", "-i"])
        try:
            cmd = (
                f"source {str(keybindings)!r}; "
                "for km in viopp visual; do "
                "  for k in ib ab 'i(' 'a]' 'i\"' \"a'\"; do "
                "    print -r -- \"$km:$k=$(bindkey -M $km $k)\"; "
                "  done; "
                "done; "
                "exit\r"
            )
            os.write(fd, cmd.encode())
            out = b""
            while True:
                r, _, _ = select.select([fd], [], [], 2.0)
                if not r:
                    break
                try:
                    chunk = os.read(fd, 4096)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
            os.waitpid(pid, 0)

        text = out.decode("utf-8", "replace")
        for km in ("viopp", "visual"):
            self.assertIn(f'{km}:ib="ib" select-bracketed', text)
            self.assertIn(f'{km}:ab="ab" select-bracketed', text)
            self.assertIn(f'{km}:i(="i(" select-bracketed', text)
            self.assertIn(f'{km}:a]="a]" select-bracketed', text)
            self.assertIn(f'{km}:i"="i\\"" select-quoted', text)
            self.assertIn(f"{km}:a'=\"a'\" select-quoted", text)

    def test_yazi_wrapper_changes_directory(self):
        target = self.base / "target_dir"
        target.mkdir()
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        yazi = bin_dir / "yazi"
        yazi.write_text(
            '#!/bin/sh\n'
            'for arg in "$@"; do\n'
            '  case "$arg" in\n'
            '    --cwd-file=*) printf "%s" "$TARGET_DIR" > "${arg#--cwd-file=}" ;;\n'
            '  esac\n'
            'done\n'
        )
        yazi.chmod(0o755)
        funcs = ROOT / "dot_zsh/functions.zsh"
        env = dict(
            os.environ,
            PATH=f"{bin_dir}:{os.environ['PATH']}",
            TARGET_DIR=str(target),
        )
        res = subprocess.run(
            [ZSH, "-f", "-c", 'source "$1"; cd "$2"; y; print -r -- "$PWD"', "test", str(funcs), str(self.home)],
            env=env, capture_output=True, text=True, check=True,
        )
        self.assertEqual(Path(res.stdout.strip()).resolve(), target.resolve())

    def test_terminfo_fallback_when_unknown(self):
        zshenv = self.base / ".zshenv"
        zshenv.write_text(self.render("dot_zshenv.tmpl"))
        env = dict(os.environ, HOME=str(self.home), TERM="xterm-nonexistent-term-9999")
        res = subprocess.run(
            [ZSH, "-f", "-c", 'source "$1"; print -r -- "$TERM"', "test", str(zshenv)],
            env=env, capture_output=True, text=True, check=True,
        )
        self.assertEqual(res.stdout.strip(), "xterm-256color")

    def test_gitconfig_local_include_wins(self):
        gitconfig = self.home / ".gitconfig"
        gitconfig.write_text(self.render("dot_gitconfig.tmpl"))
        local = self.home / ".gitconfig.local"
        local.write_text("[user]\n\temail = local-override@example.com\n")
        env = dict(os.environ, HOME=str(self.home), GIT_CONFIG_NOSYSTEM="1")
        res = subprocess.run(
            ["git", "config", "--file", str(gitconfig), "--includes", "user.email"],
            env=env, capture_output=True, text=True, check=True,
        )
        self.assertEqual(res.stdout.strip(), "local-override@example.com")
        algo = subprocess.run(
            ["git", "config", "--file", str(gitconfig), "diff.algorithm"],
            env=env, capture_output=True, text=True, check=True,
        )
        self.assertEqual(algo.stdout.strip(), "histogram")

    def test_atuin_config_valid_toml(self):
        cfg = tomllib.loads((ROOT / "dot_config/atuin/private_config.toml").read_text())
        self.assertTrue(cfg["enter_accept"])
        self.assertTrue(cfg["workspaces"])
        self.assertTrue(cfg["secrets_filter"])
        self.assertEqual(cfg["keymap_mode"], "auto")
        self.assertTrue(cfg["sync"]["records"])


if __name__ == "__main__":
    unittest.main()
