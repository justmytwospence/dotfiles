import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'dot_local/bin/executable_orca-setup'


class OrcaSetupTests(unittest.TestCase):
    def test_linux_dispatch_and_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / 'calls'
            for name, body in {
                'uname': 'echo Linux',
                'docker': '''printf '%s\\n' "$*" >> "$CALLS"
case "$*" in
  *status*) echo '{"ok":true,"result":{"runtime":{"state":"ready","appVersion":"test"}}}' ;;
  *'repo add'*) echo '{"ok":true,"result":{"repo":{"id":"fixture"}}}' ;;
  *) echo '{}' ;;
esac''',
            }.items():
                command = root / name
                command.write_text('#!/bin/sh\n' + body + '\n')
                command.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + ':' + os.environ['PATH'], CALLS=str(log))
            def run(*args):
                return subprocess.run(['bash', str(SCRIPT), *args], env=env, capture_output=True, text=True)
            self.assertEqual(run().returncode, 0)
            self.assertEqual(run('register', str(root)).returncode, 0)
            self.assertEqual(run('cli', 'repo', 'list', '--json').returncode, 0)
            calls = log.read_text()
            self.assertIn('exec orca /opt/host-home/enter.sh orca-ide repo add --path ' + str(root), calls)
            self.assertIn('exec orca /opt/host-home/enter.sh orca-ide repo list --json', calls)
            self.assertIn('project setup-update --setup fixture --worktree-base-path ' + str(root) + '/.worktrees', calls)
            self.assertNotIn('worktree create', calls)
            self.assertEqual(run('register').returncode, 2)
            self.assertEqual(run('register', 'relative').returncode, 2)
            (root / 'docker').write_text('#!/bin/sh\necho \'{"ok":true,"result":{"runtime":{"state":"stopped"}}}\'\n')
            self.assertNotEqual(run().returncode, 0)

    def test_mac_checks_nuc_and_refuses_local_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / 'calls'
            uname = root / 'uname'
            uname.write_text('#!/bin/sh\necho Darwin\n')
            uname.chmod(0o755)
            cli = root / 'Applications/Orca.app/Contents/Resources/bin/orca'
            cli.parent.mkdir(parents=True)
            cli.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$CALLS"
echo '{"ok":true,"result":{"runtime":{"state":"ready","appVersion":"test"}}}'
''')
            cli.chmod(0o755)
            for name in ('claude', 'codex', 'pi', 'opencode'):
                agent = root / name
                agent.write_text('#!/bin/sh\nexit 0\n')
                agent.chmod(0o755)
            env = dict(os.environ, HOME=str(root), PATH=str(root) + ':' + os.environ['PATH'], CALLS=str(log),
                       ORCA_CLI=str(cli))
            result = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('status --environment NUC --json', log.read_text())
            before = log.read_text()
            result = subprocess.run(['bash', str(SCRIPT), 'register', str(root)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(log.read_text(), before)
            self.assertNotIn('ws://mac-pro', result.stdout)


if __name__ == '__main__':
    unittest.main()
