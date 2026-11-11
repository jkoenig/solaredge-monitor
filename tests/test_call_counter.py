"""Tests for call_counter.py: cycle math, persistence, states, summaries, pruning."""

import json
import os
import stat
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import call_counter  # noqa: E402
from call_counter import (  # noqa: E402
    BRAKE,
    OK,
    SITE_TZ,
    STOPPED,
    CallCounter,
    QuotaBlocked,
    cycle_start_for,
    endpoint_for_url,
    next_reset_for,
    reset_date,
)


def zt(y, mo, d, h=12, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=SITE_TZ)


class CycleMathTests(unittest.TestCase):
    def test_reset_date_clamps(self):
        self.assertEqual(reset_date(2027, 2, 31), date(2027, 2, 28))
        self.assertEqual(reset_date(2028, 2, 31), date(2028, 2, 29))
        self.assertEqual(reset_date(2026, 4, 31), date(2026, 4, 30))
        self.assertEqual(reset_date(2026, 11, 5), date(2026, 11, 5))

    def test_cycle_start_and_next_reset(self):
        self.assertEqual(cycle_start_for(date(2026, 11, 4), 5), date(2026, 10, 5))
        self.assertEqual(cycle_start_for(date(2026, 11, 5), 5), date(2026, 11, 5))
        self.assertEqual(cycle_start_for(date(2026, 1, 2), 5), date(2025, 12, 5))
        self.assertEqual(next_reset_for(date(2026, 11, 11), 5), date(2026, 12, 5))
        self.assertEqual(next_reset_for(date(2026, 12, 20), 5), date(2027, 1, 5))

    def test_billing_day_31_short_months(self):
        self.assertEqual(cycle_start_for(date(2026, 11, 30), 31), date(2026, 11, 30))
        self.assertEqual(cycle_start_for(date(2026, 11, 29), 31), date(2026, 10, 31))
        self.assertEqual(next_reset_for(date(2026, 11, 1), 31), date(2026, 11, 30))
        self.assertEqual(next_reset_for(date(2027, 2, 10), 31), date(2027, 2, 28))


class EndpointTests(unittest.TestCase):
    def test_mapping(self):
        base = "https://monitoringapi.solaredge.com/v2"
        cases = {
            f"{base}/sites/X/overview?x=1": "overview",
            f"{base}/sites/X/storage/telemetry": "storage",
            f"{base}/sites/X/storage/status": "temperature",
            f"{base}/sites/X/energy?a=b": "history",
            f"{base}/sites/X/meters/telemetry": "history",
            f"{base}/sites/X/devices": "devices",
            "https://host/oauth2/token": "token",
            f"{base}/something/else": "other",
        }
        for url, expected in cases.items():
            self.assertEqual(endpoint_for_url(url), expected, url)


class CounterTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / ".calls.json"

    def make(self, **kw):
        return CallCounter(self.path, **kw)


class PersistenceTests(CounterTestBase):
    def test_persisted_before_return_and_mode(self):
        t = zt(2026, 11, 11)
        self.make().acquire("overview", t)
        again = self.make()
        self.assertEqual(again.cycle_total(t), 1)
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        data = json.loads(self.path.read_text())
        self.assertEqual(data["days"]["2026-11-11"]["endpoints"], {"overview": 1})
        self.assertNotIn("http", self.path.read_text())

    def test_persist_failure_fails_closed(self):
        t = zt(2026, 11, 11)
        c = self.make()
        with mock.patch("call_counter.os.replace", side_effect=OSError("boom")):
            with self.assertRaises(QuotaBlocked) as cm:
                c.acquire("overview", t)
        self.assertEqual(cm.exception.reason, "counter not persisted")
        self.assertEqual(c.cycle_total(t), 1)

    def test_corrupt_file_starts_at_zero_with_warning(self):
        self.path.write_text("{not json")
        with self.assertLogs(level="WARNING") as cm:
            c = self.make()
        self.assertTrue(any("invalid" in m for m in cm.output))
        self.assertEqual(c.cycle_total(zt(2026, 11, 11)), 0)

    def test_wrong_version_starts_at_zero_with_warning(self):
        self.path.write_text(json.dumps({"version": 99}))
        with self.assertLogs(level="WARNING"):
            c = self.make()
        self.assertEqual(c.cycle_total(zt(2026, 11, 11)), 0)

    def test_missing_file_no_warning(self):
        with self.assertNoLogs(level="WARNING"):
            c = self.make()
            self.assertEqual(c.cycle_total(zt(2026, 11, 11)), 0)

    def test_fetch_state_roundtrip_keeps_counts(self):
        t = zt(2026, 11, 11)
        c = self.make()
        c.acquire("overview", t)
        self.assertTrue(c.save_fetch_state({"a": 1}))
        again = self.make()
        self.assertEqual(again.fetch_state(), {"a": 1})
        self.assertEqual(again.cycle_total(t), 1)
        self.assertEqual(self.make().fetch_state(), {"a": 1})

    def test_fetch_state_empty_by_default(self):
        self.assertEqual(self.make().fetch_state(), {})


class StateTests(CounterTestBase):
    def test_thresholds(self):
        t = zt(2026, 11, 11)
        c = self.make()
        c.seed(1499, t)
        self.assertEqual(c.state(t), OK)
        c.seed(1500, t)
        self.assertEqual(c.state(t), BRAKE)
        c.seed(1800, t)
        self.assertEqual(c.state(t), STOPPED)

    def test_acquire_blocked_when_stopped(self):
        t = zt(2026, 11, 11)
        c = self.make()
        c.seed(1800, t)
        with self.assertRaises(QuotaBlocked) as cm:
            c.acquire("overview", t)
        self.assertEqual(cm.exception.reason, "stopped")
        self.assertEqual(c.cycle_total(t), 1800)

    def test_reset_at_site_midnight(self):
        c = self.make()
        c.acquire("overview", zt(2026, 12, 4, 23, 59))
        self.assertEqual(c.cycle_total(zt(2026, 12, 4, 23, 59)), 1)
        t = zt(2026, 12, 5, 0, 0)
        self.assertEqual(c.state(t), OK)
        self.assertEqual(c.cycle_total(t), 0)

    def test_reset_clears_stopped(self):
        c = self.make()
        c.seed(1800, zt(2026, 12, 4))
        self.assertEqual(c.state(zt(2026, 12, 5, 0, 0)), OK)

    def test_brake_and_stop_logged_once(self):
        t = zt(2026, 11, 11)
        c = self.make(soft_limit=3, hard_limit=5)
        with self.assertLogs(level="WARNING") as cm:
            for _ in range(5):
                c.acquire("overview", t)
            for _ in range(2):
                with self.assertRaises(QuotaBlocked):
                    c.acquire("overview", t)
        self.assertEqual(sum("soft brake" in m for m in cm.output), 1)
        self.assertEqual(sum("hard stop" in m for m in cm.output), 1)

    def test_mark_exhausted(self):
        t = zt(2026, 11, 11)
        c = self.make()
        c.seed(10, t)
        c.mark_exhausted(t)
        self.assertEqual(c.state(t), STOPPED)
        self.assertEqual(self.make().state(t), STOPPED)
        self.assertEqual(self.make().state(zt(2026, 12, 5, 0, 0)), OK)
        with self.assertRaises(QuotaBlocked):
            c.acquire("overview", t)

    def test_next_reset(self):
        self.assertEqual(self.make().next_reset(zt(2026, 11, 11)), date(2026, 12, 5))

    def test_billing_day_change_never_moves_cycle_back(self):
        t = zt(2026, 11, 11)
        c = self.make(billing_day=5)
        c.acquire("overview", t)
        other = self.make(billing_day=20)  # would compute cycle start 2026-10-20
        self.assertEqual(other.cycle_total(t), 1)

    def test_seed(self):
        t = zt(2026, 11, 11)
        c = self.make()
        c.seed(10, t)
        self.assertEqual(c.seed(500, t), 500)
        self.assertEqual(c.seed(5, t), 500)
        self.assertEqual(c.seed(5, t, force=True), 5)


class SummaryTests(CounterTestBase):
    def test_day_summary_once(self):
        c = self.make()
        d = zt(2026, 11, 6)
        c.acquire("token", d)
        c.acquire("overview", d)
        c.acquire("overview", d)
        t = zt(2026, 11, 7, 0, 5)
        self.assertEqual(
            c.pop_day_summaries(t),
            ["Calls 2026-11-06: 3 (overview 2, token 1); cycle 3/1800"],
        )
        self.assertEqual(c.pop_day_summaries(t), [])
        self.assertEqual(self.make().pop_day_summaries(t), [])

    def test_summary_order_and_omits_zero(self):
        c = self.make()
        d = zt(2026, 11, 6)
        for ep in ("temperature", "history", "storage", "overview"):
            c.acquire(ep, d)
        line = c.pop_day_summaries(zt(2026, 11, 7))[0]
        self.assertEqual(
            line,
            "Calls 2026-11-06: 4 (overview 1, storage 1, history 1, temperature 1); cycle 4/1800",
        )
        self.assertNotIn("token", line)

    def test_no_summary_for_unknown_day(self):
        self.assertEqual(self.make().pop_day_summaries(zt(2026, 11, 7)), [])

    def test_zero_call_day(self):
        c = self.make()
        c.cycle_total(zt(2026, 11, 6))
        c._persist()
        self.assertEqual(
            c.pop_day_summaries(zt(2026, 11, 7)),
            ["Calls 2026-11-06: 0; cycle 0/1800"],
        )


class PruneTests(CounterTestBase):
    def test_old_days_dropped_previous_cycle_kept(self):
        c = self.make()
        c.acquire("overview", zt(2026, 9, 20))  # two cycles back (cycle from 09-05)
        c.acquire("overview", zt(2026, 10, 10))  # cycle from 10-05
        c.acquire("overview", zt(2026, 11, 10))  # cycle from 11-05 (prev cycle = 10-05)
        days = json.loads(self.path.read_text())["days"]
        self.assertNotIn("2026-09-20", days)
        self.assertIn("2026-10-10", days)
        self.assertIn("2026-11-10", days)


if __name__ == "__main__":
    unittest.main()
