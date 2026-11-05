"""SolarEdge Monitoring API V2 client on top of the Phase 11 TokenStore.

Every request goes through TokenStore.authorized_request (Bearer token, one
refresh on 401). Every call costs one API credit, so there is no blanket retry:
only get_overview may retry, once, on 5xx or timeout. All other jobs make one
attempt. 400/403/404/429 are never retried.

All public methods return None on any fetch or parse failure so the caller can
keep showing stale data. LoginRequired is deliberately not caught: it
propagates to main.py, which shows the login screen.

Logs never contain the site id, serial numbers, tokens, params or response
bodies. Endpoints are logged as path templates with a literal "{site_id}".
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import requests

from models import BatteryData, EnergyDetails, EnergyHistory
from token_store import TransientAuthError

SITE_TZ = ZoneInfo("Europe/Zurich")
BASE_URL = "https://monitoringapi.solaredge.com/v2"
IDLE_THRESHOLD_W = 50

_UNIT_FACTORS_TO_KWH = {
    "WH": 0.001,
    "KWH": 1.0,
    "MWH": 1000.0,
    "GWH": 1_000_000.0,
}

RETRY_SLEEP_SECONDS = 2


def to_kwh(value, unit) -> float:
    """Convert a value in WH/KWH/MWH/GWH to kWh. None becomes 0.0.

    Raises ValueError for an unknown unit.
    """
    if value is None:
        return 0.0
    factor = _UNIT_FACTORS_TO_KWH.get(str(unit).upper())
    if factor is None:
        raise ValueError("unknown energy unit")
    return float(value) * factor


def last_non_null(values) -> Optional[float]:
    """Return the last non-null "value" of a list of {"timestamp","value"} dicts."""
    for entry in reversed(values or []):
        if isinstance(entry, dict) and entry.get("value") is not None:
            return float(entry["value"])
    return None


def derive_battery_status(net_power_w: float, threshold_w: float = IDLE_THRESHOLD_W) -> str:
    """Return "Charge", "Discharge" or "Idle" from net power (positive = charging)."""
    if net_power_w > threshold_w:
        return "Charge"
    if net_power_w < -threshold_w:
        return "Discharge"
    return "Idle"


class SolarEdgeAPI:
    """V2 client. Construct with a TokenStore; site id comes from the store."""

    def __init__(
        self,
        token_store,
        sleep: Callable[[float], None] = time.sleep,
        now_fn: Optional[Callable[[], datetime]] = None,
    ):
        self.token_store = token_store
        self._sleep = sleep
        self._now_fn = now_fn or (lambda: datetime.now(SITE_TZ))

    def _now(self) -> datetime:
        return self._now_fn()

    def _window(self, hours: float) -> dict:
        """Offset-bearing from/to strings covering the last `hours` hours."""
        now = self._now()
        start = now - timedelta(hours=hours)
        return {
            "from": start.isoformat(timespec="seconds"),
            "to": now.isoformat(timespec="seconds"),
        }

    def _request(self, path_template: str, params: Optional[dict] = None, retry: bool = False):
        """GET a V2 path. Returns parsed JSON or None. LoginRequired propagates."""
        url = BASE_URL + path_template.format(site_id=self.token_store.site_id)
        attempts = 2 if retry else 1
        for attempt in range(1, attempts + 1):
            try:
                resp = self.token_store.authorized_request("GET", url, params=params)
            except requests.exceptions.Timeout:
                if attempt < attempts:
                    logging.warning(f"API timeout: {path_template} (attempt {attempt}), retrying")
                    self._sleep(RETRY_SLEEP_SECONDS)
                    continue
                logging.error(f"API timeout: {path_template}")
                return None
            except TransientAuthError:
                logging.warning(f"API auth refresh deferred: {path_template}")
                return None
            except requests.exceptions.RequestException as e:
                logging.error(f"API request failed: {path_template} ({type(e).__name__})")
                return None

            status = resp.status_code
            logging.info(f"API {path_template} -> {status}")

            if status >= 500:
                if attempt < attempts:
                    logging.warning(f"API HTTP {status}: {path_template} (attempt {attempt}), retrying")
                    self._sleep(RETRY_SLEEP_SECONDS)
                    continue
                logging.error(f"API HTTP error {status}: {path_template}")
                return None
            if status == 429:
                remaining = None
                try:
                    remaining = resp.headers.get("x-ratelimit-remaining-minute")
                except AttributeError:
                    pass
                logging.error(
                    f"API HTTP error 429: {path_template} "
                    f"(x-ratelimit-remaining-minute={remaining})"
                )
                return None
            if status >= 400:
                logging.error(f"API HTTP error {status}: {path_template}")
                return None

            try:
                return resp.json()
            except ValueError:
                logging.error(f"API response is not JSON: {path_template}")
                return None
        return None

    def get_overview(self, retry: bool = True) -> Optional[EnergyDetails]:
        """Today's energy totals from /overview (kWh, null becomes 0.0)."""
        body = self._request("/sites/{site_id}/overview", retry=retry)
        if body is None:
            return None
        try:
            if not isinstance(body, dict):
                raise TypeError("overview body is not an object")

            def section(name):
                obj = body.get(name)
                if obj is None:
                    return {}, "WH"
                return obj, obj.get("unit", "WH")

            prod, prod_unit = section("production")
            cons, cons_unit = section("consumption")
            return EnergyDetails(
                production=to_kwh(prod.get("total"), prod_unit),
                self_consumption=to_kwh(prod.get("toSelfConsumption"), prod_unit),
                feed_in=to_kwh(prod.get("toGrid"), prod_unit),
                to_storage=to_kwh(prod.get("toStorage"), prod_unit),
                consumption=to_kwh(cons.get("total"), cons_unit),
                purchased=to_kwh(cons.get("fromGrid"), cons_unit),
                from_pv=to_kwh(cons.get("fromPv"), cons_unit),
                from_storage=to_kwh(cons.get("fromStorage"), cons_unit),
            )
        except (KeyError, ValueError, TypeError, AttributeError):
            logging.error("Failed to parse overview response")
            return None

    def detect_battery(self) -> Optional[bool]:
        """True if at least one BATTERY device is active, None if unknown."""
        body = self._request("/sites/{site_id}/devices", {"types": "BATTERY"})
        if body is None:
            return None
        if not isinstance(body, list):
            logging.error("Failed to parse devices response")
            return None
        n_active = sum(1 for d in body if isinstance(d, dict) and d.get("active") is True)
        logging.info(f"Battery detection: {n_active} active of {len(body)}")
        return n_active > 0
