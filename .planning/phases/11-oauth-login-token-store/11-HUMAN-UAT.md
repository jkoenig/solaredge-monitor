---
status: partial
phase: 11-oauth-login-token-store
source: [11-VERIFICATION.md]
started: 2026-11-05T14:05:00+01:00
updated: 2026-11-05T14:05:00+01:00
---

## Current Test

[awaiting human testing]

## Tests

### 1. First real token refresh on se-monitor
expected: About 2 h after login (~15:54 on 2026-11-05) the journal shows "Access token refreshed"; `.tokens.json` stays `600 pi`; the service does not fall back to "Login nötig". Check: `ssh se-monitor 'journalctl -u solaredge-monitor --since today --no-pager -o cat | grep -E "Access token refreshed|Login required"; stat -c "%a %U" /home/pi/solaredge-monitor/.tokens.json'`
result: [pending]

### 2. "Login nötig" on the physical e-ink panel
expected: With no token file the panel shows "Login nötig" top-left and "Mac: login-Skript starten" centered, nothing else. (Software state confirmed in the journal 13:41; panel not yet seen by the owner. Can be checked at the next re-login, or by temporarily renaming .tokens.json — that does not burn the token.)
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
