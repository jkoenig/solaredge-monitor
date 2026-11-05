---
phase: 12-v2-data-client-screens
plan: 03
subsystem: data-client
tags: [solaredge-v2, api-client, token-store]
requires: [12-01]
provides:
  - "SolarEdgeAPI(token_store) V2 client: get_overview, get_battery_telemetry, get_storage_temperature, detect_battery, get_energy_history"
  - "Helpers: SITE_TZ, IDLE_THRESHOLD_W, to_kwh, last_non_null, derive_battery_status"
affects: [12-04, 12-05]
tech-stack:
  added: []
  patterns: [return-None-on-failure, injected sleep and clock, path templates in logs]
key-files:
  created: [tests/test_solaredge_api.py]
  modified: [solaredge_api.py, models.py]
key-decisions:
  - "Constructor is SolarEdgeAPI(token_store, sleep=time.sleep, now_fn=None); now_fn optional so the 12-04/12-05 contract is unchanged"
  - "get_energy_history skips the /meters/telemetry call when /energy fails (saves a credit)"
  - "429 log includes x-ratelimit-remaining-minute"
requirements-completed: [API-01, API-02, API-03, API-04, API-05]
duration: 25min
completed: 2026-11-05
---

# Phase 12 Plan 03: V2 SolarEdge client Summary

V2 client on TokenStore with one-retry-only-for-overview policy, null-as-0 unit-converting parsers for overview, storage telemetry/status, battery detection and a 14-day history.

## Task Commits
1. V2 transport, overview, battery detection: 76f7796
2. Storage telemetry and status: abee712
3. 14-day history, V1 models removed: 6d42f5e

## Accomplishments
- Only `get_overview(retry=True)` retries (once, 2 s sleep, 5xx/timeout); every other job makes one attempt; 400/403/404/429 never retried; LoginRequired propagates; TransientAuthError gives None.
- Logs use `{site_id}` path templates only; hygiene test asserts the fake site id and serial never appear.
- Battery: SoC/power/status/remainingEnergy from `/storage/telemetry` (last non-null, 1 h window), temperature from `/storage/status` (2 h window); 50 W idle threshold with strict comparisons.
- History: production from `/energy`, consumption summed over every meter with `consumptionEnergy`, bucketed by timestamp[:10]; DST-spanning fixtures pass.
- `PowerFlow` and `SiteOverview` removed from models.py. 41 new tests; full suite 135 tests green.

## Deviations from Plan
- Worktree HEAD was behind the expected base (ec605c0); reset to 46b2819 per the startup check, no work lost.
- ROADMAP success criterion 4 names `/meters/telemetry` for both history screens; per D-10 (live probe) production comes from `/energy` because this site's meters response has no productionEnergy.
- Today's bar patch (D-06) is intentionally left to 12-04 (`patch_history_today`).

## Known Stubs
None.

## Notes for 12-05
main.py still references removed names (PowerFlow-based fetch, old constructor); expected until 12-05 rewires it.

## Self-Check: PASSED
