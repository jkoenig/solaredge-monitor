---
phase: 11-oauth-login-token-store
plan: 01
subsystem: auth
tags: [oauth2, token-store, flock, atomic-write, requests]
requires: []
provides:
  - token_store module (TokenData, TokenStore, TokenFileWatcher, LoginRequired, TransientAuthError)
affects: [11-02, 11-04, phase-12]
tech-stack:
  added: []
  patterns: [persist-before-use, tmp+fsync+os.replace under fcntl.flock]
key-files:
  created: [token_store.py, tests/test_token_store.py]
  modified: []
key-decisions:
  - "Both tasks were committed together in one feat commit (single module, tests written alongside)"
  - "Transient refresh failure with still-valid token returns old token; force_refresh never does"
requirements-completed: [AUTH-03, AUTH-04]
duration: 15min
completed: 2026-11-05
---

# Phase 11 Plan 01: Token Store Summary

Pi-side OAuth token store: validated token file, atomic 0600 persistence under flock, refresh with rotated refresh token persisted before use, LoginRequired/TransientAuthError signals, bearer `authorized_request` (refresh once, retry once), file watcher and 24-month grant warning.

## Tasks
1. Token file layer (schema, load, atomic locked save, watcher): commit 6e2790a
2. Refresh, persist-before-use, authorized request, grant warning: commit 6e2790a

24 stdlib unittest tests pass (`uv run --no-project --python 3.11 --with-requirements requirements.txt python -m unittest discover -s tests -p 'test_token_store.py'`). Acceptance greps (no Retry, no data= on post, no secrets in log calls, no oauthlib) pass.

## Deviations from Plan

- **Worktree base correction:** worktree started at 5ba5192 and was reset to the required base e2edb84 per the branch check. No code impact.
- Tasks 1 and 2 share one commit rather than two, and no separate RED commit was made; tests and implementation were developed together.
- A test-visible bug (retry reused and mutated the same headers dict) was fixed during development.

## Known Stubs
None.

## Threat Flags
None.

## Self-Check: PASSED
