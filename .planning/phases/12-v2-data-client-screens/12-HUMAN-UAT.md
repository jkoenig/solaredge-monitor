---
status: partial
phase: 12-v2-data-client-screens
source: [12-VERIFICATION.md]
started: 2026-11-06T08:15:00+01:00
updated: 2026-11-06T08:15:00+01:00
---

## Current Test

[awaiting human testing]

## Tests

### 1. Steady-state call count on se-monitor
expected: At least 70 min after the last restart (08:05 on 2026-11-06), during daytime, `ssh se-monitor 'journalctl -u solaredge-monitor --since "-60 min" --no-pager -o cat | grep -c "API /sites"'` prints <= 4.
result: [pending]

### 2. Physical panel rotation
expected: The owner watches the e-ink panel for a few minutes: screens rotate (about 1 min each) between 30-min polls, Hausakku shows ~SoC % (not 0 %), values match the rendered preview approved on 2026-11-06.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
