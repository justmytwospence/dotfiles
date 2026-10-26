"""Check both menu-bar states without changing the Mac's sleep settings."""
from pathlib import Path
import subprocess
import unittest


PLUGIN = (Path(__file__).resolve().parents[1] / "dot_config/swiftbar/plugins/"
          "executable_lid-caffeine.30s.sh")


class LidCaffeineTests(unittest.TestCase):
    def render(self, state):
        # Substitute only the state reader; never invoke real pmset or sudo.
        script = PLUGIN.read_text().replace(
            'PMSET=/usr/bin/pmset',
            f'fake_pmset() {{ printf "SleepDisabled {state}\\n"; }}\nPMSET=fake_pmset')
        return subprocess.run(["/bin/bash", "-s"], input=script, text=True,
                              capture_output=True, check=True).stdout

    def test_awake_mode_has_filled_monochrome_icon(self):
        output = self.render(1)
        self.assertIn("sfimage=cup.and.saucer.fill", output.splitlines()[0])
        self.assertIn("ON", output.splitlines()[0])
        self.assertNotIn("color=", output)
        self.assertIn("param1=off", output)

    def test_normal_sleep_has_outline_monochrome_icon(self):
        output = self.render(0)
        self.assertIn("sfimage=cup.and.saucer ", output.splitlines()[0])
        self.assertIn("OFF", output.splitlines()[0])
        self.assertNotIn("color=", output)
        self.assertIn("param1=on", output)


if __name__ == "__main__":
    unittest.main()
