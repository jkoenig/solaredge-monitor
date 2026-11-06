"""One fetch round of the interim D-07 cadence.

The cadence itself lives in fetch_schedule.FetchPlan; this module only runs
the jobs the plan says are due, keeps the last good value of every data type
in a DataCache and patches today's bar of the history (D-06). Phase 13 adds
the call counter around these calls.

LoginRequired raised by any API method propagates to the caller.
"""

import logging
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import List, Optional

import fetch_schedule as fs
from models import BatteryData, EnergyDetails, EnergyHistory, ForecastData


@dataclass
class DataCache:
    """Last successful value of every data type."""
    energy: Optional[EnergyDetails] = None
    battery: Optional[BatteryData] = None
    history: Optional[EnergyHistory] = None
    forecast: Optional[ForecastData] = None
    temperature: Optional[float] = None


@dataclass(frozen=True)
class RoundResult:
    overview_ok: bool
    battery_detected: Optional[bool] = None


def patch_history_today(
    history: EnergyHistory, today: date, production_kwh: float, consumption_kwh: float
) -> EnergyHistory:
    """Return history re-aligned to end at `today` with today's values set (D-06).

    Accepted limitation: today's bar comes from the site overview, while older
    bars come from /energy (production) and the summed meter telemetry
    (consumption). The sources may differ slightly, so the last bar can shift a
    little when the next history refresh replaces it. A consistent source would
    need extra API calls (credit budget), so the small mismatch is accepted.
    """
    n = len(history.dates)
    if n == 0:
        return history
    old_prod = dict(zip(history.dates, history.production))
    old_cons = dict(zip(history.dates, history.consumption))
    dates = [(today - timedelta(days=n - 1 - i)).isoformat() for i in range(n)]
    production = [old_prod.get(d, 0.0) for d in dates]
    consumption = [old_cons.get(d, 0.0) for d in dates]
    production[-1] = production_kwh
    consumption[-1] = consumption_kwh
    return EnergyHistory(
        dates=dates,
        production=production,
        consumption=consumption,
        fetched_at=history.fetched_at,
    )


def fetch_round(
    api,
    plan,
    cache: DataCache,
    now: datetime,
    has_battery: bool,
    battery_known: bool,
    forecast_api=None,
) -> RoundResult:
    """Run every job FetchPlan says is due and update the cache."""
    detected = None
    if not battery_known:
        if fs.DEVICES in plan.due(now, has_battery, battery_known):
            detected = api.detect_battery()
            plan.record(fs.DEVICES, now, detected is not None)
            if detected is not None:
                has_battery = detected

    jobs = plan.due(now, has_battery, battery_known or detected is not None)
    if not jobs:
        logging.debug("Fetch round skipped (overview backoff)")
        return RoundResult(overview_ok=False, battery_detected=detected)
    logging.info("Fetch round: jobs=%s", sorted(jobs))

    overview_ok = False

    if fs.OVERVIEW in jobs:
        energy = api.get_overview(retry=not plan.in_backoff)
        plan.record(fs.OVERVIEW, now, energy is not None)
        if energy is not None:
            cache.energy = energy
            overview_ok = True

    if fs.TEMPERATURE in jobs:
        temp = api.get_storage_temperature()
        plan.record(fs.TEMPERATURE, now, temp is not None)
        if temp is not None:
            cache.temperature = temp
            if fs.STORAGE not in jobs and cache.battery is not None:
                cache.battery = replace(cache.battery, internal_temp=temp)

    if fs.STORAGE in jobs:
        internal_temp = cache.temperature if cache.temperature is not None else 0.0
        battery = api.get_battery_telemetry(internal_temp=internal_temp)
        plan.record(fs.STORAGE, now, battery is not None)
        if battery is not None:
            cache.battery = battery

    if fs.HISTORY in jobs:
        history = api.get_energy_history()
        plan.record(fs.HISTORY, now, history is not None)
        if history is not None:
            cache.history = history

    if cache.history is not None and cache.energy is not None:
        cache.history = patch_history_today(
            cache.history, now.date(), cache.energy.production, cache.energy.consumption
        )

    if forecast_api is not None:
        raw = forecast_api.get_forecast()
        actual = cache.energy.production if cache.energy is not None else 0.0
        if raw:
            cache.forecast = ForecastData(
                today_kwh=raw.today_kwh,
                tomorrow_kwh=raw.tomorrow_kwh,
                actual_production=actual,
                fetched_at=raw.fetched_at,
            )
        elif cache.forecast is not None and overview_ok:
            cache.forecast = replace(cache.forecast, actual_production=actual)

    return RoundResult(overview_ok=overview_ok, battery_detected=detected)


def build_cycle(screens: list, cache: DataCache) -> List[tuple]:
    """Map screens to (render_fn, data, name) using cached values; skip screens without data."""
    by_key = {
        "energy": cache.energy,
        "battery": cache.battery,
        "history": cache.history,
        "forecast": cache.forecast,
    }
    cycle = []
    for render_fn, data_key, name in screens:
        data = by_key.get(data_key)
        if data is not None:
            cycle.append((render_fn, data, name))
    return cycle
