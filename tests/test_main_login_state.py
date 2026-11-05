"""Subprocess smoke tests: main.py in debug mode without a usable token."""

import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEBUG_DIR = REPO / "debug"


def _pngs():
    return {p.name for p in DEBUG_DIR.glob("*.png")} if DEBUG_DIR.exists() else set()


def run_main(token_path, seconds=8):
    before = _pngs()
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "SOLAREDGE_TOKEN_FILE": str(token_path),
        "SOLAREDGE_DEBUG": "true",
        "SOLAREDGE_SLEEP_START": "0",
        "SOLAREDGE_SLEEP_END": "0",
        "SOLAREDGE_CLIENT_ID": "cid",
        "SOLAREDGE_CLIENT_SECRET": "sec",
    }
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=REPO,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(seconds)
    proc.send_signal(signal.SIGTERM)
    out, _ = proc.communicate(timeout=15)
    return out, proc.returncode, _pngs() - before


class LoginStateSmokeTest(unittest.TestCase):
    def setUp(self):
        self._created = set()

    def tearDown(self):
        for name in self._created:
            try:
                (DEBUG_DIR / name).unlink()
            except FileNotFoundError:
                pass

    def _run(self, token_path):
        out, rc, new = run_main(token_path)
        self._created |= new
        return out, rc, new

    def _assert_login_only(self, out, rc, new):
        self.assertEqual(rc, 0, out)
        self.assertNotIn("Starting poll cycle", out)
        self.assertNotIn("Traceback", out)
        self.assertEqual(len(new), 1, new)
        self.assertTrue(next(iter(new)).startswith("login_"), new)

    def test_missing_token_shows_login_only(self):
        with tempfile.TemporaryDirectory() as d:
            out, rc, new = self._run(Path(d) / "missing.json")
        self.assertIn("Login required: token file missing", out)
        self._assert_login_only(out, rc, new)

    def test_corrupt_token_shows_login_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tokens.json"
            p.write_text("{broken")
            out, rc, new = self._run(p)
        self.assertIn("Login required: token file corrupt", out)
        self._assert_login_only(out, rc, new)

    def test_no_network_calls_in_login_state(self):
        with tempfile.TemporaryDirectory() as d:
            out, rc, new = self._run(Path(d) / "missing.json")
        for marker in ("API HTTP error", "API timeout", "API request failed", "Token refresh"):
            self.assertNotIn(marker, out)


if __name__ == "__main__":
    unittest.main()
