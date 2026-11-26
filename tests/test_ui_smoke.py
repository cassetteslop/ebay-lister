"""Runs tests/ui_smoke.py in a subprocess with the fake tkinter (tests/fake_tk) first on the path."""

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class UISmokeTest(unittest.TestCase):
    def test_app_flows_headless(self):
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([os.path.join(ROOT, "tests", "fake_tk"), ROOT]))
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "ui_smoke.py")], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("UI SMOKE OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
