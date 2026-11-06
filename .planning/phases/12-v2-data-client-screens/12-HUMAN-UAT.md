---
status: partial
phase: 12-v2-data-client-screens
source: [12-VERIFICATION.md]
started: 2026-11-06T08:15:00+01:00
updated: 2026-11-06T16:35:00+01:00
---

## Current Test

[awaiting human testing]

## Tests

### 1. Steady-state call count on se-monitor
expected: At least 70 min after the last restart (08:05 on 2026-11-06), during daytime, `ssh se-monitor 'journalctl -u solaredge-monitor --since "-60 min" --no-pager -o cat | grep -c "API /sites"'` prints <= 4.
result: passed — journal of the 08:05–16:30 run, per clock hour 09–15: 3,3,3,4,3,3,3 calls (4 = temperature slot at 12:00); 0 non-200, 0 Traceback. Review-fix deploy at 16:30 restarted with 5 calls (battery cache hit, no /devices).

### 2. Physical panel rotation
expected: The owner watches the e-ink panel for a few minutes: screens rotate (about 1 min each) between 30-min polls, Hausakku shows ~SoC % (not 0 %), values match the rendered preview approved on 2026-11-06.
result: [pending]

## Summary

total: 2
passed: 1
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
