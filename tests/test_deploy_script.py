"""Tests for deploy.sh using fake sudo/git/pip on PATH and temp dirs only."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy.sh"
UNIT = ROOT / "solaredge-monitor.service"

class DeployScriptTest(unittest.TestCase):
    def run_deploy(self, dst_mode, test_flag="1", dst_override=None):
        """dst_mode: 'missing', 'different' or 'identical'.

        test_flag: value for SOLAREDGE_DEPLOY_TEST (None = not set).
        dst_override: value for SOLAREDGE_UNIT_DST instead of the temp file.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            shutil.copy(DEPLOY, tmp / "deploy.sh")
            shutil.copy(UNIT, tmp / "solaredge-monitor.service")
            (tmp / "venv" / "bin").mkdir(parents=True)
            (tmp / "venv" / "bin" / "pip").write_text(
                '#!/bin/bash\necho "$@" >> "%s/pip.log"\nexit 0\n' % tmp
            )
            (tmp / "venv" / "bin" / "pip").chmod(0o755)
            bindir = tmp / "bin"
            bindir.mkdir()
            for name in ("git", "sudo"):
                p = bindir / name
                p.write_text(
                    '#!/bin/bash\necho "$@" >> "%s/%s.log"\nexit 0\n' % (tmp, name)
                )
                p.chmod(0o755)
            dst = tmp / "dst.service"
            if dst_mode == "different":
                dst.write_text("[Unit]\nDescription=old\n")
            elif dst_mode == "identical":
                shutil.copy(UNIT, dst)
            env = dict(os.environ)
            env["PATH"] = "%s:%s" % (bindir, env["PATH"])
            env["SOLAREDGE_UNIT_DST"] = dst_override or str(dst)
            env.pop("SOLAREDGE_DEPLOY_TEST", None)
            if test_flag is not None:
                env["SOLAREDGE_DEPLOY_TEST"] = test_flag
            r = subprocess.run(
                ["bash", str(tmp / "deploy.sh")],
                capture_output=True, text=True, timeout=30, env=env, cwd=str(tmp),
            )

            def log(name):
                f = tmp / (name + ".log")
                return f.read_text().splitlines() if f.exists() else []

            return r, log("sudo"), log("git"), log("pip"), str(tmp)

    def assert_in_order(self, lines, expected):
        idx = -1
        for want in expected:
            matches = [i for i, l in enumerate(lines) if l == want and i > idx]
            self.assertTrue(matches, "missing in order: %r in %r" % (want, lines))
            idx = matches[0]

    def test_changed_unit_is_installed(self):
        for mode in ("missing", "different"):
            r, sudo, git, pip, tmp = self.run_deploy(mode)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Unit file changed", r.stdout)
            self.assert_in_order(sudo, [
                "install -m 644 -o root -g root %s/solaredge-monitor.service %s/dst.service"
                % (tmp, tmp),
                "systemctl daemon-reload",
                "systemctl enable solaredge-monitor",
                "systemctl restart solaredge-monitor",
            ])
            self.assertIn("pull", git)
            self.assertIn("install -r requirements.txt -q", pip)

    def test_unchanged_unit_is_left_alone(self):
        r, sudo, git, pip, _ = self.run_deploy("identical")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Unit file unchanged", r.stdout)
        self.assertFalse([l for l in sudo if l.startswith("install")])
        self.assertNotIn("systemctl daemon-reload", sudo)
        self.assertIn("systemctl restart solaredge-monitor", sudo)

    REAL_DST = "/etc/systemd/system/solaredge-monitor.service"

    def assert_override_ignored(self, r, sudo, tmp):
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ignoring SOLAREDGE_UNIT_DST", r.stdout)
        self.assertNotIn("TEST MODE", r.stdout)
        installs = [l for l in sudo if l.startswith("install")]
        for line in installs:
            self.assertEqual(
                line,
                "install -m 644 -o root -g root %s/solaredge-monitor.service %s"
                % (tmp, self.REAL_DST),
            )
        self.assertFalse([l for l in sudo if "dst.service" in l])
        self.assertIn("systemctl restart solaredge-monitor", sudo)

    def test_override_ignored_without_test_flag(self):
        # sudo is the fake from run_deploy, nothing is written for real.
        for flag in (None, "", "0", "true"):
            r, sudo, _, _, tmp = self.run_deploy("different", test_flag=flag)
            self.assert_override_ignored(r, sudo, tmp)

    def test_override_ignored_for_unsafe_targets(self):
        for target in ("/etc/cron.d/x", "/etc", "/tmp/../etc/x", "relative/x"):
            r, sudo, _, _, tmp = self.run_deploy(
                "missing", test_flag="1", dst_override=target)
            self.assert_override_ignored(r, sudo, tmp)
            self.assertFalse([l for l in sudo if l.endswith(" " + target)])

    def test_test_mode_announces_destination(self):
        r, _, _, _, tmp = self.run_deploy("missing")
        self.assertIn("TEST MODE: unit destination is %s/dst.service" % tmp, r.stdout)

    def test_script_structure(self):
        text = DEPLOY.read_text()
        self.assertEqual(text.splitlines()[-1], 'main "$@"; exit $?')
        self.assertNotIn("seed_call_counter", text)
        guard = text.index('"$EUID" -eq 0')
        self.assertLess(guard, text.index("main() {"))


if __name__ == "__main__":
    unittest.main()
