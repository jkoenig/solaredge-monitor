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
    def run_deploy(self, dst_mode):
        """dst_mode: 'missing', 'different' or 'identical'."""
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
            env["SOLAREDGE_UNIT_DST"] = str(dst)
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

    def test_script_structure(self):
        text = DEPLOY.read_text()
        self.assertEqual(text.splitlines()[-1], 'main "$@"; exit $?')
        self.assertNotIn("seed_call_counter", text)
        guard = text.index('"$EUID" -eq 0')
        self.assertLess(guard, text.index("main() {"))


if __name__ == "__main__":
    unittest.main()
