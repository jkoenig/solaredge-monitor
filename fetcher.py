"""One fetch round of the final Phase 13 cadence.

The cadence itself lives in fetch_schedule.FetchPlan (day: overview, storage,
history, temperature; night: only battery storage slots). This module runs
the jobs the plan says are due, keeps the last good value of every data type
in a DataCache and patches today's bar of the history. The counter state
(ok/brake/stopped) is passed through as quota_mode to every plan.due call.

Fetch state (plan slots, history, temperature and the last overview's energy
values with their site-local date) is exported into the counter file and
restored at startup (D-06), so a restart neither re-fetches history nor shows
a blank display at night. Today's history bar is patched only from an
overview fetched on the same site-local date.

LoginRequired raised by any API method propagates to the caller.
"""

import math
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
    energy_date: Optional[date] = None  # site-local date of the overview behind `energy`


@dataclass(frozen=True)
class RoundResult:
    overview_ok: bool
    battery_detected: Optional[bool] = None
    overview_attempted: bool = True


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


def _record(api, plan, job, now, ok: bool) -> None:
    """Record a job outcome, unless the call budget blocked it (no call was sent)."""
    if not ok and getattr(api, "quota_blocked", False) is True:
        logging.debug("Fetch job %s blocked by call budget; not recorded as failure", job)
        return
    plan.record(job, now, ok)


def fetch_round(
    api,
    plan,
    cache: DataCache,
    now: datetime,
    has_battery: bool,
    battery_known: bool,
    forecast_api=None,
    quota_mode: str = "ok",
) -> RoundResult:
    """Run every job FetchPlan says is due and update the cache."""
    detected = None
    if not battery_known:
        if fs.DEVICES in plan.due(now, has_battery, battery_known, quota_mode):
            detected = api.detect_battery()
            plan.record(fs.DEVICES, now, detected is not None)
            if detected is not None:
                has_battery = detected

    jobs = plan.due(now, has_battery, battery_known or detected is not None, quota_mode)
    if not jobs:
        logging.debug("Fetch round skipped (no jobs due)")
        return RoundResult(
            overview_ok=False, battery_detected=detected, overview_attempted=False
        )
    logging.info("Fetch round: jobs=%s", sorted(jobs))

    overview_ok = False

    if fs.OVERVIEW in jobs:
        api.quota_blocked = False
        energy = api.get_overview(retry=not plan.in_backoff)
        _record(api, plan, fs.OVERVIEW, now, energy is not None)
        if energy is not None:
            cache.energy = energy
            cache.energy_date = now.date()
            overview_ok = True

    if fs.TEMPERATURE in jobs:
        api.quota_blocked = False
        temp = api.get_storage_temperature()
        _record(api, plan, fs.TEMPERATURE, now, temp is not None)
        if temp is not None:
            cache.temperature = temp
            if fs.STORAGE not in jobs and cache.battery is not None:
                cache.battery = replace(cache.battery, internal_temp=temp)

    if fs.STORAGE in jobs:
        internal_temp = cache.temperature if cache.temperature is not None else 0.0
        api.quota_blocked = False
        battery = api.get_battery_telemetry(internal_temp=internal_temp)
        _record(api, plan, fs.STORAGE, now, battery is not None)
        if battery is not None:
            cache.battery = battery

    if fs.HISTORY in jobs:
        api.quota_blocked = False
        history = api.get_energy_history()
        _record(api, plan, fs.HISTORY, now, history is not None)
        if history is not None:
            cache.history = history

    energy_today = cache.energy is not None and cache.energy_date == now.date()
    if cache.history is not None and energy_today:
        cache.history = patch_history_today(
            cache.history, now.date(), cache.energy.production, cache.energy.consumption
        )

    if forecast_api is not None:
        raw = forecast_api.get_forecast()
        actual = cache.energy.production if energy_today else 0.0
        if raw:
            cache.forecast = ForecastData(
                today_kwh=raw.today_kwh,
                tomorrow_kwh=raw.tomorrow_kwh,
                actual_production=actual,
                fetched_at=raw.fetched_at,
            )
        elif cache.forecast is not None and overview_ok:
            cache.forecast = replace(cache.forecast, actual_production=actual)

    return RoundResult(
        overview_ok=overview_ok,
        battery_detected=detected,
        overview_attempted=fs.OVERVIEW in jobs,
    )


_ENERGY_FIELDS = (
    "production", "self_consumption", "feed_in", "consumption",
    "purchased", "to_storage", "from_pv", "from_storage",
)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def export_fetch_state(plan, cache: DataCache) -> dict:
    """JSON-able fetch state for the counter file (values only, no ids)."""
    history = None
    if cache.history is not None:
        history = {
            "dates": list(cache.history.dates),
            "production": list(cache.history.production),
            "consumption": list(cache.history.consumption),
            "fetched_at": cache.history.fetched_at.isoformat(),
        }
    energy = None
    if cache.energy is not None and cache.energy_date is not None:
        energy = {f: float(getattr(cache.energy, f)) for f in _ENERGY_FIELDS}
        energy["date"] = cache.energy_date.isoformat()
    return {
        "plan": plan.to_dict(),
        "history": history,
        "temperature": cache.temperature,
        "energy": energy,
    }


def _restore_history(h, now: datetime) -> Optional[EnergyHistory]:
    if not isinstance(h, dict):
        return None
    dates, prod, cons = h.get("dates"), h.get("production"), h.get("consumption")
    if not (isinstance(dates, list) and isinstance(prod, list) and isinstance(cons, list)):
        return None
    if not (len(dates) == len(prod) == len(cons)) or not dates:
        return None
    if not all(isinstance(d, str) for d in dates):
        return None
    if not all(_is_num(v) for v in prod) or not all(_is_num(v) for v in cons):
        return None
    try:
        fetched_at = datetime.fromisoformat(h.get("fetched_at"))
    except (TypeError, ValueError):
        fetched_at = datetime.now(now.tzinfo)
    return EnergyHistory(
        dates=list(dates), production=list(prod), consumption=list(cons),
        fetched_at=fetched_at,
    )


def _restore_energy(e, now: datetime):
    if not isinstance(e, dict):
        return None
    if not all(_is_num(e.get(f)) for f in _ENERGY_FIELDS):
        return None
    try:
        d = date.fromisoformat(e.get("date"))
    except (TypeError, ValueError):
        return None
    details = EnergyDetails(
        **{f: float(e[f]) for f in _ENERGY_FIELDS},
        fetched_at=datetime.now(now.tzinfo),
    )
    return details, d


def restore_fetch_state(plan, cache: DataCache, data, now: datetime) -> None:
    """Restore cache values and plan slots from export_fetch_state output.

    Tolerant: malformed input never raises and leaves the affected part empty.
    Battery and forecast are deliberately not persisted.
    """
    if not isinstance(data, dict):
        return
    history = _restore_history(data.get("history"), now)
    if history is not None:
        cache.history = history
    temp = data.get("temperature")
    temp_ok = _is_num(temp)
    if temp_ok:
        cache.temperature = float(temp)
    restored = _restore_energy(data.get("energy"), now)
    if restored is not None:
        cache.energy, cache.energy_date = restored

    plan_data = data.get("plan")
    if isinstance(plan_data, dict):
        slots = plan_data.get("slots")
        if isinstance(slots, list):
            def keep(e):
                if not isinstance(e, dict) or e.get("succeeded") is not True:
                    return True
                if e.get("job") == fs.HISTORY:
                    return history is not None
                if e.get("job") == fs.TEMPERATURE:
                    return temp_ok
                return True
            plan_data = dict(plan_data, slots=[e for e in slots if keep(e)])
        try:
            plan.load_dict(plan_data, now)
        except Exception as exc:  # never break startup on a bad file
            logging.warning("Could not restore fetch plan state: %s", exc)


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
