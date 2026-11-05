---
phase: 12-v2-data-client-screens
plan: 04
subsystem: fetch-orchestration
tags: [fetcher, config, budget, D-06, D-07]
requires: [12-01, 12-02]
provides: [fetcher.DataCache, fetcher.RoundResult, fetcher.fetch_round, fetcher.patch_history_today, fetcher.build_cycle, Config.battery_cache_file]
affects: [main.py (12-05)]
key-files:
  created: [fetcher.py, tests/test_fetcher.py, tests/test_config.py]
  modified: [config.py, .env.example, README.md]
decisions:
  - "Poll interval floor MIN_POLL_INTERVAL = 30 with warning instead of an error"
  - "Awake window > 13 h logs a startup warning (MAX_AWAKE_HOURS)"
metrics:
  tasks: 2
  completed: 2026-11-05
---

# Phase 12 Plan 04: Fetch round and V2 config Summary

One budget-aware fetch round (FetchPlan-driven, last-good DataCache, today-bar patch) plus V2-only config with budget-safe defaults and no API key.

## Commits
- 9dc6974: feat(12-04): fetcher.py + tests/test_fetcher.py
- Task 2 commit (config, .env.example, README, tests/test_config.py): b1fbe99

## What was built
- fetcher.py: fetch_round runs devices, overview, temperature, storage, history, forecast in that order, only for jobs the plan returns; records every attempt; overview retry only outside backoff; today's history bar patched from overview totals each round; build_cycle uses cached values so Hausakku no longer vanishes between hourly storage fetches.
- All-failure-day test: 36 API method calls, 3 overview calls with retry=True.
- config.py: api_key removed, defaults 30 / 20 / 7, poll floor, battery_cache_file, startup warnings. .env.example and README cleaned of the key and stale defaults/module names.

## Deviations from Plan
- Worktree base was behind the expected base; reset to 46b2819 as the startup check instructs.
- README: also updated SOLAREDGE_SITE_ID hint wording in the troubleshooting line; otherwise as planned.

## Known Stubs
None.

## Notes
- main.py still references config.api_key until 12-05 (expected). Full suite (116 tests) is green.

## Self-Check: PASSED
