---
phase: 12-v2-data-client-screens
plan: 05
subsystem: main-loop
tags: [v2, fetcher, battery-cache, rotation]
requires: [12-03, 12-04]
provides:
  - "main.py V2 wiring: LoopState, run_iteration, init_site_clients with battery cache"
affects: [12-06]
key-files:
  modified: [main.py, tests/test_main_login_state.py]
  created: [tests/test_main_loop.py]
decisions:
  - "run_iteration polls only when next_poll is due and FetchPlan.due is non-empty; rotation always runs afterwards on cached values"
  - "Error screen is rendered once, when consecutive_failures reaches 3; rotation then stops until an overview succeeds"
metrics:
  tests_before: 165
  tests_after: 173
  completed: 2026-11-05
---

# Phase 12 Plan 05: Main loop V2 wiring Summary

main.py now builds SolarEdgeAPI(token_store), fills the DataCache via fetch_round on the FetchPlan cadence, reads battery presence from the disk cache, and rotates cached screens between polls without any API call.

## Tasks

1. Rewrite poll/rotation (commit 13dc80b): V1 `fetch_data` removed; `init_site_clients` makes no API call; `LoopState` dataclass; `run_iteration` (token pre-check + fetch_round only when due and not in backoff, battery detection saved to cache and screens rebuilt, error screen at 3 failures, LoginRequired propagates to the existing login state). Removed `SOLAREDGE_API_KEY` from the login smoke test env. New tests/test_main_loop.py with 8 tests covering every behavior bullet.
2. V1 removal gate: the grep gate over tracked and untracked app code and docs (outside lib/, tests/, .planning/) found nothing; no further changes needed. Full suite: 173 tests, OK (before: 165 at plan start; the plan text mentioned 56, which was outdated).

## Deviations from Plan

None in behavior. Notes: the worktree base had to be reset to the expected commit at start (HEAD was behind). On a site-id change the new LoopState keeps the pending next_poll instead of polling immediately. Wake from sleep and login recovery also update state.next_poll.

## Known Stubs

None.

## Self-Check: PASSED
