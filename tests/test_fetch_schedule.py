import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_schedule import (  # noqa: E402
    DEVICES,
    HISTORY,
    OVERVIEW,
    STORAGE,
    TEMPERATURE,
    FetchPlan,
)

TZ = ZoneInfo("Europe/Zurich")


def at(h, m=0, day=(2026, 11, 5)):
    return datetime(day[0], day[1], day[2], h, m, tzinfo=TZ)


def simulate(success, has_battery=True, battery_known=True):
    plan = FetchPlan()
    counts = {OVERVIEW: 0, STORAGE: 0, HISTORY: 0, TEMPERATURE: 0, DEVICES: 0}
    overview_outside_backoff = 0
    now = at(7)
    while now <= at(19, 30):
        was_backoff = plan.in_backoff
        due = plan.due(now, has_battery, battery_known)
        if OVERVIEW in due and not was_backoff:
            overview_outside_backoff += 1
        for job in due:
            counts[job] += 1
            plan.record(job, now, success)
        now += timedelta(minutes=30)
    return counts, overview_outside_backoff


def weighted(counts):
    return (
        counts[OVERVIEW]
        + counts[STORAGE]
        + counts[HISTORY] * FetchPlan.HISTORY_CALLS
        + counts[TEMPERATURE]
        + counts[DEVICES]
    )


class BudgetTests(unittest.TestCase):
    def test_success_day_is_43_calls(self):
        counts, _ = simulate(True)
        self.assertEqual(counts[OVERVIEW], 26)
        self.assertEqual(counts[STORAGE], 13)
        self.assertEqual(counts[HISTORY], 1)
        self.assertEqual(counts[TEMPERATURE], 2)
        self.assertEqual(weighted(counts), 43)

    def test_failure_day_is_39_calls(self):
        counts, outside = simulate(False)
        self.assertEqual(counts[OVERVIEW], 14)
        self.assertEqual(counts[STORAGE], 13)
        self.assertEqual(counts[HISTORY], 3)
        self.assertEqual(counts[TEMPERATURE], 6)
        self.assertEqual(weighted(counts), 39)
        self.assertEqual(outside, 3)

    def test_no_battery_no_storage_or_temperature(self):
        counts, _ = simulate(True, has_battery=False, battery_known=True)
        self.assertEqual(counts[STORAGE], 0)
        self.assertEqual(counts[TEMPERATURE], 0)


class BackoffTests(unittest.TestCase):
    def test_backoff_after_exactly_three_failures(self):
        plan = FetchPlan()
        plan.record(OVERVIEW, at(7), False)
        plan.record(OVERVIEW, at(7, 30), False)
        self.assertFalse(plan.in_backoff)
        plan.record(OVERVIEW, at(8), False)
        self.assertTrue(plan.in_backoff)

    def test_interleaved_success_prevents_backoff(self):
        plan = FetchPlan()
        plan.record(OVERVIEW, at(7), False)
        plan.record(OVERVIEW, at(7, 30), False)
        plan.record(OVERVIEW, at(8), True)
        plan.record(OVERVIEW, at(8, 30), False)
        self.assertFalse(plan.in_backoff)

    def test_hourly_gating_in_backoff(self):
        plan = FetchPlan()
        for t in (at(7), at(7, 30), at(8)):
            plan.record(OVERVIEW, t, False)
        self.assertEqual(plan.due(at(8, 30), True, True), set())
        self.assertEqual(plan.due(at(8, 59), True, True), set())
        self.assertIn(OVERVIEW, plan.due(at(9), True, True))

    def test_reset_on_success(self):
        plan = FetchPlan()
        for t in (at(7), at(7, 30), at(8)):
            plan.record(OVERVIEW, t, False)
        plan.record(OVERVIEW, at(9), True)
        self.assertFalse(plan.in_backoff)
        self.assertIn(OVERVIEW, plan.due(at(9, 30), True, True))


class JobTests(unittest.TestCase):
    def test_storage_attempt_based(self):
        plan = FetchPlan()
        self.assertIn(STORAGE, plan.due(at(7), True, True))
        plan.record(STORAGE, at(7), False)
        self.assertNotIn(STORAGE, plan.due(at(7, 30), True, True))
        self.assertIn(STORAGE, plan.due(at(8), True, True))

    def test_history_retry_gap_and_attempt_cap(self):
        plan = FetchPlan()
        plan.record(HISTORY, at(7), False)
        self.assertNotIn(HISTORY, plan.due(at(7, 30), True, True))
        self.assertIn(HISTORY, plan.due(at(8), True, True))
        plan.record(HISTORY, at(8), False)
        plan.record(HISTORY, at(9), False)
        self.assertNotIn(HISTORY, plan.due(at(15), True, True))

    def test_history_success_then_next_day(self):
        plan = FetchPlan()
        plan.record(HISTORY, at(7), True)
        self.assertNotIn(HISTORY, plan.due(at(12), True, True))
        self.assertIn(HISTORY, plan.due(at(7, day=(2026, 11, 6)), True, True))

    def test_temperature_slots(self):
        plan = FetchPlan()
        plan.record(TEMPERATURE, at(7), True)
        self.assertNotIn(TEMPERATURE, plan.due(at(11), True, True))
        self.assertIn(TEMPERATURE, plan.due(at(12), True, True))

    def test_late_start_only_pm_slot(self):
        plan = FetchPlan()
        self.assertIn(TEMPERATURE, plan.due(at(14), True, True))
        plan.record(TEMPERATURE, at(14), True)
        self.assertNotIn(TEMPERATURE, plan.due(at(15), True, True))

    def test_devices_only_when_unknown(self):
        plan = FetchPlan()
        self.assertNotIn(DEVICES, plan.due(at(7), True, True))
        self.assertIn(DEVICES, plan.due(at(7), False, False))
        plan.record(DEVICES, at(7), False)
        self.assertNotIn(DEVICES, plan.due(at(12), False, False))
        self.assertIn(DEVICES, plan.due(at(13), False, False))

    def test_dst_end_uses_local_date(self):
        plan = FetchPlan()
        day = (2026, 10, 25)
        plan.record(HISTORY, at(7, day=day), True)
        self.assertNotIn(HISTORY, plan.due(at(19, day=day), True, True))
        self.assertIn(HISTORY, plan.due(at(7, day=(2026, 10, 26)), True, True))

    def test_unknown_job_raises(self):
        with self.assertRaises(ValueError):
            FetchPlan().record("bogus", at(7), True)


if __name__ == "__main__":
    unittest.main()
