---
phase: 12
fixed_at: 2026-11-06T00:00:00Z
review_path: .planning/phases/12-v2-data-client-screens/12-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 12: Code Review Fix Report

**Fixed at:** 2026-11-06
**Source review:** .planning/phases/12-v2-data-client-screens/12-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5
- Fixed: 5
- Skipped: 0

Tests: 185 passing (175 before).

## Fixed Issues

### WR-01: Error screen never redrawn after sleep window

**Files modified:** `main.py`, `tests/test_main_loop.py`
**Commit:** f6c14a3
**Applied fix:** Added `LoopState.error_screen_shown`. The error screen renders when failures >= 3 and it is not shown. The flag is reset on success, on wake from sleep and on login resume. Added a test (fixed: requires human verification, since it is state logic).

### WR-02: stateOfEnergy always multiplied by 100

**Files modified:** `solaredge_api.py`, `tests/test_solaredge_api.py`
**Commit:** 49b9e96
**Applied fix:** Values <= 1.0 are scaled as fractions, values > 1.0 are used as percent. A raw 1.0 is read as 100 %. Tests cover both forms.

### WR-03: Missing stateOfEnergy reported as 0%

**Files modified:** `solaredge_api.py`, `tests/test_solaredge_api.py`
**Commit:** d2e88ba
**Applied fix:** Batteries with a null or missing SoC are skipped. If none remain, `get_battery_telemetry` returns None, so the cached BatteryData stays. Power and energy metrics still default to 0. Added a test.

### WR-04: Battery presence cached permanently

**Files modified:** `battery_cache.py`, `main.py`, `tests/test_battery_cache.py`, `tests/test_main_loop.py`
**Commit:** c57a0bc
**Applied fix:** The cache file now stores `checked_at`. A cached False expires after 7 days, and a False without a timestamp (old format) counts as expired. True never expires. Expiry is applied at load and also at runtime in `run_iteration`, which re-enables the DEVICES job (at most one extra /devices call per 7 days). `init_site_clients` now returns a fifth value, `checked_at`. Added tests.

### WR-05: Today's bar source mismatch

**Files modified:** `fetcher.py`
**Commit:** 6ce3f0f
**Applied fix:** No same-source consumption is available without extra API calls, so the small mismatch is documented in the `patch_history_today` docstring as an accepted limitation.

---

_Fixed: 2026-11-06_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
