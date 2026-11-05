import json
import logging
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from battery_cache import load_battery_cache, save_battery_cache  # noqa: E402

SITE = "12345678"


class BatteryCacheTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.path = self.dir / ".battery.json"

    def test_roundtrip(self):
        for value in (True, False):
            self.assertTrue(save_battery_cache(self.path, SITE, value))
            self.assertIs(load_battery_cache(self.path, SITE), value)

    def test_missing_file(self):
        self.assertIsNone(load_battery_cache(self.path, SITE))

    def test_unreadable_file(self):
        self.path.mkdir()  # reading a directory raises OSError
        self.assertIsNone(load_battery_cache(self.path, SITE))

    def test_invalid_contents(self):
        good = {"version": 1, "has_battery": True}
        from battery_cache import _site_hash

        good["site_hash"] = _site_hash(SITE)
        cases = [
            "not json",
            "[1, 2]",
            json.dumps({**good, "version": 2}),
            json.dumps({**good, "version": True}),
            json.dumps({**good, "has_battery": "yes"}),
            json.dumps({**good, "has_battery": 1}),
        ]
        for text in cases:
            self.path.write_text(text)
            self.assertIsNone(load_battery_cache(self.path, SITE), text)

    def test_other_site(self):
        save_battery_cache(self.path, SITE, True)
        self.assertIsNone(load_battery_cache(self.path, "87654321"))

    def test_file_content_has_no_identifiers(self):
        save_battery_cache(self.path, SITE, True)
        raw = self.path.read_text()
        self.assertEqual(
            set(json.loads(raw).keys()), {"version", "has_battery", "site_hash"}
        )
        self.assertNotIn(SITE, raw)

    def test_mode_0600(self):
        save_battery_cache(self.path, SITE, True)
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)

    def test_write_failure(self):
        with mock.patch("battery_cache.os.replace", side_effect=OSError("boom")):
            with self.assertLogs(level=logging.WARNING):
                self.assertFalse(save_battery_cache(self.path, SITE, True))
        self.assertEqual(list(self.dir.glob("*.tmp")), [])
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
