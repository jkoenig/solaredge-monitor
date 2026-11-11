"""Tests for scripts/seed_call_counter.py."""
import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import seed_call_counter as sc  # noqa: E402
from call_counter import CallCounter  # noqa: E402

JOURNAL = [
    "x API /sites/123/overview -> 200",
    "x API /sites/123/storage/telemetry -> 500",
    "x Access token refreshed, expires in 120 min",
    "x Token refresh failed temporarily: timeout",
    "x API timeout: /sites/123/overview (attempt 1), retrying",
    "x Forecast fetched",
    "x Starting poll cycle",
]


def run(argv, stdin=""):
    out = io.StringIO()
    with mock.patch("sys.stdin", io.StringIO(stdin)), contextlib.redirect_stdout(out), \
            contextlib.redirect_stderr(io.StringIO()):
        code = sc.main(argv)
    return code, out.getvalue()


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = os.path.join(self.tmp.name, ".calls.json")

    def total(self):
        return CallCounter(self.file).cycle_total()

    def test_count_journal_calls(self):
        self.assertEqual(sc.count_journal_calls(JOURNAL), 5)

    def test_count_with_margin(self):
        code, out = run(["--count", "300", "--margin", "20", "--file", self.file])
        self.assertEqual(code, 0)
        self.assertEqual(self.total(), 320)
        self.assertIn("320/1800", out)
        self.assertIn("next reset", out)

    def test_from_journal(self):
        code, _ = run(["--from-journal", "--margin", "10", "--file", self.file], "\n".join(JOURNAL))
        self.assertEqual(code, 0)
        self.assertEqual(self.total(), 15)

    def test_never_lowers_without_force(self):
        run(["--count", "500", "--margin", "0", "--file", self.file])
        code, out = run(["--count", "100", "--margin", "0", "--file", self.file])
        self.assertEqual(code, 0)
        self.assertEqual(self.total(), 500)
        self.assertIn("kept", out)
        run(["--count", "100", "--margin", "0", "--force", "--file", self.file])
        self.assertEqual(self.total(), 100)

    def test_argparse_errors(self):
        for argv in (["--file", self.file],
                     ["--count", "1", "--from-journal", "--file", self.file]):
            with self.assertRaises(SystemExit) as cm:
                run(argv)
            self.assertEqual(cm.exception.code, 2)

    def test_negative_values(self):
        self.assertEqual(run(["--count", "-1", "--file", self.file])[0], 2)
        self.assertEqual(run(["--count", "1", "--margin", "-1", "--file", self.file])[0], 2)
        self.assertFalse(os.path.exists(self.file))

    def test_invalid_billing_day_rejected(self):
        for day in ("0", "32", "-1"):
            code, _ = run(["--count", "1", "--billing-day", day, "--file", self.file])
            self.assertEqual(code, 2)
        with mock.patch.dict(os.environ, {"SOLAREDGE_BILLING_DAY": "40"}):
            self.assertEqual(run(["--count", "1", "--file", self.file])[0], 2)
        self.assertFalse(os.path.exists(self.file))

    def test_persist_failure_exits_nonzero(self):
        with mock.patch("call_counter.os.replace", side_effect=OSError("ro")):
            code, out = run(["--count", "5", "--file", self.file])
        self.assertEqual(code, 1)
        self.assertNotIn("Call counter:", out)

    def test_force_lowering_clears_stopped_flag(self):
        c = CallCounter(self.file)
        c.mark_exhausted()
        self.assertEqual(CallCounter(self.file).state().__str__(), "stopped")
        code, _ = run(["--count", "100", "--margin", "0", "--force", "--file", self.file])
        self.assertEqual(code, 0)
        self.assertEqual(CallCounter(self.file).state(), "ok")

    def test_file_mode_and_no_ids(self):
        run(["--from-journal", "--file", self.file], "\n".join(JOURNAL))
        self.assertEqual(stat.S_IMODE(os.stat(self.file).st_mode), 0o600)
        text = Path(self.file).read_text()
        self.assertNotIn("site", text)
        self.assertIsInstance(json.loads(text), dict)


if __name__ == "__main__":
    unittest.main()
