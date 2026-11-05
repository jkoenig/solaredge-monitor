"""Tests for fetcher.py: fetch_round orchestration, today-bar patch, build_cycle."""

import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fetch_schedule as fs  # noqa: E402
from fetch_schedule import FetchPlan  # noqa: E402
from fetcher import (  # noqa: E402
    DataCache,
    RoundResult,
    build_cycle,
    fetch_round,
    patch_history_today,
)
from models import BatteryData, EnergyDetails, EnergyHistory, ForecastData  # noqa: E402

TZ = ZoneInfo("Europe/Zurich")


def at(h, m=0, day=5):
    return datetime(2026, 11, day, h, m, tzinfo=TZ)


def energy(prod=10.0, cons=8.0):
    return EnergyDetails(production=prod, self_consumption=4.0, feed_in=1.0,
                         consumption=cons, purchased=2.0)


def battery(temp=21.0):
    return BatteryData(state_of_charge=50, status="Idle", internal_temp=temp,
                       available_energy=3.0, power=0.0)


def history(end, n=14, prod=1.0, cons=2.0):
    dates = [(end - timedelta(days=n - 1 - i)).isoformat() for i in range(n)]
    return EnergyHistory(dates=dates, production=[prod + i for i in range(n)],
                         consumption=[cons + i for i in range(n)])


def make_api(**overrides):
    api = mock.MagicMock()
    api.get_overview.return_value = energy()
    api.get_battery_telemetry.return_value = battery()
    api.get_storage_temperature.return_value = 18.5
    api.detect_battery.return_value = True
    api.get_energy_history.return_value = history(date(2026, 11, 5))
    for k, v in overrides.items():
        getattr(api, k).return_value = v
    return api


def method_calls(api):
    return [c for c in api.mock_calls if "." not in c[0] and c[0]]


class FetchRoundTests(unittest.TestCase):
    def test_devices_detected_same_round_treated_as_battery(self):
        api = make_api()
        cache = DataCache()
        res = fetch_round(api, FetchPlan(), cache, at(7), False, False)
        api.detect_battery.assert_called_once()
        self.assertIs(res.battery_detected, True)
        api.get_storage_temperature.assert_called_once()
        api.get_battery_telemetry.assert_called_once()
        self.assertIsNotNone(cache.battery)

    def test_detect_none_skips_battery_calls(self):
        api = make_api(detect_battery=None)
        plan = FetchPlan()
        res = fetch_round(api, plan, DataCache(), at(7), False, False)
        self.assertIsNone(res.battery_detected)
        api.get_storage_temperature.assert_not_called()
        api.get_battery_telemetry.assert_not_called()
        # DEVICES attempt recorded: not due again 30 min later
        self.assertNotIn(fs.DEVICES, plan.due(at(7, 30), False, False))

    def test_order_and_fresh_temperature_passed(self):
        api = make_api()
        order = []
        manager = mock.MagicMock()
        manager.attach_mock(api.detect_battery, "devices")
        manager.attach_mock(api.get_overview, "overview")
        manager.attach_mock(api.get_storage_temperature, "temperature")
        manager.attach_mock(api.get_battery_telemetry, "storage")
        manager.attach_mock(api.get_energy_history, "history")
        forecast = mock.MagicMock()
        manager.attach_mock(forecast.get_forecast, "forecast")
        forecast.get_forecast.return_value = None
        fetch_round(api, FetchPlan(), DataCache(), at(7), False, False, forecast)
        order = [c[0] for c in manager.mock_calls]
        self.assertEqual(order, ["devices", "overview", "temperature", "storage",
                                 "history", "forecast"])
        api.get_battery_telemetry.assert_called_once_with(internal_temp=18.5)

    def test_zero_temperature_fallback(self):
        api = make_api(get_storage_temperature=None)
        fetch_round(api, FetchPlan(), DataCache(), at(7), True, True)
        api.get_battery_telemetry.assert_called_once_with(internal_temp=0.0)

    def test_temperature_replaces_cached_battery_when_storage_not_due(self):
        api = make_api()
        plan = mock.MagicMock()
        plan.due.return_value = {fs.TEMPERATURE}
        plan.in_backoff = False
        cache = DataCache(battery=battery(temp=10.0))
        fetch_round(api, plan, cache, at(12), True, True)
        self.assertEqual(cache.battery.internal_temp, 18.5)
        self.assertEqual(cache.battery.state_of_charge, 50)
        api.get_battery_telemetry.assert_not_called()

    def test_failure_keeps_previous_value_and_records_false(self):
        api = make_api(get_overview=None, get_battery_telemetry=None,
                       get_energy_history=None, get_storage_temperature=None)
        old_energy, old_batt, old_hist = energy(1, 1), battery(), history(date(2026, 11, 5))
        cache = DataCache(energy=old_energy, battery=old_batt, history=old_hist,
                          temperature=9.0)
        plan = mock.MagicMock()
        plan.due.return_value = {fs.OVERVIEW, fs.STORAGE, fs.HISTORY, fs.TEMPERATURE}
        plan.in_backoff = False
        res = fetch_round(api, plan, cache, at(7), True, True)
        self.assertFalse(res.overview_ok)
        self.assertIs(cache.energy, old_energy)
        self.assertIs(cache.battery, old_batt)
        self.assertEqual(cache.temperature, 9.0)
        for job in (fs.OVERVIEW, fs.STORAGE, fs.HISTORY, fs.TEMPERATURE):
            plan.record.assert_any_call(job, at(7), False)

    def test_success_records_true_and_updates_cache(self):
        api = make_api()
        plan = mock.MagicMock()
        plan.due.return_value = {fs.OVERVIEW, fs.HISTORY}
        plan.in_backoff = False
        cache = DataCache()
        res = fetch_round(api, plan, cache, at(7), False, True)
        self.assertTrue(res.overview_ok)
        plan.record.assert_any_call(fs.OVERVIEW, at(7), True)
        plan.record.assert_any_call(fs.HISTORY, at(7), True)
        self.assertIsNotNone(cache.energy)
        self.assertIsNotNone(cache.history)

    def test_only_due_jobs_called(self):
        api = make_api()
        plan = mock.MagicMock()
        plan.due.return_value = {fs.OVERVIEW}
        plan.in_backoff = False
        fetch_round(api, plan, DataCache(), at(7), True, True)
        self.assertEqual([c[0] for c in method_calls(api)], ["get_overview"])

    def test_overview_retry_flag_follows_backoff(self):
        api = make_api()
        plan = mock.MagicMock()
        plan.due.return_value = {fs.OVERVIEW}
        plan.in_backoff = False
        fetch_round(api, plan, DataCache(), at(7), False, True)
        api.get_overview.assert_called_with(retry=True)
        plan.in_backoff = True
        fetch_round(api, plan, DataCache(), at(8), False, True)
        api.get_overview.assert_called_with(retry=False)

    def test_backoff_gate_makes_no_call_then_full_round_after_hour(self):
        api = make_api(get_overview=None)
        plan = FetchPlan()
        t = at(7)
        for _ in range(3):
            fetch_round(api, plan, DataCache(), t, False, True)
            t += timedelta(minutes=30)
        self.assertTrue(plan.in_backoff)
        last_attempt = t - timedelta(minutes=30)
        api.reset_mock()
        res = fetch_round(api, plan, DataCache(), last_attempt + timedelta(minutes=30),
                          False, True)
        self.assertEqual(method_calls(api), [])
        self.assertFalse(res.overview_ok)
        res = fetch_round(api, plan, DataCache(), last_attempt + timedelta(minutes=60),
                          False, True)
        api.get_overview.assert_called_once_with(retry=False)

    def test_all_failure_day_budget(self):
        api = mock.MagicMock()
        for name in ("get_overview", "get_battery_telemetry", "get_storage_temperature",
                     "detect_battery", "get_energy_history"):
            getattr(api, name).return_value = None
        plan = FetchPlan()
        cache = DataCache()
        t = at(7)
        while t < at(20):
            fetch_round(api, plan, cache, t, True, True)
            t += timedelta(minutes=30)
        self.assertEqual(len(method_calls(api)), 36)
        retries = [c for c in api.get_overview.mock_calls if c.kwargs == {"retry": True}]
        self.assertEqual(len(retries), 3)

    def test_login_required_propagates(self):
        class LoginRequired(Exception):
            pass
        api = make_api()
        api.get_overview.side_effect = LoginRequired("x")
        with self.assertRaises(LoginRequired):
            fetch_round(api, FetchPlan(), DataCache(), at(7), False, True)

    def test_today_bar_patched_even_with_stale_history(self):
        api = make_api(get_overview=energy(7.5, 9.0))
        cache = DataCache(history=history(date(2026, 11, 4)))
        plan = mock.MagicMock()
        plan.due.return_value = {fs.OVERVIEW}
        plan.in_backoff = False
        fetch_round(api, plan, cache, at(9), False, True)
        self.assertEqual(cache.history.dates[-1], "2026-11-05")
        self.assertEqual(cache.history.production[-1], 7.5)
        self.assertEqual(cache.history.consumption[-1], 9.0)

    def test_forecast_new_and_actual_update(self):
        api = make_api(get_overview=energy(6.0, 5.0))
        fa = mock.MagicMock()
        fa.get_forecast.return_value = mock.MagicMock(
            today_kwh=12.0, tomorrow_kwh=14.0, fetched_at=at(7))
        cache = DataCache()
        fetch_round(api, FetchPlan(), cache, at(7), False, True, fa)
        self.assertEqual(cache.forecast.today_kwh, 12.0)
        self.assertEqual(cache.forecast.actual_production, 6.0)
        fa.get_forecast.return_value = None
        api.get_overview.return_value = energy(8.0, 5.0)
        fetch_round(api, FetchPlan(), cache, at(8), False, True, fa)
        self.assertEqual(cache.forecast.today_kwh, 12.0)
        self.assertEqual(cache.forecast.actual_production, 8.0)

    def test_roundresult_frozen(self):
        with self.assertRaises(Exception):
            RoundResult(True).overview_ok = False


class PatchHistoryTests(unittest.TestCase):
    def test_ending_today(self):
        h = history(date(2026, 11, 5))
        p = patch_history_today(h, date(2026, 11, 5), 7.5, 9.0)
        self.assertEqual(p.dates, h.dates)
        self.assertEqual(p.production[-1], 7.5)
        self.assertEqual(p.consumption[-1], 9.0)
        self.assertEqual(p.production[:-1], h.production[:-1])
        self.assertEqual(p.consumption[:-1], h.consumption[:-1])

    def test_ending_yesterday_shifts(self):
        h = history(date(2026, 11, 4))
        p = patch_history_today(h, date(2026, 11, 5), 3.0, 4.0)
        self.assertEqual(len(p.dates), 14)
        self.assertEqual(p.dates[-1], "2026-11-05")
        self.assertEqual(p.dates[0], "2026-10-23")
        self.assertEqual(p.production[-2], h.production[-1])
        self.assertEqual(p.production[0], h.production[1])
        self.assertEqual(p.production[-1], 3.0)
        self.assertEqual(p.consumption[-1], 4.0)

    def test_gap_fills_zero(self):
        h = history(date(2026, 11, 2))
        p = patch_history_today(h, date(2026, 11, 5), 1.0, 1.0)
        self.assertEqual(p.production[-2], 0.0)
        self.assertEqual(p.production[-3], 0.0)
        self.assertEqual(p.production[-4], h.production[-1])
        self.assertEqual(p.consumption[-3], 0.0)

    def test_empty_unchanged(self):
        h = EnergyHistory(dates=[], production=[], consumption=[])
        self.assertIs(patch_history_today(h, date(2026, 11, 5), 1.0, 1.0), h)


class BuildCycleTests(unittest.TestCase):
    SCREENS = [
        ("r1", "energy", "Produktion"),
        ("r2", "energy", "Verbrauch"),
        ("r3", "energy", "Einspeisung"),
        ("r4", "energy", "Bezug"),
        ("r5", "battery", "Hausakku"),
        ("r6", "history", "Verlauf"),
        ("r7", "forecast", "Prognose"),
    ]

    def full_cache(self):
        return DataCache(energy=energy(), battery=battery(), history=history(date(2026, 11, 5)),
                         forecast=ForecastData(1.0, 2.0))

    def test_all_present_in_order(self):
        cycle = build_cycle(self.SCREENS, self.full_cache())
        self.assertEqual([c[2] for c in cycle], [s[2] for s in self.SCREENS])
        self.assertEqual(cycle[0][0], "r1")
        self.assertIsInstance(cycle[4][1], BatteryData)

    def test_battery_missing_skipped_then_back(self):
        cache = self.full_cache()
        cache.battery = None
        self.assertNotIn("Hausakku", [c[2] for c in build_cycle(self.SCREENS, cache)])
        cache.battery = battery()
        self.assertIn("Hausakku", [c[2] for c in build_cycle(self.SCREENS, cache)])

    def test_energy_missing_skips_four(self):
        cache = self.full_cache()
        cache.energy = None
        names = [c[2] for c in build_cycle(self.SCREENS, cache)]
        self.assertEqual(names, ["Hausakku", "Verlauf", "Prognose"])


if __name__ == "__main__":
    unittest.main()
