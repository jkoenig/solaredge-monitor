---
phase: 11-oauth-login-token-store
plan: 05
subsystem: auth
tags: [oauth, deploy, live-verification]
requires: [11-02, 11-04]
provides: [live token chain on se-monitor]
key-files:
  created: []
  modified: [scripts/solaredge_login.py, tests/test_login_script.py]
key-decisions:
  - "1Password item lives in the personal account (my.1password.com); login script gets --op-account with that default"
requirements-completed: [AUTH-01, AUTH-02, AUTH-03, AUTH-04]
completed: 2026-11-05
---

# Phase 11 Plan 05: Live login on se-monitor — Summary

Phase 11 deployed to se-monitor, real OAuth login run from the Mac, token chain now held by the Pi.

## Task results

1. **Deploy + "Login nötig"**: Local suite green (55 + 28). Pushed 26 commits, `./deploy.sh` on se-monitor. Journal: `Login required: token file missing`, no Traceback; service `active`, `NRestarts=0`.
2. **Real login**: First run failed: `op` used the default (work) account and reported the item "isn't an item". Fix `ec605c0` adds `--op-account` (default `my.1password.com`) plus a test. Second run: browser consent OK ("Login erfolgreich"), site ...9764, access token valid until 15:54, grant ~24 months.
3. **Read-only checks** (no values printed):
   - `.tokens.json` mode/owner `600 pi`; keys: access_token, expires_at, granted_at, obtained_at, refresh_token, site_id, token_type, version
   - Pi `.env`: exactly 1 each of SOLAREDGE_CLIENT_ID, SOLAREDGE_CLIENT_SECRET, SOLAREDGE_API_KEY
   - No `.tokens.json.upload` leftover; no `.tokens.json` or `solaredge-login-*` temp dir on the Mac
   - Journal 13:54:40 "Token file or .env changed, re-checking login" → "Login OK, resuming" (6 s after upload), `NRestarts=0`, service active

## Observations / open questions

- **`state` echo (research open question 2):** the script tolerates both; it does not log which case occurred, so this remains unconfirmed.
- **Token exchange:** JSON body accepted on first try; `expires_in` gave ~2 h.
- After resume the V1 calls return HTTP 410 (inventory, energyDetails, currentPowerFlow) → display goes to "Fehler" after 3 failures. Expected until Phase 12.
- Battery detection ran against V1 and returned False (410) — Phase 12 replaces this with `/devices?types=BATTERY` + disk cache.
- V1 error log lines contain the full site id in the URL path (pre-existing V1 code, removed in Phase 12).
- The systemd unit is `disabled` (not started at boot). Relevant for Phase 14 (OPS-01).
- First real refresh expected in the journal as "Access token refreshed" ~2 h after login (AUTH-03 on-device confirmation).

## Deviations

- [Rule 1 - Bug] 1Password account selection: added `--op-account` (commit `ec605c0`).

## Self-Check: PASSED
