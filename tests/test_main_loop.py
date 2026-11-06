"""Tests for main.run_iteration: poll only when due, always rotate cached screens."""

import time
import unittest
from unittest import mock

import main
from fetcher import DataCache, RoundResult
from token_store import LoginRequired


def make_state(due=("overview",), next_poll_offset=1000.0, energy=True, has_battery=False):
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
    )


class RunIterationTest(unittest.TestCase):
    def setUp(self):
        patches = {
            "cycle": mock.patch.object(main, "run_screen_cycle"),
            "fetch": mock.patch.object(main, "fetch_round"),
            "save": mock.patch.object(main, "save_battery_cache"),
            "err": mock.patch.object(main, "render_error_screen", return_value="img"),
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
        # sleep/wake: display cleared, main resets the flag; next failed poll redraws
        state.error_screen_shown = False
        self.run_it(state)
        self.assertEqual(state.consecutive_failures, 4)
        self.assertEqual(self.display.render.call_count, 2)
        # but not on every further failure
        state.next_poll = time.monotonic() - 1
        self.run_it(state)
        self.assertEqual(self.display.render.call_count, 2)

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


if __name__ == "__main__":
    unittest.main()
