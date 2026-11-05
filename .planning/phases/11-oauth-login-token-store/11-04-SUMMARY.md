---
phase: 11-oauth-login-token-store
plan: 04
subsystem: auth
tags: [oauth, main-loop, login-state]
requires: [11-01, 11-03]
provides: [login-needed state in main.py, lazy site init, per-poll token refresh]
affects: [main.py]
key-files:
  modified: [main.py]
  created: [tests/test_main_login_state.py]
requirements-completed: [AUTH-03, AUTH-04]
completed: 2026-11-05
---

# Phase 11 Plan 04: Login state in main loop Summary

main.py now starts without a token, shows only "Login nötig" (rendered once, no calls, no data rotation), watches token file and .env every 60 s to resume automatically, and refreshes the token on each daytime poll.

## Commits
- f8343b9: feat(11-04) main.py login state, init_site_clients, token refresh/grant warning per poll
- test commit: tests/test_main_login_state.py (3 subprocess smoke tests)

## Behavior
- Startup: `token_store.load()`; LoginRequired enters login state ("Login required: <reason>").
- Login branch sits after the sleep-window block and `continue`s before polling; re-renders only after wake from sleep.
- Poll: `get_access_token()`; LoginRequired (incl. refresh rejected) enters login state, bypassing the failure counter; TransientAuthError logs and continues.
- API client, battery detection and screens are created lazily via `init_site_clients` from the token's site_id; a differing SOLAREDGE_SITE_ID is warned once.
- solaredge_api.py untouched (Phase 12).

## Deviations from Plan
- [Rule 3] Worktree base was wrong (5ba5192); reset to 8a06eee per the base-correction step so plan and wave 1 files existed.
- Smoke tests were run with the in-process env dict (no `env -i`); not needed.

## Verification
Full suite: 55 tests OK (52 existing + 3 new). `/usr/bin/python3` login-script test not separately run; it is included in the uv discover run.

## Known Stubs
None.

## Self-Check: PASSED
