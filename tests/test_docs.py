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
        # All application modules, not only config.py: some keys are read
        # elsewhere (for example the log file in logging_setup.py).
        keys = set()
        for module in sorted(ROOT.glob("*.py")):
            keys |= set(re.findall(
                r'"((?:SOLAREDGE|FORECAST)_[A-Z_]+)"',
                module.read_text(encoding="utf-8")))
        self.assertIn("SOLAREDGE_POLL_INTERVAL", keys)
        self.assertIn("SOLAREDGE_LOG_FILE", keys)
        for key in sorted(keys):
            self.assertIn(key, self.text, f"{key} missing in .env.example")

    def test_parses_with_active_client_keys(self):
        values = dotenv_values(ROOT / ".env.example")
        self.assertIn("SOLAREDGE_CLIENT_ID", values)
        self.assertIn("SOLAREDGE_CLIENT_SECRET", values)

    def test_client_keys_ship_empty(self):
        # A placeholder would count as a real credential after "cp .env.example .env"
        # and could be sent to the token endpoint. Empty means "login required".
        values = dotenv_values(ROOT / ".env.example")
        self.assertEqual(values["SOLAREDGE_CLIENT_ID"], "")
        self.assertEqual(values["SOLAREDGE_CLIENT_SECRET"], "")
        self.assertNotIn("_here", "\n".join(
            line for line in self.text.splitlines() if not line.lstrip().startswith("#")))

    def test_no_workflow_references(self):
        self.assertIsNone(FORBIDDEN.search(self.text))


class ReadmeTest(unittest.TestCase):
    HEADINGS = [
        "## Hardware",
        "## SolarEdge-API-Zugang",
        "## Installation",
        "## Login-Skript",
        "## Re-Login nach mehr als 14 Tagen offline",
        "## API-Kontingent und Zähler",
        "## Fehlerbehebung",
        "## Deployment",
    ]
    MENTIONS = [
        "solaredge_login.py",
        "solaredge_login.example.ini",
        "seed_call_counter.py",
        "--from-journal",
        "--margin 20",
        "Login nötig",
        "Kontingent aufgebraucht",
        "time-sync.target",
        "./deploy.sh",
    ]

    def setUp(self):
        self.text = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_headings(self):
        for heading in self.HEADINGS:
            self.assertIn(heading + "\n", self.text)

    def test_mentions(self):
        for needle in self.MENTIONS:
            self.assertIn(needle, self.text)

    def test_screenshots_linked_and_present(self):
        links = set(re.findall(r"docs/screens/[a-z-]+\.png", self.text))
        for link in links:
            self.assertTrue((ROOT / link).is_file(), link)
        on_disk = {f"docs/screens/{p.name}" for p in (ROOT / "docs/screens").glob("*.png")}
        self.assertEqual(len(on_disk), 12)
        self.assertEqual(links, on_disk)

    def test_no_internal_references(self):
        self.assertNotIn(".planning", self.text)
        self.assertNotIn("docs/screen-", self.text)
        self.assertIsNone(re.search(r"\bD-\d+", self.text))


if __name__ == "__main__":
    unittest.main()
