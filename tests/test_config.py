"""Tests for config.py: V2 defaults, poll floor, API key removal."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config  # noqa: E402


def make_config(**env):
    base = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
    base.update(env)
    with mock.patch.dict(os.environ, base, clear=True):
        return Config()


class ConfigTests(unittest.TestCase):
    def test_empty_env_defaults(self):
        c = make_config()
        self.assertEqual(c.poll_interval, 30)
        self.assertEqual(c.sleep_start_hour, 20)
        self.assertEqual(c.sleep_end_hour, 7)
        self.assertFalse(hasattr(c, "api_key"))

    def test_api_key_env_ignored(self):
        c = make_config(SOLAREDGE_API_KEY="dummy-key-value")
        self.assertFalse(hasattr(c, "api_key"))

    def test_poll_interval_floor_warns(self):
        with self.assertLogs(level="WARNING") as cm:
            c = make_config(SOLAREDGE_POLL_INTERVAL="5")
        self.assertEqual(c.poll_interval, 30)
        self.assertTrue(any("30 min" in m for m in cm.output))

    def test_poll_interval_above_floor(self):
        self.assertEqual(make_config(SOLAREDGE_POLL_INTERVAL="45").poll_interval, 45)

    def test_poll_interval_not_integer(self):
        with self.assertRaises(ValueError):
            make_config(SOLAREDGE_POLL_INTERVAL="abc")

    def test_battery_cache_default_and_custom(self):
        c = make_config()
        self.assertEqual(c.battery_cache_file,
                         str(Path(c.token_file).parent / ".battery.json"))
        c = make_config(SOLAREDGE_TOKEN_FILE="/srv/x/tokens.json")
        self.assertEqual(c.battery_cache_file, str(Path("/srv/x/.battery.json")))

    def test_log_startup_has_no_api_key(self):
        c = make_config()
        with self.assertLogs(level="INFO") as cm:
            c.log_startup()
        self.assertFalse(any("API_KEY" in m for m in cm.output))
        self.assertFalse(any("exceed the interim" in m for m in cm.output))

    def test_log_startup_warns_on_long_daytime(self):
        c = make_config(SOLAREDGE_SLEEP_START="0", SOLAREDGE_SLEEP_END="6")
        with self.assertLogs(level="INFO") as cm:
            c.log_startup()
        self.assertTrue(any(m.startswith("WARNING") and "13 h" in m for m in cm.output))


if __name__ == "__main__":
    unittest.main()
