import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_schedule import (  # noqa: E402
    DEVICES,
    HISTORY,
    MODE_BRAKE,
    MODE_OK,
    MODE_STOPPED,
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


def simulate_24h(mode, step_minutes=30, start_minute=0):
    plan = FetchPlan()
    counts = {OVERVIEW: 0, STORAGE: 0, HISTORY: 0, TEMPERATURE: 0, DEVICES: 0}
    now = at(7, start_minute)
    end = now + timedelta(hours=24)
    while now < end:
        for job in plan.due(now, True, True, mode):
            counts[job] += 1
            plan.record(job, now, True)
        now += timedelta(minutes=step_minutes)
    return counts


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


D5 = (2026, 11, 5)
D6 = (2026, 11, 6)


class NightTests(unittest.TestCase):
    def test_is_night(self):
        plan = FetchPlan()
        self.assertFalse(plan.is_night(at(19, 59)))
        self.assertTrue(plan.is_night(at(20, 0)))
        self.assertTrue(plan.is_night(at(23, 30)))
        self.assertTrue(plan.is_night(at(6, 59)))
        self.assertFalse(plan.is_night(at(7, 0)))
        self.assertFalse(FetchPlan(night_start_hour=0, night_end_hour=0).is_night(at(3)))

    def test_slot_fires_once(self):
        plan = FetchPlan()
        self.assertEqual(plan.due(at(21), True, True), set())
        self.assertEqual(plan.due(at(23), True, True), {STORAGE})
        plan.record(STORAGE, at(23), True)
        self.assertEqual(plan.due(at(23, 30), True, True), set())

    def test_slot_across_midnight(self):
        plan = FetchPlan()
        plan.record(STORAGE, at(23, day=D5), True)
        self.assertEqual(plan.due(at(0, 30, day=D6), True, True), set())
        self.assertEqual(plan.due(at(2, day=D6), True, True), {STORAGE})

    def test_late_poll(self):
        plan = FetchPlan()
        self.assertEqual(plan.due(at(1, 45, day=D6), True, True), {STORAGE})
        plan.record(STORAGE, at(1, 45, day=D6), True)
        self.assertEqual(plan.due(at(2, 15, day=D6), True, True), {STORAGE})

    def test_no_battery_and_only_storage(self):
        plan = FetchPlan()
        self.assertEqual(plan.due(at(23), False, True), set())
        self.assertEqual(plan.due(at(23), True, False), {STORAGE})

    def test_failed_attempt_not_retried(self):
        plan = FetchPlan()
        plan.record(STORAGE, at(23), False)
        self.assertEqual(plan.due(at(23, 30), True, True), set())
        self.assertEqual(plan.due(at(1, 0, day=D6), True, True), set())

    def test_hourly_polls_make_three_night_calls(self):
        night = 0
        plan = FetchPlan()
        now = at(20, 45)
        while now < at(7, 0, day=D6):
            for job in plan.due(now, True, True, MODE_OK):
                night += 1
                plan.record(job, now, True)
            now += timedelta(minutes=60)
        self.assertEqual(night, 3)


class QuotaModeTests(unittest.TestCase):
    def test_stopped(self):
        plan = FetchPlan()
        self.assertEqual(plan.due(at(9), True, True, MODE_STOPPED), set())
        self.assertEqual(plan.due(at(23), True, True, MODE_STOPPED), set())
        self.assertEqual(weighted(simulate_24h(MODE_STOPPED)), 0)

    def test_brake_overview_hourly_no_night(self):
        plan = FetchPlan()
        plan.record(OVERVIEW, at(9), True)
        self.assertNotIn(OVERVIEW, plan.due(at(9, 30), True, True, MODE_BRAKE))
        self.assertIn(OVERVIEW, plan.due(at(10), True, True, MODE_BRAKE))
        self.assertEqual(plan.due(at(23), True, True, MODE_BRAKE), set())

    def test_ok_24h_budget_is_46(self):
        c = simulate_24h(MODE_OK)
        self.assertEqual(c[OVERVIEW], 26)
        self.assertEqual(c[STORAGE], 16)
        self.assertEqual(c[HISTORY], 1)
        self.assertEqual(c[TEMPERATURE], 2)
        self.assertEqual(weighted(c), 46)

    def test_brake_24h_budget_is_30(self):
        c = simulate_24h(MODE_BRAKE)
        self.assertEqual(c[OVERVIEW], 13)
        self.assertEqual(c[STORAGE], 13)
        self.assertEqual(c[HISTORY], 1)
        self.assertEqual(c[TEMPERATURE], 2)
        self.assertEqual(weighted(c), 30)


class PersistenceTests(unittest.TestCase):
    def roundtrip(self, plan, now):
        data = json.loads(json.dumps(plan.to_dict()))
        plan2 = FetchPlan()
        plan2.load_dict(data, now)
        return plan2

    def test_history(self):
        plan = FetchPlan()
        plan.record(HISTORY, at(7), True)
        plan2 = self.roundtrip(plan, at(9))
        self.assertNotIn(HISTORY, plan2.due(at(9), True, True))

    def test_temperature(self):
        plan = FetchPlan()
        plan.record(TEMPERATURE, at(8), True)
        plan2 = self.roundtrip(plan, at(10))
        self.assertNotIn(TEMPERATURE, plan2.due(at(10), True, True))
        self.assertIn(TEMPERATURE, plan2.due(at(13), True, True))

    def test_night_slot(self):
        plan = FetchPlan()
        plan.record(STORAGE, at(23, day=D5), True)
        plan2 = self.roundtrip(plan, at(0, 30, day=D6))
        self.assertEqual(plan2.due(at(0, 30, day=D6), True, True), set())

    def test_garbage_never_raises(self):
        plan = FetchPlan()
        for bad in (
            {"version": 1, "slots": [1, {"job": "x"}, {"job": "history", "date": "bad"}]},
            None,
            {},
            {"version": 2, "slots": []},
            {"version": 1, "slots": "x"},
        ):
            plan.load_dict(bad, at(9))
        self.assertEqual(plan._slots, {})

    def test_old_slots_dropped(self):
        plan = FetchPlan()
        plan.record(HISTORY, at(7, day=(2026, 11, 1)), True)
        plan2 = self.roundtrip(plan, at(9))
        self.assertEqual(plan2._slots, {})

    def test_unknown_version(self):
        plan = FetchPlan()
        plan.record(HISTORY, at(7), True)
        data = plan.to_dict()
        data["version"] = 9
        plan2 = FetchPlan()
        plan2.load_dict(data, at(9))
        self.assertEqual(plan2._slots, {})


if __name__ == "__main__":
    unittest.main()
