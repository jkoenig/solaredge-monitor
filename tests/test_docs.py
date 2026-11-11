"""Coverage checks for the user documentation (README and .env.example)."""

import re
import unittest
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = re.compile(r"phase|\.planning|\bD-\d+", re.IGNORECASE)


class EnvExampleTest(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / ".env.example").read_text(encoding="utf-8")

    def test_every_config_key_is_documented(self):
        config = (ROOT / "config.py").read_text(encoding="utf-8")
        keys = set(re.findall(r'"((?:SOLAREDGE|FORECAST)_[A-Z_]+)"', config))
        self.assertTrue(keys)
        for key in sorted(keys):
            self.assertIn(key, self.text, f"{key} missing in .env.example")

    def test_parses_with_active_client_keys(self):
        values = dotenv_values(ROOT / ".env.example")
        self.assertIn("SOLAREDGE_CLIENT_ID", values)
        self.assertIn("SOLAREDGE_CLIENT_SECRET", values)

    def test_no_workflow_references(self):
        self.assertIsNone(FORBIDDEN.search(self.text))


if __name__ == "__main__":
    unittest.main()
