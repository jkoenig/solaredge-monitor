"""Tests for the location guard of install.sh (fake sudo on PATH, temp dirs only)."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
UNIT = ROOT / "solaredge-monitor.service"
EXPECTED_DIR = "/home/pi/solaredge-monitor"


class InstallLocationGuardTest(unittest.TestCase):
    def run_install(self, with_unit=True):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            shutil.copy(INSTALL, tmp / "install.sh")
            if with_unit:
                shutil.copy(UNIT, tmp / "solaredge-monitor.service")
            bindir = tmp / "bin"
            bindir.mkdir()
            # Fakes so that nothing real could run even if the guard were missing.
            for name in ("sudo", "python3", "groups"):
                p = bindir / name
                p.write_text(
                    '#!/bin/bash\necho "$@" >> "%s/%s.log"\nexit 1\n' % (tmp, name)
                )
                p.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = "%s:%s" % (bindir, env["PATH"])
            r = subprocess.run(
                ["bash", str(tmp / "install.sh")],
                capture_output=True, text=True, timeout=30, env=env, cwd=str(tmp),
            )
            touched = sorted(
                p.name for p in tmp.iterdir()
                if p.name not in ("install.sh", "solaredge-monitor.service", "bin")
            )
            return r, touched

    def test_wrong_directory_stops_before_any_change(self):
        r, touched = self.run_install()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("the systemd unit expects %s" % EXPECTED_DIR, r.stdout)
        self.assertNotIn("[1/6]", r.stdout)
        self.assertEqual(touched, [])  # no sudo/python3 call logs, no venv, no .env

    def test_missing_unit_file_stops(self):
        r, touched = self.run_install(with_unit=False)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("[1/6]", r.stdout)
        self.assertEqual(touched, [])

    def test_guard_reads_the_path_from_the_unit_and_precedes_sudo(self):
        text = INSTALL.read_text()
        self.assertNotIn(EXPECTED_DIR, text)  # single source: the unit file
        guard = text.index("UNIT_DIR=")
        self.assertLess(text.index('"$EUID" -eq 0'), guard)
        self.assertLess(guard, text.index("sudo "))
        self.assertIn("WorkingDirectory=%s\n" % EXPECTED_DIR, UNIT.read_text())


if __name__ == "__main__":
    unittest.main()
