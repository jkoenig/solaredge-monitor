#!/usr/bin/env python3
"""Render the documentation screenshots offline from invented example values.

Usage: python scripts/render_doc_screens.py [output_dir]

Writes one 1000x488 PNG per screen to docs/screens/ (default). Nothing is read
from the API, the cache or the environment; all values below are made up.
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models import BatteryData, EnergyDetails, EnergyHistory, ForecastData  # noqa: E402
from screens.battery import render_battery_screen  # noqa: E402
from screens.consumption import render_consumption_screen  # noqa: E402
from screens.error import (  # noqa: E402
    render_login_required_screen,
    render_quota_exhausted_screen,
)
from screens.feed_in import render_feed_in_screen  # noqa: E402
from screens.forecast import render_forecast_screen  # noqa: E402
from screens.history import (  # noqa: E402
    render_history_consumption_screen,
    render_history_production_screen,
)
from screens.production import render_production_screen  # noqa: E402
from screens.purchased import render_purchased_screen  # noqa: E402

NAMES = [
    "produktion", "verbrauch", "einspeisung", "bezug",
    "hausakku-charging", "hausakku-discharging", "hausakku-idle",
    "verlauf-produktion", "verlauf-verbrauch", "prognose",
    "login-noetig", "kontingent-aufgebraucht",
]

# Fixed timestamp so that no wall-clock value can leak into the images.
_FIXED = datetime(2025, 7, 14, 12, 0, 0)

_HISTORY_START = date(2025, 7, 1)
_HISTORY_PRODUCTION = [
    14.2, 17.8, 9.6, 6.1, 19.3, 21.0, 20.4, 12.7, 15.9, 22.1, 18.6, 8.3, 13.4, 19.8,
]
_HISTORY_CONSUMPTION = [
    10.4, 9.8, 12.1, 13.5, 8.7, 9.2, 11.0, 12.9, 10.1, 8.4, 9.9, 14.2, 11.6, 10.3,
]


def _energy() -> EnergyDetails:
    return EnergyDetails(
        production=18.4, self_consumption=7.9, feed_in=6.4,
        consumption=11.2, purchased=1.2,
        to_storage=4.1, from_pv=7.9, from_storage=2.1,
        fetched_at=_FIXED,
    )


def _battery(soc: int, status: str, temp: float, power: float) -> BatteryData:
    return BatteryData(
        state_of_charge=soc, status=status, internal_temp=temp,
        available_energy=round(soc / 100 * 10.0, 1), power=power,
        fetched_at=_FIXED,
    )


def _history() -> EnergyHistory:
    dates = [(_HISTORY_START + timedelta(days=i)).isoformat() for i in range(14)]
    return EnergyHistory(
        dates=dates, production=list(_HISTORY_PRODUCTION),
        consumption=list(_HISTORY_CONSUMPTION), fetched_at=_FIXED,
    )


def _images() -> dict:
    energy = _energy()
    history = _history()
    return {
        "produktion": render_production_screen(energy),
        "verbrauch": render_consumption_screen(energy),
        "einspeisung": render_feed_in_screen(energy),
        "bezug": render_purchased_screen(energy),
        "hausakku-charging": render_battery_screen(_battery(64, "Charge", 24.5, 1.8)),
        "hausakku-discharging": render_battery_screen(
            _battery(38, "Discharge", 22.8, -0.6)),
        "hausakku-idle": render_battery_screen(_battery(100, "Idle", 25.9, 0.0)),
        "verlauf-produktion": render_history_production_screen(history),
        "verlauf-verbrauch": render_history_consumption_screen(history),
        "prognose": render_forecast_screen(
            ForecastData(today_kwh=24.6, tomorrow_kwh=21.3,
                         actual_production=9.8, fetched_at=_FIXED)),
        "login-noetig": render_login_required_screen(),
        "kontingent-aufgebraucht": render_quota_exhausted_screen(date(2025, 8, 5)),
    }


def main(out_dir: Optional[str] = None) -> int:
    out = Path(out_dir) if out_dir else ROOT / "docs" / "screens"
    out.mkdir(parents=True, exist_ok=True)
    images = _images()
    for name in NAMES:
        path = out / f"{name}.png"
        images[name].save(path)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
