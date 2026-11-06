---
phase: 12-v2-data-client-screens
reviewed: 2026-11-06T00:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - .env.example
  - .gitignore
  - README.md
  - battery_cache.py
  - config.py
  - fetch_schedule.py
  - fetcher.py
  - main.py
  - models.py
  - screens/consumption.py
  - screens/production.py
  - solaredge_api.py
  - tests/test_battery_cache.py
  - tests/test_config.py
  - tests/test_fetch_schedule.py
  - tests/test_fetcher.py
  - tests/test_main_login_state.py
  - tests/test_main_loop.py
  - tests/test_screens_v2.py
  - tests/test_solaredge_api.py
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 12: Code Review Report

**Depth:** standard. Source files were read in full. Test files were not reviewed line by line, and the CONVENTION rule packs were not run.

## Summary

The V2 client is carefully built. Logging is clean: only path templates and status codes are logged, with no site id, serials or tokens. Retries are tightly limited, so the credit budget is protected. I found no security issues. The main problems are a display state bug after the sleep window, a fragile stateOfEnergy scaling, and some fake-zero values shown as real readings.

## Warnings

### WR-01: Error screen is never redrawn after the sleep window, so the display stays blank
**File:** `main.py:204-209` (with `main.py:323-336`)
**Issue:** The error screen is rendered only when `consecutive_failures == MAX_FAILURES`. The sleep branch calls `display.clear()` at 20:00 but does not reset `consecutive_failures`. After the 07:00 wake, `run_iteration` returns False while `consecutive_failures >= MAX_FAILURES`, so no screen is drawn. If the wake poll fails again, the counter goes to 4 and the `==` check never fires. The display then stays blank all day, and there is no indication of the error.
**Fix:** Track `error_screen_shown` in `LoopState`. Reset it on wake and on success, and render when `consecutive_failures >= MAX_FAILURES and not error_screen_shown`. Alternatively, reset `consecutive_failures` to 0 on wake. That costs at most 3 extra failed polls.

### WR-02: stateOfEnergy is unconditionally multiplied by 100 and then clamped
**File:** `solaredge_api.py:223-227`
**Issue:** The 0..1 fraction was probed on a single live sample. If the API ever returns percent values (a firmware or API change, or a different battery model), a SoC of 11.1 becomes 1110 and is clamped to 100%. The result is a confidently wrong "100%". The clamp hides the problem.
**Fix:** Log a warning when the raw value is greater than 1.0 and a response unit is available. Or treat values greater than 1.0 as already being percent: `pct = v * 100 if v <= 1.0 else v`. Note that this guess is ambiguous for a real 1% SoC, so check the `unit` field if the response provides one.

### WR-03: A missing stateOfEnergy metric is reported as 0% charge
**File:** `solaredge_api.py:215, 237-241`
**Issue:** `_metric_last` returns 0.0 for a missing or all-null metric, and that 0.0 is averaged into the SoC. A telemetry response with null SoC (common right after a gap or at API hiccups) shows "0 %" and a "success". It also overwrites the last good cached battery value. The same applies to chargePower and dischargePower, which gives a fake "Idle". The docstring documents this, but it is misleading on an energy display.
**Fix:** For SoC, skip batteries whose value is None. If no SoC is available, return None so the stale cache is kept.

### WR-04: Battery presence is cached permanently from a single detection result
**File:** `main.py:178-188`, `solaredge_api.py:189-191`, `battery_cache.py`
**Issue:** `detect_battery` returns False for an empty list or for a battery that is temporarily `active != True`. That False is persisted and `battery_known` becomes True, so detection is never retried. The battery screen disappears until someone deletes `.battery.json`. Nothing in the UI hints at this, and the file is only documented in the module docstring.
**Fix:** Cache only a True result permanently. Cache a False result with a timestamp so it expires, for example after 7 days. Alternatively, keep re-detecting a False result at a low rate, since the `devices_retry_after` setting of 6 hours is already available.

### WR-05: Today's history bucket is overwritten with overview consumption, which may differ from the meter-based consumption
**File:** `fetcher.py:48-49, 112-115`
**Issue:** History consumption comes from the sum of `consumptionEnergy` over meters. Today's bar is replaced with `overview.consumption.total`. The two sources are not guaranteed to be equal. If meters or the overview report different totals, the last bar will visibly jump when the next history refresh replaces the patched value. The patch also shifts the date axis to `now.date()`. If the history is stale and today is not in it, the older entries move left and a zero-filled today bar is overwritten. That is correct, but the dropped oldest day is lost for good until the next successful history fetch.
**Fix:** Confirm the sources agree against live data. If they do not, use a consistent source for today's bar, or document the discrepancy in the context file.

## Info

### IN-01: Temperature 0.0 is returned for an all-null series
**File:** `solaredge_api.py:259-260`
**Issue:** An all-null internalTemperature series yields a "successful" 0.0 °C, which is shown on the battery screen and cached. It also marks the temperature slot as succeeded, so there is no retry that day.
**Fix:** Return None, so the slot retries and the screen can show a dash.

### IN-02: Power unit is assumed to be W and ignored
**File:** `solaredge_api.py:216-217, 231`
**Issue:** Energy honours its `unit` field, but chargePower and dischargePower are assumed to be W. The idle threshold (50 W) is also hard-coded.
**Fix:** Read the `unit` field and convert, or assert W.

### IN-03: Inconsistent timezones
**File:** `main.py:80` (Europe/Berlin), `solaredge_api.py:28` (Europe/Zurich), `fetch_schedule.py`
**Issue:** The sleep window uses Berlin time and the fetch slots use Zurich time. They are equal today, but the split is accidental.
**Fix:** Use `SITE_TZ` in `is_sleep_time`.

### IN-04: Partial site id is written to the log
**File:** `config.py:161-165`
**Issue:** The last 4 characters of the site id and client id are logged. The project rule is that the site id must never be logged. This is a masked, partial value and matches the earlier masking convention, but it is still a deviation.
**Fix:** Log only "set" or "from token file".

---

_Reviewed: 2026-11-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
