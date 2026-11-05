"""Render tests for the V2 data contract (stdlib unittest, fake values only)."""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import ImageDraw  # noqa: E402

from models import BatteryData, EnergyDetails, EnergyHistory  # noqa: E402
from screens.battery import render_battery_screen  # noqa: E402
from screens.consumption import render_consumption_screen  # noqa: E402
from screens.history import (  # noqa: E402
    render_history_consumption_screen,
    render_history_production_screen,
)
from screens.production import render_production_screen  # noqa: E402

_ORIGINAL_TEXT = ImageDraw.ImageDraw.text


def drawn_texts(render, data):
    """Render and return every string passed to ImageDraw.text."""
    with mock.patch.object(
        ImageDraw.ImageDraw, "text", autospec=True, side_effect=_ORIGINAL_TEXT
    ) as spy:
        render(data)
    texts = []
    for call in spy.call_args_list:
        if "text" in call.kwargs:
            texts.append(call.kwargs["text"])
        else:
            texts.append(call.args[2])
    return texts


def energy(**overrides):
    values = dict(
        production=10.0,
        self_consumption=4.0,
        feed_in=3.0,
        consumption=8.0,
        purchased=1.0,
        to_storage=2.5,
        from_pv=5.0,
        from_storage=2.0,
    )
    values.update(overrides)
    return EnergyDetails(**values)


class ProductionScreenTest(unittest.TestCase):
    def test_in_akku_uses_direct_to_storage(self):
        texts = drawn_texts(render_production_screen, energy())
        self.assertIn("In Akku", texts)
        self.assertIn("2.5 kWh", texts)
        # old remainder (10 - 4 - 3) must not appear; 3.0 only as Ins Netz column
        self.assertEqual(texts.count("3.0 kWh"), 1)


class ConsumptionScreenTest(unittest.TestCase):
    def test_columns_use_direct_values(self):
        texts = drawn_texts(render_consumption_screen, energy())
        self.assertIn("5.0 kWh", texts)
        self.assertIn("2.0 kWh", texts)
        self.assertIn("1.0 kWh", texts)
        self.assertIn("Davon 62% von PV-Anlage", texts)

    def test_zero_consumption_does_not_divide_by_zero(self):
        texts = drawn_texts(
            render_consumption_screen,
            energy(consumption=0.0, from_pv=0.0, from_storage=0.0, purchased=0.0),
        )
        self.assertIn("Davon 0% von PV-Anlage", texts)


class BatteryScreenTest(unittest.TestCase):
    def test_idle_has_no_english_or_legend(self):
        data = BatteryData(
            state_of_charge=57, status="Idle", internal_temp=21.4,
            available_energy=4.3, power=0.02,
        )
        texts = drawn_texts(render_battery_screen, data)
        for expected in ("57", "21°C", "4.3 kWh"):
            self.assertIn(expected, texts)
        for text in texts:
            self.assertNotIn("Idle", text)
            self.assertNotIn("Leerlauf", text)
            self.assertNotIn(" mit ", text)

    def test_charging_legend(self):
        data = BatteryData(
            state_of_charge=50, status="Charge", internal_temp=20.0,
            available_energy=4.0, power=1.234,
        )
        self.assertIn("Lädt mit 1.2 kW", drawn_texts(render_battery_screen, data))

    def test_discharging_legend(self):
        data = BatteryData(
            state_of_charge=50, status="Discharge", internal_temp=20.0,
            available_energy=4.0, power=-0.8,
        )
        self.assertIn("Entlädt mit 0.8 kW", drawn_texts(render_battery_screen, data))


class HistoryScreenTest(unittest.TestCase):
    def test_fourteen_date_labels_across_dst_switch(self):
        start = date(2026, 10, 23)
        dates = [(start + timedelta(days=i)).isoformat() for i in range(14)]
        self.assertEqual(dates[-1], "2026-11-05")
        production = [float(i) for i in range(14)]
        production[3] = 0.0
        history = EnergyHistory(dates=dates, production=production, consumption=list(production))
        expected = [d[-2:] for d in dates]
        for render in (render_history_production_screen, render_history_consumption_screen):
            texts = drawn_texts(render, history)
            for label in expected:
                self.assertIn(label, texts)
            self.assertEqual(sum(1 for t in texts if t in set(expected)), 14)


if __name__ == "__main__":
    unittest.main()
