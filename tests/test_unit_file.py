"""Tests for the systemd unit file (OPS-01: start only after time sync)."""
import configparser
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIT = ROOT / "solaredge-monitor.service"


def load_unit():
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    cp.optionxform = str
    cp.read_string(UNIT.read_text())
    return cp


class UnitFileTest(unittest.TestCase):
    def test_wants_network_online_and_time_wait_sync(self):
        wants = load_unit()["Unit"]["Wants"].split()
        self.assertIn("network-online.target", wants)
        self.assertIn("systemd-time-wait-sync.service", wants)

    def test_after_network_online_and_time_sync(self):
        after = load_unit()["Unit"]["After"].split()
        self.assertIn("network-online.target", after)
        self.assertIn("time-sync.target", after)
        self.assertNotIn("network.target", after)

    def test_no_timeout_keys(self):
        text = UNIT.read_text()
        for key in ("JobTimeoutSec", "JobRunningTimeoutSec", "TimeoutStartSec"):
            self.assertNotIn(key, text)

    def test_service_and_install_sections_kept(self):
        cp = load_unit()
        svc = cp["Service"]
        self.assertEqual(svc["User"], "pi")
        self.assertEqual(svc["WorkingDirectory"], "/home/pi/solaredge-monitor")
        self.assertEqual(
            svc["ExecStart"],
            "/home/pi/solaredge-monitor/venv/bin/python3 main.py",
        )
        self.assertEqual(svc["Restart"], "always")
        self.assertEqual(cp["Install"]["WantedBy"], "multi-user.target")

    def test_install_sh_installs_unit_root_owned(self):
        text = (ROOT / "install.sh").read_text()
        self.assertIn(
            "sudo install -m 644 -o root -g root solaredge-monitor.service", text
        )

    def test_shell_scripts_parse(self):
        for name in ("install.sh", "deploy.sh"):
            r = subprocess.run(["bash", "-n", str(ROOT / name)], capture_output=True)
            self.assertEqual(r.returncode, 0, name)


if __name__ == "__main__":
    unittest.main()
