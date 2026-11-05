---
phase: 11-oauth-login-token-store
verified: 2026-11-05T13:58:00Z
status: passed
score: 4/4 must-haves verified
has_blocking_gaps: false
overrides_applied: 0
human_verification:
  - test: "First on-device token refresh"
    expected: "Journal on se-monitor shows 'Access token refreshed' about 2 h after login (~15:54) and .tokens.json stays 600 and readable"
    why_human: "Not yet occurred at verification time (13:57); the refresh path is covered by unit tests in tests/test_token_store.py"
  - test: "Physical display shows 'Login nötig'"
    expected: "E-ink shows headline 'Login nötig' and hint 'Mac: login-Skript starten' when the token file is missing"
    why_human: "The owner did not visually confirm the e-ink panel; the renderer and its tests exist"
---

# Phase 11: OAuth Login & Token Store Verification Report

**Phase Goal:** Owner logs in once from the Mac; the Pi then holds a valid token chain on its own or clearly says it needs a new login.
**Status:** human_needed (all automated and live checks pass; two items remain for a human or later follow-up)

## Observable Truths

| # | Truth (ROADMAP SC) | Status | Evidence |
|---|---|---|---|
| 1 | Login script opens consent page, catches the callback on :8765 (with or without state), exchanges the code, reads client ID/secret via `op` | VERIFIED | `scripts/solaredge_login.py` exists with the callback server, state validated only if present, and `op` calls. The login test suite passes (OK, 1 skipped). 11-05 live run completed a real login. |
| 2 | Token file on se-monitor is 0600 and the Mac keeps no refreshing copy | VERIFIED | Live read-only check on se-monitor: `.tokens.json` is `600 pi`. 11-05 recorded no Mac copy or temp dir, and no upload leftover on the Pi. |
| 3 | Refresh persists the rotated token (tmp + fsync + rename, flock) before use | VERIFIED (code and tests) / live refresh pending | `token_store.py` has fsync (l.172), `os.replace` (l.175), directory fsync (l.183) and `flock` (l.193). The 56-test suite passes. The first real refresh is not due until ~15:54. |
| 4 | Missing, corrupt or rejected token shows "Login nötig", the service stays up and resumes by itself | VERIFIED | `LoginRequired` is raised for missing, corrupt and 400/401 cases (token_store.py l.150-256). `screens/error.py` has the "Login nötig" screen. Live: the journal shows "Login required: token file missing", then "Login OK, resuming" 6 s after upload, with NRestarts=0. |

**Score:** 4/4 (SC3 live confirmation outstanding, see human items)

## Requirements Coverage

| Req | Plans | Status | Evidence |
|---|---|---|---|
| AUTH-01 | 11-02, 11-05 | SATISFIED | Login script, live login succeeded |
| AUTH-02 | 11-02, 11-05 | SATISFIED | Mode 600 on the Pi, no Mac copy |
| AUTH-03 | 11-01, 11-04, 11-05 | SATISFIED in code and tests; live refresh pending | token_store.py, tests |
| AUTH-04 | 11-01, 11-03, 11-04, 11-05 | SATISFIED | Login screen, main.py state, live resume |

No orphaned requirements: all four IDs appear in PLAN frontmatter. Note that REQUIREMENTS.md still shows `[ ]` and "Pending" for AUTH-01..04, so the orchestrator should tick them.

## Tests

- Full suite (uv, Python 3.11): OK.
- `/usr/bin/python3` login script tests: OK (skipped=1).

## Anti-Patterns

No TBD/FIXME/XXX markers in phase files.

## Code Review Warnings (0 critical, 4 warnings)

None blocks the phase goal. They are robustness items for follow-up (backlog):
- WR-01: the callback listener can hang on an idle preconnect socket. The fix is a handler `timeout`. This is the most likely to annoy during a re-login, but the live login worked.
- WR-02: a callback without `state` is accepted, and a stray `/callback` request ends the wait. It follows D-02 and is a local-only risk.
- WR-03: the Mac upload `mv` does not take the Pi's flock. It is a narrow race with a refresh, and the worst case is a fresh "Login nötig".
- WR-04: a persist failure after a successful refresh loses the rotated token. It needs a disk-full or read-only filesystem, and it ends in a clean "Login nötig".

## Human Verification Required

1. First on-device refresh (~15:54): `journalctl -u solaredge-monitor | grep "Access token refreshed"`, and confirm the file is still 600 with no fall back to "Login nötig". It is a follow-up item, not a gap. The refresh path is unit-tested.
2. Physical e-ink check of the "Login nötig" screen. It was not visually confirmed by the owner.

## Gaps Summary

No gaps. Expected V1 HTTP 410 / "Fehler" after resume belongs to Phase 12. The `state`-echo question is unresolved (not logged), which is informational only.

_Verifier: Claude (gsd-verifier)_
