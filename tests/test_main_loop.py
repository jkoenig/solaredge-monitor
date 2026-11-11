"""Tests for main.run_iteration: poll only when due, always rotate cached screens."""

import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import main
from fetcher import DataCache, RoundResult
from call_counter import QuotaBlocked
from screens.error import render_quota_exhausted_screen
from token_store import LoginRequired


def make_counter(mode="ok", summaries=()):
    c = mock.MagicMock()
    c.state.return_value = mode
    c.next_reset.return_value = date(2026, 12, 5)
    c.pop_day_summaries.return_value = list(summaries)
    return c


def make_state(due=("overview",), next_poll_offset=1000.0, energy=True, has_battery=False,
               counter=None):
    cfg = mock.MagicMock()
    cfg.battery_cache_file = "battery_cache.json"
    cache = DataCache()
    if energy:
        e = mock.MagicMock()
        e.production = e.consumption = e.feed_in = e.purchased = 1.0
        cache.energy = e
    plan = mock.MagicMock()
    plan.due.return_value = set(due)
    return main.LoopState(
        config=cfg,
        token_store=mock.MagicMock(),
        api=mock.MagicMock(),
        plan=plan,
        cache=cache,
        screens=[(lambda d: None, "energy", "Produktion")],
        has_battery=has_battery,
        battery_known=False,
        site_id="site",
        next_poll=time.monotonic() + next_poll_offset,
        poll_interval_seconds=1800,
        counter=counter,
    )


class RunIterationTest(unittest.TestCase):
    def setUp(self):
        patches = {
            "cycle": mock.patch.object(main, "run_screen_cycle"),
            "fetch": mock.patch.object(main, "fetch_round"),
            "save": mock.patch.object(main, "save_battery_cache"),
            "err": mock.patch.object(main, "render_error_screen", return_value="img"),
            "export": mock.patch.object(main, "export_fetch_state", return_value={"x": 1}),
        }
        self.m = {k: p.start() for k, p in patches.items()}
        for p in patches.values():
            self.addCleanup(p.stop)
        self.display = mock.MagicMock()

    def run_it(self, state):
        return main.run_iteration(state, self.display, time.monotonic())

    def test_rotation_without_poll_makes_no_calls(self):
        state = make_state()
        self.assertTrue(self.run_it(state))
        self.m["cycle"].assert_called_once()
        cycle = self.m["cycle"].call_args[0][1]
        self.assertEqual([n for _, _, n in cycle], ["Produktion"])
        self.m["fetch"].assert_not_called()
        state.token_store.get_access_token.assert_not_called()
        self.assertEqual(state.api.mock_calls, [])

    def test_no_cache_no_rotation(self):
        state = make_state(energy=False)
        self.assertFalse(self.run_it(state))
        self.m["cycle"].assert_not_called()

    def test_poll_due(self):
        state = make_state(next_poll_offset=-1.0)
        before = state.next_poll
        self.m["fetch"].return_value = RoundResult(overview_ok=True)
        self.assertTrue(self.run_it(state))
        state.token_store.get_access_token.assert_called_once()
        self.m["fetch"].assert_called_once()
        self.m["cycle"].assert_called_once()
        self.assertGreater(state.next_poll, before)

    def test_backoff_gate_skips_poll(self):
        state = make_state(due=(), next_poll_offset=-1.0)
        before = state.next_poll
        self.assertTrue(self.run_it(state))
        state.token_store.get_access_token.assert_not_called()
        self.m["fetch"].assert_not_called()
        self.m["cycle"].assert_called_once()
        self.assertGreater(state.next_poll, before)

    def test_error_screen_at_threshold_once(self):
        state = make_state(next_poll_offset=-1.0)
        self.m["fetch"].return_value = RoundResult(overview_ok=False)
        for _ in range(2):
            self.run_it(state)
            state.next_poll = time.monotonic() - 1
        self.display.render.assert_not_called()
        self.run_it(state)
        self.display.render.assert_called_once_with("img", "error")
        self.assertEqual(state.consecutive_failures, 3)
        # no rotation once the threshold is reached
        self.assertEqual(self.m["cycle"].call_count, 2)
        state.next_poll = time.monotonic() + 1000
        self.assertFalse(self.run_it(state))
        self.assertEqual(self.m["cycle"].call_count, 2)
        self.display.render.assert_called_once()

    def test_error_screen_redrawn_after_wake(self):
        state = make_state(next_poll_offset=-1.0)
        self.m["fetch"].return_value = RoundResult(overview_ok=False)
        for _ in range(3):
            self.run_it(state)
            state.next_poll = time.monotonic() - 1
        self.display.render.assert_called_once_with("img", "error")
        # manual flag reset (e.g. after login resume); next failed poll redraws
        state.error_screen_shown = False
        self.run_it(state)
        self.assertEqual(state.consecutive_failures, 4)
        self.assertEqual(self.display.render.call_count, 2)
        # but not on every further failure
        state.next_poll = time.monotonic() - 1
        self.run_it(state)
        self.assertEqual(self.display.render.call_count, 2)

    def test_expired_false_battery_is_redetected(self):
        state = make_state(next_poll_offset=-1.0)
        state.battery_known = True
        state.has_battery = False
        state.battery_checked_at = None  # legacy cache without timestamp
        self.m["fetch"].return_value = RoundResult(overview_ok=True)
        self.run_it(state)
        self.assertFalse(self.m["fetch"].call_args[0][5])  # battery_known passed False

    def test_fresh_false_battery_not_redetected(self):
        state = make_state(next_poll_offset=-1.0)
        state.battery_known = True
        state.has_battery = False
        state.battery_checked_at = time.time()
        self.m["fetch"].return_value = RoundResult(overview_ok=True)
        self.run_it(state)
        self.assertTrue(self.m["fetch"].call_args[0][5])

    def test_battery_detected_saves_and_rebuilds(self):
        state = make_state(next_poll_offset=-1.0)
        self.m["fetch"].return_value = RoundResult(overview_ok=True, battery_detected=True)
        with mock.patch.object(
            main, "get_screens", return_value=[(lambda d: None, "battery", "Hausakku")]
        ) as gs:
            self.run_it(state)
        self.m["save"].assert_called_once_with("battery_cache.json", "site", True)
        self.assertTrue(state.has_battery)
        self.assertTrue(state.battery_known)
        gs.assert_called_once()
        self.assertIn("Hausakku", [n for _, _, n in state.screens])

    def test_login_required_from_fetch_propagates(self):
        state = make_state(next_poll_offset=-1.0)
        self.m["fetch"].side_effect = LoginRequired("expired")
        with self.assertRaises(LoginRequired):
            self.run_it(state)

    def test_login_required_from_token_propagates(self):
        state = make_state(next_poll_offset=-1.0)
        state.token_store.get_access_token.side_effect = LoginRequired("expired")
        with self.assertRaises(LoginRequired):
            self.run_it(state)
        self.m["fetch"].assert_not_called()

    def test_stopped_appends_info_screen_no_calls(self):
        counter = make_counter("stopped")
        state = make_state(due=(), next_poll_offset=-1.0, counter=counter)
        self.assertTrue(self.run_it(state))
        self.assertEqual(state.plan.due.call_args[0][3], "stopped")
        state.token_store.get_access_token.assert_not_called()
        self.m["fetch"].assert_not_called()
        cycle = self.m["cycle"].call_args[0][1]
        self.assertEqual([n for _, _, n in cycle], ["Produktion", "Kontingent"])
        self.assertIs(cycle[-1][0], render_quota_exhausted_screen)
        self.assertEqual(cycle[-1][1], date(2026, 12, 5))

    def test_stopped_empty_cache_info_screen_alone(self):
        state = make_state(energy=False, due=(), counter=make_counter("stopped"))
        self.assertTrue(self.run_it(state))
        cycle = self.m["cycle"].call_args[0][1]
        self.assertEqual(cycle, [(render_quota_exhausted_screen, date(2026, 12, 5), "Kontingent")])
        self.display.render.assert_not_called()

    def test_stopped_resets_failures(self):
        state = make_state(counter=make_counter("stopped"))
        state.consecutive_failures = 3
        state.error_screen_shown = True
        self.assertTrue(self.run_it(state))
        self.assertEqual(state.consecutive_failures, 0)
        self.assertFalse(state.error_screen_shown)
        self.m["cycle"].assert_called_once()
        self.display.render.assert_not_called()

    def test_skipped_overview_rounds_never_fail(self):
        state = make_state(next_poll_offset=-1.0, counter=make_counter("ok"))
        self.m["fetch"].return_value = RoundResult(overview_ok=False, overview_attempted=False)
        for _ in range(3):
            self.run_it(state)
            state.next_poll = time.monotonic() - 1
        self.assertEqual(state.consecutive_failures, 0)
        self.display.render.assert_not_called()

    def test_brake_mode_passed_no_info_screen(self):
        state = make_state(next_poll_offset=-1.0, counter=make_counter("brake"))
        self.m["fetch"].return_value = RoundResult(overview_ok=True)
        self.run_it(state)
        self.assertEqual(state.plan.due.call_args[0][3], "brake")
        self.assertEqual(self.m["fetch"].call_args[1]["quota_mode"], "brake")
        cycle = self.m["cycle"].call_args[0][1]
        self.assertNotIn("Kontingent", [n for _, _, n in cycle])

    def test_quota_blocked_at_token_precheck(self):
        state = make_state(next_poll_offset=-1.0, counter=make_counter("ok"))
        state.token_store.get_access_token.side_effect = QuotaBlocked("stop")
        self.m["fetch"].return_value = RoundResult(overview_ok=False)
        with self.assertLogs(level="WARNING") as cm:
            self.run_it(state)
        self.assertTrue(any("Token refresh deferred" in r for r in cm.output))
        self.m["fetch"].assert_called_once()

    def test_fetch_state_saved_after_round(self):
        counter = make_counter("ok")
        state = make_state(next_poll_offset=-1.0, counter=counter)
        self.m["fetch"].return_value = RoundResult(overview_ok=True)
        self.run_it(state)
        self.m["export"].assert_called_once_with(state.plan, state.cache)
        counter.save_fetch_state.assert_called_once_with({"x": 1})

    def test_429_during_round_stops_and_suppresses_error(self):
        counter = make_counter("ok")
        counter.state.side_effect = ["ok", "stopped", "stopped"]
        state = make_state(next_poll_offset=-1.0, counter=counter)
        state.consecutive_failures = 2
        self.m["fetch"].return_value = RoundResult(overview_ok=False)
        self.run_it(state)
        self.assertEqual(state.consecutive_failures, 0)
        self.display.render.assert_not_called()

    def test_day_summary_logged_without_poll(self):
        line = "Calls 2026-11-06: 3 (overview 2, token 1); cycle 3/1800"
        state = make_state(counter=make_counter("ok", [line]))
        with self.assertLogs(level="INFO") as cm:
            self.run_it(state)
        self.assertTrue(any(line in r for r in cm.output))

    def test_night_restart_rotates_cached_energy(self):
        state = make_state(due=(), counter=make_counter("ok"))
        self.assertTrue(self.run_it(state))
        cycle = self.m["cycle"].call_args[0][1]
        self.assertEqual([n for _, _, n in cycle], ["Produktion"])

    def test_main_source_clears_display_only_in_finally(self):
        src = (Path(main.__file__)).read_text()
        self.assertEqual(src.count("display.clear()"), 1)
        self.assertNotIn("is_sleep_time", src)
        self.assertNotIn("in_sleep", src)


if __name__ == "__main__":
    unittest.main()
