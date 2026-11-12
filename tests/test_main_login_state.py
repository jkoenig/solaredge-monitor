"""Subprocess smoke tests: main.py in debug mode without a usable token.

Each run gets its own temporary working directory. In debug mode main.py
writes its PNGs to "debug/" below the working directory, and the call counter
and its lock file live next to the token file, so nothing is shared between
tests or between two test runs that happen at the same time. The test waits
for the login screen to be rendered instead of sleeping a fixed time.
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

RENDERED_MARKER = "Rendered 'login'"
STARTUP_TIMEOUT_SECONDS = 90
# After the login screen is up: time for a wrong follow-up action (a poll, a
# second screen) to show itself. Only absence is asserted after this pause,
# so a slow machine cannot turn it into a failure.
SETTLE_SECONDS = 2
SHUTDOWN_TIMEOUT_SECONDS = 30


def run_main(workdir, token_path):
    """Start main.py in `workdir`, wait for the login screen, stop it.

    Returns (output, returncode, set of PNG names written by this run).
    """
    workdir = Path(workdir)
    # Fonts are looked up relative to the working directory.
    os.symlink(REPO / "fonts", workdir / "fonts")
    debug_dir = workdir / "debug"
    log_path = workdir / "main.out"
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

    def output():
        return log_path.read_text(encoding="utf-8", errors="replace")

    with open(log_path, "wb") as log:
        proc = subprocess.Popen(
            [sys.executable, str(REPO / "main.py")],
            cwd=workdir,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
            rendered = False
            while time.monotonic() < deadline:
                if RENDERED_MARKER in output():
                    rendered = True
                    break
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
            if not rendered:
                state = "exited with %s" % proc.returncode \
                    if proc.poll() is not None else "still running"
                raise AssertionError(
                    "login screen not rendered within %d s (process %s):\n%s"
                    % (STARTUP_TIMEOUT_SECONDS, state, output())
                )
            time.sleep(SETTLE_SECONDS)
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    pngs = {p.name for p in debug_dir.glob("*.png")} if debug_dir.exists() else set()
    return output(), proc.returncode, pngs


class LoginStateSmokeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workdir = Path(tmp.name) / "work"
        self.workdir.mkdir()
        self.state_dir = Path(tmp.name) / "state"
        self.state_dir.mkdir()

    def _run(self, token_path):
        return run_main(self.workdir, token_path)

    def _assert_login_only(self, out, rc, new):
        self.assertEqual(rc, 0, out)
        self.assertNotIn("Starting poll cycle", out)
        self.assertNotIn("Traceback", out)
        self.assertEqual(len(new), 1, new)
        self.assertTrue(next(iter(new)).startswith("login_"), new)

    def test_missing_token_shows_login_only(self):
        out, rc, new = self._run(self.state_dir / "missing.json")
        self.assertIn("Login required: token file missing", out)
        self._assert_login_only(out, rc, new)

    def test_corrupt_token_shows_login_only(self):
        p = self.state_dir / "tokens.json"
        p.write_text("{broken")
        out, rc, new = self._run(p)
        self.assertIn("Login required: token file corrupt", out)
        self._assert_login_only(out, rc, new)

    def test_no_network_calls_in_login_state(self):
        out, rc, new = self._run(self.state_dir / "missing.json")
        for marker in ("API HTTP error", "API timeout", "API request failed", "Token refresh"):
            self.assertNotIn(marker, out)


if __name__ == "__main__":
    unittest.main()
