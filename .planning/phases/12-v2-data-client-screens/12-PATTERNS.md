# Phase 12: V2 Data Client & Screens - Pattern Map

**Mapped:** 2026-11-05
**Files analyzed:** 16 (new or modified)
**Analogs found:** 15 / 16 (history-patching helper has no direct analog)

No serial numbers or site IDs appear here. The test fixtures below use fake placeholders only.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `solaredge_api.py` (rewrite as V2 client on TokenStore) | service/client | request-response | current `solaredge_api.py` (return-None-on-failure, parse/log structure) plus `token_store.py` (`authorized_request`, `requests.exceptions` handling) | exact (role), new transport |
| `models.py` (drop `PowerFlow`/`SiteOverview`; change `EnergyDetails`, `BatteryData`) | model | transform | `models.py` itself (frozen dataclasses) | exact |
| battery presence cache (in the V2 client or a small helper module) | utility | file-I/O (atomic write) | `token_store.TokenStore.save` / `load` (lines 145-187) | role-match |
| `main.py` (`fetch_data`, `init_site_clients`, cadences, `last_successful_*`) | controller/orchestrator | batch/polling, event-driven | `main.py` itself | exact |
| `config.py` (drop `api_key`, D-07 defaults) | config | transform | `config.py` itself (env parsing, `log_startup`) | exact |
| `screens/production.py` | component (renderer) | transform | itself | exact |
| `screens/consumption.py` | component (renderer) | transform | itself | exact |
| `screens/feed_in.py`, `screens/purchased.py` | component (renderer) | transform | themselves (rename fields only) | exact |
| `screens/battery.py` | component (renderer) | transform | itself | exact |
| `screens/history.py` | component (renderer) | transform | itself (no change expected) | exact |
| `screens/forecast.py` / `ForecastData` | component | transform | itself (only the feed in `main.py` changes) | exact |
| `screens/__init__.py` | config/registry | n/a | itself (`get_screens`, data_key docs) | exact |
| `.env.example`, `README.md` (API-key lines) | config/docs | n/a | itself. README rewrite belongs to Phase 14, but the `SOLAREDGE_API_KEY` line must go from `.env.example` now | exact |
| `tests/test_solaredge_api.py` (new) | test | request-response (mocked) | `tests/test_token_store.py` | role-match |
| `tests/test_main_login_state.py` (edit) | test | subprocess smoke | itself (remove `SOLAREDGE_API_KEY` env at line 25) | exact |
| `tests/test_config.py` / `tests/test_screens_v2.py` (optional new) | test | transform | `tests/test_token_store.py` style (stdlib unittest) | partial |

## Conventions

Convention derivation skipped (`gsd-tools verify conventions --derive` returned `no-readable-files` for this repo). Observed by reading instead:

| Axis | Dominant | Notes |
|---|---|---|
| File names | snake_case modules (`token_store.py`, `forecast_api.py`) | named contract |
| Identifiers | snake_case functions/vars, PascalCase classes, UPPER_CASE constants | named contract |
| Exports/imports | flat top-level imports (`from models import ...`, `from token_store import ...`); tests insert repo root into `sys.path` | named contract |
| Language | English code/logs/docstrings, German display copy | named contract |

Contested hotspots (author's choice): the CJS/SDK dual resolver (`bin/lib/**` CJS vs `sdk/src/**` ESM) does not exist in this Python repo. Match the local style of the directory you edit.

## Pattern Assignments

### `solaredge_api.py` (V2 client, request-response)

**Analogs:** current `solaredge_api.py` (shape), `token_store.py` (transport).

Decision: rewrite in place and keep the module/class name, so `main.py` imports barely change. Constructor takes the `TokenStore` instead of `api_key`/`site_id` (`site_id` comes from `token_store.site_id`, which raises `LoginRequired`).

**Imports pattern** (`solaredge_api.py` lines 12-19, adapt):
```python
import logging
from datetime import datetime, timedelta
from typing import Optional
import requests

from models import EnergyDetails, EnergyHistory
# new: from token_store import TokenStore, LoginRequired, TransientAuthError
```
Drop `HTTPAdapter` and `urllib3.Retry` entirely (D: no blanket retry on 429/5xx). Base URL is now `https://monitoringapi.solaredge.com/v2`.

**Return-None-on-failure `_request` pattern** (current lines 60-90, keep the structure, swap transport):
```python
try:
    response = self.session.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()
except requests.exceptions.Timeout:
    logging.error(f"API timeout after 10s: {endpoint}")
    return None
except requests.exceptions.HTTPError as e:
    logging.error(f"API HTTP error {e.response.status_code}: {endpoint}")
    return None
except requests.exceptions.RequestException as e:
    logging.error(f"API request failed: {endpoint} - {e}")
    return None
```
Change to: `resp = self.token_store.authorized_request("GET", url, params=params)`; check `resp.status_code` explicitly. Rules from CONTEXT:
- `LoginRequired` and `TransientAuthError` must NOT be swallowed inside `_request` as generic failures. `main.py` already catches `LoginRequired` and calls `enter_login_state`. Let `LoginRequired` propagate (document it), or re-raise it, and treat `TransientAuthError` as a failed fetch (None).
- At most one retry, only on 5xx/timeout (a simple loop of 2 attempts; no sleep storm). 400/403: log status + endpoint (no body, no ids), return None, no retry. 429: no retry.
- Log endpoint names without the site id. Mask like `****{site_id[-4:]}` if an id must be logged (see `config.log_startup` line 164). Never log serials.
- `token_store.authorized_request` already sets `timeout=HTTP_TIMEOUT` (10) and has a retry-free `requests.Session` (`token_store.py` lines 304-317, 135-136).

**Parse pattern** (current `get_energy_details` lines 158-195): wrap in `try/except (KeyError, ValueError, TypeError)`, log `Failed to parse ... response: {e}`, return None. Replace the meter loop with:
- Overview (`GET /sites/{id}/overview`): per D-08, read `production.{total,toSelfConsumption,toStorage,toGrid,unit}` and `consumption.{total,fromPv,fromStorage,fromGrid,unit}`. Null maps to 0, convert via `unit` (WH/KWH/MWH/GWH to kWh). Write one small `_to_kwh(value, unit)` helper (None gives 0.0).
- History: `_request` the two endpoints (`/sites/{id}/energy?resolution=DAY&unit=WH` and `/sites/{id}/meters/telemetry?resolution=DAY`). `from`/`to` must carry an offset (naive times give 400). Build the ISO strings with `datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds")` (same tz as `main.is_sleep_time`, `main.py` lines 72-75). Bucket by `timestamp[:10]` (local date part, D-11). Sum every meter that carries `consumptionEnergy`; do not assume meter keys are serials (D-10).
- Date-indexed accumulation pattern to keep (current lines 282-308): build `production_by_date` / `consumption_by_date` dicts keyed by `entry.get("date", "")[:10]`, then emit ordered lists for 14 days with `.get(d, 0.0)`. Use `timestamp` instead of `date`.
- Battery telemetry: last non-null per metric. Write a `_last_non_null(values)` helper (iterate `reversed`). `stateOfEnergy` (percent), `chargePower - dischargePower` (W to kW), `remainingEnergy` (Wh to kWh). Ignore `acGridChargingEnergy` (empty values list, D-11). Window is the last ~1 h with an offset-bearing `from`/`to`, `resolution=QUARTER_HOUR`.
- Storage status (`/storage/status`): `internalTemperature` last non-null. A successful fetch with null gives 0.0 (UI-SPEC null rule). Failed fetch gives None (caller keeps the cached value).
- Devices (`/devices?types=BATTERY`): response is a JSON array; battery present when any entry has `active is True`.
- Battery status derivation (replaces the V1 `"Charge"/"Discharge"/"Idle"` string): keep the internal strings so `STATUS_MAP` and the screen stay stable. Net power `> +threshold` is "Charge", `< -threshold` is "Discharge", else "Idle". Threshold 50 W (UI-SPEC).

**Remove:** `get_current_power_flow`, `get_site_overview`, `has_battery` (inventory), `get_storage_data` (V1 `storageData`), `api_key` param.

---

### Battery presence cache (D-09 / API-03; file-I/O)

**Analog:** `token_store.py` `load`/`save` (lines 145-187). Location: next to the token file (`Path(config.token_file).parent / ".battery.json"` or similar). Delete the file to re-detect.

**Atomic write pattern** (`token_store.py` lines 159-187), copy minus the flock and 0600 mode if not needed (file holds no secret, but never store serials):
```python
fd, tmp = tempfile.mkstemp(dir=directory, prefix=self.token_file.name + ".", suffix=".tmp")
try:
    try:
        os.fchmod(fd, 0o600)
        payload = json.dumps(data.to_dict(), indent=2).encode("utf-8")
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, self.token_file)
except BaseException:
    with contextlib.suppress(FileNotFoundError):
        os.unlink(tmp)
    raise
```
**Tolerant load pattern** (lines 145-157): `FileNotFoundError` and `OSError` and `ValueError`/`json.JSONDecodeError` all map to "unknown, re-detect" (return None) rather than raising. Store only `{"version": 1, "has_battery": bool}` (plus optionally `checked_at`), never serial numbers. On restart: read the cache; only call `/devices` if the cache is missing.

---

### `models.py` (model, transform)

**Analog:** itself. Frozen dataclasses with `fetched_at: datetime = field(default_factory=datetime.now)` last (lines 14-21, 41-61, 103-120).

Changes:
- Delete `PowerFlow` (lines 14-38) and `SiteOverview` (lines 64-84).
- `EnergyDetails` (lines 41-61): keep the existing field names where screens use them (`production`, `self_consumption`, `feed_in`, `consumption`, `purchased`) and ADD `to_storage` and `from_pv`, `from_storage` (all kWh, floats) so screens use direct values (UI-SPEC). Map: `self_consumption = production.toSelfConsumption`, `feed_in = production.toGrid`, `purchased = consumption.fromGrid`, `to_storage = production.toStorage`, `from_pv = consumption.fromPv`, `from_storage = consumption.fromStorage`. Give new fields defaults (`= 0.0`) before `fetched_at` only if call sites need it.
- `BatteryData` (lines 103-120): keep `state_of_charge`, `status`, `internal_temp`, `available_energy`, `power` (kW, signed; sign convention is only consumed through `abs()` and status). Docstring update: `available_energy` is `remainingEnergy` (currently stored), not pack size; temperature from `/storage/status`.
- `EnergyHistory` unchanged (dates, production, consumption lists of length 14).
- Docstring of `ForecastData.actual_production` (line 132) should point to overview `production.total`.

---

### `main.py` (orchestrator, polling)

**Analog:** itself.

**Imports** (lines 34-47): replace `from models import BatteryData, ForecastData` as needed; `from solaredge_api import SolarEdgeAPI` stays if the class name is kept. Update the module docstring (lines 16-19) to drop `SOLAREDGE_API_KEY`.

**Lazy site-client init** (lines 157-165), keep the shape and change construction:
```python
def init_site_clients(config: Config, site_id: str, has_forecast: bool):
    api = SolarEdgeAPI(config.api_key, site_id)      # -> SolarEdgeAPI(token_store)
    battery_detected = api.has_battery()             # -> cached /devices lookup
    logging.info(f"Battery detected: {battery_detected}")
    screens = get_screens(has_battery=battery_detected, has_forecast_config=has_forecast)
```
`init_site_clients` needs the `token_store` passed in (it is constructed at lines 220-222, before the loop). Called at lines 340-341 inside the loop after `token_store.site_id` is read.

**Fetch fan-out** (`fetch_data`, lines 110-154). Rewrite around per-endpoint cadences; keep the return tuple `(energy_details, battery_data, history_data, forecast_data)` so the cycle-building code (lines 366-376 and 398-407) stays unchanged. Cadence state (next_history_due, next_storage_due, temp fetch slots, last temperature) must live outside the pure function: either in a small `FetchSchedule`/state object created in `main()` or `nonlocal` locals like `consecutive_failures`. Keep it easy for Phase 13 to replace (single place).

**Forecast feed** (lines 141-152): keep; `actual_prod = energy_details.production if energy_details else 0.0` still works.

**Today's bar patch (D-06):** after getting history, replace the last element of `production`/`consumption` with the overview's `production.total`/`consumption.total`, and make sure `dates[-1]` is today's local date. `EnergyHistory` is frozen, so use `dataclasses.replace` or build a new instance. No analog exists for this helper; write it as a pure function (easy to unit test).

**Stale-data fallback pattern** (lines 248-251, 349-358, 395-408): keep `last_successful_energy/battery/history/forecast`. Note the success branch hinges on `energy_details is not None`. With overview as the single poll call, that still holds. Catch `LoginRequired` raised from API calls the same way as lines 326-330 (`enter_login_state(e.reason); continue`).

**Interim cadence (D-07):** the poll interval is currently `config.poll_interval * 60` (line 252) and the sleep window is `is_sleep_time(config)` (lines 65-91, defaults 0-6). New defaults: poll interval 30 min, daytime window e.g. sleep 20 to 7 (planner picks; Phase 13 says 07:00-20:00). The Pi `.env` has no overrides, so these must be the code defaults in `config.py`, and `.env.example` (which sets `SOLAREDGE_POLL_INTERVAL=5`, `SLEEP_START=0`, `SLEEP_END=6`) must be updated so a copy of it does not burn credits.

**Budget check:** with overview every 30 min over 13 h that is about 26 calls, storage hourly about 13, history 2, temperature 2, plus about 8 token refreshes, which is about 51 calls/day.

**Log summary line** (lines 359-364) uses `energy_details.production/consumption/feed_in/purchased`; keep field names so it stays valid.

---

### `config.py` (config)

**Analog:** itself.

- Remove `api_key` field (line 47), the required check (lines 83-85), the docstring bullet (lines 28-29), and the masked log lines (159, 162).
- With `api_key` gone, `errors` can only come from numeric settings; keep the "accumulate errors, raise once" structure (lines 80, 140-143).
- Defaults pattern to copy for the D-07 change (lines 101-126), e.g.:
```python
poll_str = os.environ.get("SOLAREDGE_POLL_INTERVAL", "5")
try:
    self.poll_interval = int(poll_str)
    if self.poll_interval < 1:
        errors.append("  - SOLAREDGE_POLL_INTERVAL: Must be >= 1 minute")
except ValueError:
    errors.append(f"  - SOLAREDGE_POLL_INTERVAL: Must be an integer (got '{poll_str}')")
```
Change the `"5"` / `"0"` / `"6"` string defaults AND the dataclass defaults (lines 57-59) together. Consider whether `minimum: 1` should become a larger floor, since 1-minute polling is now a credit-burn risk (planner's call, within D-07).
- Masking pattern for any id (line 164): `f"****{self.site_id[-4:]}" if len(self.site_id) >= 4 else "****"`.
- Docs to update in the same pass: `.env.example` lines 10-13 (remove API key block) and 53-55 (poll/sleep defaults); `README.md` lines 84, 103, 196 mention the key (README overhaul is Phase 14, but stale `SOLAREDGE_API_KEY` mentions are cheap to remove now).

---

### `screens/production.py` (renderer, transform)

**Analog:** itself. Layout code stays byte-for-byte; only data fields change.

Edits:
- Line 85: delete `battery_energy = max(0.0, data.production - data.self_consumption - data.feed_in)`.
- Line 118: `value2 = f"{battery_energy:.1f} kWh"` becomes `f"{data.to_storage:.1f} kWh"`.
- Lines 52, 99, 137 (`data.production`, `data.self_consumption`, `data.feed_in`) are unchanged if field names are kept.
- Bar percentage (line 79) stays: `min(100.0, (data.self_consumption / data.production) * 100.0) if data.production > 0 else 0.0`.

### `screens/consumption.py`

**Analog:** itself.
- Line 85: delete `battery_energy = max(0.0, data.consumption - data.self_consumption - data.purchased)`.
- Column 1 (line 99): `data.self_consumption` becomes `data.from_pv` (label "Von PV"). The bar percentage at line 79 (`data.self_consumption / data.consumption`) must also use `from_pv`, otherwise the bar legend "Davon X% von PV-Anlage" is wrong. This is an easy miss because in the old model `self_consumption` was production-side.
- Column 2 value becomes `data.from_storage` ("Von Akku"); column 3 (line 137) stays `data.purchased` ("Vom Netz").

### `screens/feed_in.py`, `screens/purchased.py`

Line 44 / 71 in each use `data.feed_in` / `data.purchased` with `data.production` / `data.consumption` as the denominators. No change if field names are kept.

### `screens/battery.py`

**Analog:** itself.

- Idle legend is already empty (lines 68-71). Keep the `STATUS_MAP` lookup. Per UI-SPEC the English "Idle"/"Leerlauf" must never show: the `data.status == "Idle"` branch (line 68) guarantees that for the legend, so make sure the V2 status derivation emits exactly `"Idle"` (or change the check to a tolerant one).
- Line 59 (`value_text = f"{data.state_of_charge}"`) is integer; make `BatteryData.state_of_charge` an `int` (cast with `int(round(...))`).
- Line 119 `f"{data.internal_temp:.0f}°C"` and line 138 `f"{data.available_energy:.1f} kWh"` unchanged.
- Fallback when temperature was never fetched (UI-SPEC leaves to planner): `main.py` should keep the last known temperature in cadence state; before the first successful fetch use 0.0 (same as the V1 fallback `storage["internal_temp"] if storage else 0.0`, `main.py` lines 131-133). Document the choice.

### `screens/history.py`

No change expected. It reads `data.dates[i][-2:]` (line 90) and bars from `data.production`/`data.consumption`; today's bar is patched in `main.py` before rendering. Max is computed in this file from the 14 values, so it includes the patched value automatically.

### `screens/__init__.py`

Unchanged apart from keeping the `data_key` contract (`"energy"`, `"battery"`, `"history"`, `"forecast"`). Update the `EnergyDetails` doc only if renamed.

---

### `tests/test_solaredge_api.py` (new; mocked requests)

**Analog:** `tests/test_token_store.py`. stdlib `unittest`, no live calls (CONTEXT).

**Header and sys.path pattern** (lines 1-27):
```python
import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402
```

**Fake response helper** (lines 50-56), copy verbatim and add `.headers`/`raise_for_status` only if the client uses them:
```python
def fake_response(status=200, body=None, json_error=False):
    resp = mock.MagicMock()
    resp.status_code = status
    if json_error:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = body if body is not None else {}
    return resp
```

**Store test case with temp dir** (lines 57-67): build a real `TokenStore` on a temp token file, or simpler, a `mock.MagicMock()` token store whose `authorized_request` returns canned responses and whose `site_id` is `"12345"` (fake). For battery-cache tests use `tempfile.TemporaryDirectory` + `self.addCleanup(self._tmp.cleanup)`.

**Fixtures:** canned dicts shaped like D-08..D-11 with fake values and fake serials such as `"SN-TEST-1"` (never real ones):
- overview with `unit: "WH"`, null `toStorage` (null-to-0), and one `unit: "KWH"` case.
- `/devices` array with two batteries (`active: false`, `active: true`); and an array with none active.
- `/meters/telemetry` with only `{"CONSUMPTION": {"consumptionEnergy": {"unit": "WH", "values": [{"timestamp": "2026-10-25T00:00:00+02:00", "value": ...}]}}}` including a DST switch (`+02:00` to `+01:00` on 2026-10-25) and a null bucket.
- `/energy` 14 values.
- `/storage/telemetry` with trailing null values to test last-non-null, plus an empty `acGridChargingEnergy` values list.
- `/storage/status` with null last value.

**Cases to cover:** 5xx then success (exactly one retry), 5xx twice gives None, 400/403 gives None with no retry (assert `call_count`), timeout once then success, `LoginRequired` propagates, malformed body gives None, idle threshold (below 50 W empty/Idle, above Charge/Discharge), today-bar patch helper, secret/id hygiene (use the `test_secret_hygiene` idea at line 322: assert the fake site id and serial do not appear in `assertLogs` output).

**Mock-patch style for side effects** (line 106): `with mock.patch("token_store.os.replace", side_effect=OSError("boom")):` for the battery cache write-failure test.

### `tests/test_main_login_state.py`

Remove `"SOLAREDGE_API_KEY": "dummykey1234",` (line 25). Without this, nothing else breaks, but after `config.py` stops requiring the key the env entry is dead; the existing assertions (no poll, one `login_` PNG, no `API HTTP error` markers) still apply.

---

## Shared Patterns

### Return None on failure, caller keeps stale data
**Source:** `solaredge_api.py` lines 60-90 and `main.py` lines 349-408.
**Apply to:** every new V2 fetch method; `main.py` falls back to `last_successful_*`. Fetch failure shows no new on-screen indicator (UI-SPEC).

### Auth and refresh
**Source:** `token_store.py` lines 304-317 (`authorized_request`).
**Apply to:** all V2 calls (D-01). 401 gives one refresh then one retry, a second 401 raises `LoginRequired("API rejected token after refresh")`, which `main.py` turns into the login screen (lines 326-339 show the catch pattern).

### Logging hygiene (secrets, ids, serials)
**Source:** `token_store.py` module docstring ("Secrets ... are never logged"), `config.py` lines 163-167 (masking), error log style `logging.error(f"API HTTP error {status}: {endpoint}")`.
**Apply to:** all new code. Log endpoint path templates without `{id}` substituted, never response bodies, never serials.

### Parse try/except
**Source:** `solaredge_api.py` lines 193-195.
```python
except (KeyError, ValueError, TypeError) as e:
    logging.error(f"Failed to parse energy details response: {e}")
    return None
```
**Apply to:** every parser. Add `IndexError` where lists are indexed.

### Atomic file persistence
**Source:** `token_store.py` lines 159-187. **Apply to:** battery cache file.

### Frozen dataclasses with `fetched_at`
**Source:** `models.py` lines 41-61. **Apply to:** any new model; use `dataclasses.replace` to derive patched copies.

### Env-driven config with accumulated errors
**Source:** `config.py` lines 80-143. **Apply to:** any new settings (for example cadence knobs, if added).

### German display copy, English code
**Source:** screens use German literals ("Verbraucht", "In Akku", "Ins Netz", "Von PV", "Von Akku", "Vom Netz", "Temperatur", "Verfügbar"). No new strings this phase (UI-SPEC).

### Timezone
**Source:** `main.py` lines 72-75, `ZoneInfo("Europe/Berlin")`. **Apply to:** building `from`/`to` with offsets and "today" for the history patch. Bucket by the local date part of timestamps, no UTC conversion (D-11).

## No Analog Found

| File/Function | Role | Data Flow | Reason |
|---|---|---|---|
| Per-endpoint cadence scheduler (overview 30 min, storage hourly, history daily, temperature twice a day) | utility/state | event-driven, time-based | Only a single `next_poll` monotonic timer exists (`main.py` lines 252-254, 410-418). Use that `time.monotonic()` pattern per endpoint, and a date-keyed "last done" marker for the daily and twice-daily jobs. Keep it in one object so Phase 13 can swap it. |
| Today-bar patch helper | utility | transform | New behavior (D-06). Pure function on `EnergyHistory`. |
| ISO-8601 with-offset window builder | utility | transform | V1 used naive `"%Y-%m-%d %H:%M:%S"` strings (`solaredge_api.py` lines 145-150, 264-271). V2 needs offsets. Use `datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds")`. |
| Unit conversion helper (WH/KWH/MWH/GWH to kWh) | utility | transform | V1 hard-coded Wh/1000. |

## Metadata

**Analog search scope:** repo root `*.py`, `screens/`, `rendering/` (not touched), `tests/`, `.env.example`, `README.md`.
**Files read:** `solaredge_api.py`, `models.py`, `main.py`, `token_store.py`, `config.py`, `screens/production.py`, `screens/battery.py`, targeted ranges of `screens/consumption.py`, `screens/history.py`, `screens/__init__.py`, `tests/test_token_store.py`, `tests/test_main_login_state.py`, `.env.example`, `V2-API.md` section 1.
**Stale `api_key` references found (must all be removed):** `config.py` 29, 47, 83-85, 159, 162; `main.py` 17, 159; `.env.example` 13; `README.md` 84, 103, 196; `tests/test_main_login_state.py` 25; `solaredge_api.py` (rewritten).
**Pattern extraction date:** 2026-11-05
