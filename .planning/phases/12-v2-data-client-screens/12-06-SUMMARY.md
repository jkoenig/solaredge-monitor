---
phase: 12-v2-data-client-screens
plan: 06
subsystem: deploy
tags: [deploy, live-verification, v2]
requires: [12-05]
provides: [V2 data on se-monitor]
key-files:
  created: []
  modified: [solaredge_api.py, tests/test_solaredge_api.py]
key-decisions:
  - "Pi .env sleep window set to 20-07 and poll 30 min (owner approved) to keep the interim budget"
  - "V2 stateOfEnergy (unit PERCENTAGE) is a 0..1 fraction on the live API; scaled to %"
requirements-completed: [API-01, API-02, API-03, API-04, API-05]
completed: 2026-11-06
---

# Phase 12 Plan 06: Live deploy on se-monitor — Summary

Phase 12 deployed to se-monitor 2026-11-05 20:00; display shows V2 values; owner approved the screens on 2026-11-06.

## Task results

1. **Go-ahead:** local suite 173 + 29 (login script, system python) green; V1 gate clean; owner chose deploy now at 19:59.
2. **Deploy + checks:**
   - Push + `./deploy.sh` 20:00:27. Service active, NRestarts=0, no Traceback.
   - First round (no cache): devices 1 + overview + storage/status + storage/telemetry + energy + meters/telemetry = 6 calls, all 200. "Battery detection: 1 active of 2", "History fetched: 14 days", "Poll successful".
   - `.battery.json`: `600 pi`, keys [has_battery, site_hash, version], has_battery True. Site-id occurrences in the journal since deploy: 0.
   - Finding: the Pi `.env` had overrides (poll interval < 30, sleep 01-06 = 19 h awake, ~75 calls/day). Owner approved setting `SOLAREDGE_POLL_INTERVAL=30`, `SOLAREDGE_SLEEP_START=20`, `SOLAREDGE_SLEEP_END=7` (backup `.env.bak-phase12`). Restart 20:02:30 went straight to sleep.
   - Restart check (API-03): wake 2026-11-06 07:00 logged "Battery presence from cache: True" and no `/devices` call since 20:02.
3. **Owner check (remote):** owner was away, so the eight screens were rendered once on the Pi from a fresh fetch (~5 calls) and shown as a private page. Owner approved.
   - Found and fixed: Hausakku showed 0 % at ~11 %. Live `stateOfEnergy` values are fractions (0.111 with 983 Wh of a 9.2 kWh nameplate). Fix `fix(12-06): scale V2 stateOfEnergy fraction to percent` + 2 tests (175 green), deployed ~08:05.
   - Rotation keeps running between polls (journal shows polls at 07:00, 07:35, 08:01 with the service active in between; owner did not watch the panel itself).

## Observations

- Token refresh on device continues to work overnight ("Access token refreshed").
- Open question 6 (toGrid/fromGrid vs app): not compared in detail; morning values feed-in 0.0 / purchased 7.8 of 7.8 kWh consumption are plausible.
- During the sleep window the display is cleared (existing behaviour); with 20-07 it is blank in the evening. Candidate for Phase 13.
- Steady-state call count: see VERIFICATION (measured >= 70 min after the 08:05 restart).

## Deviations

- [Rule 1 - Bug] stateOfEnergy fraction (commit "fix(12-06): scale V2 stateOfEnergy fraction to percent").
- [Rule 3 - Config] Pi `.env` sleep/poll overrides changed with owner approval (not a code change).

## Self-Check: PASSED
