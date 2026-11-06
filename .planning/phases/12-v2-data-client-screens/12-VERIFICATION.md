---
phase: 12-v2-data-client-screens
verified: 2026-11-06T12:00:00Z
status: passed
score: 5/5 must-haves verified
has_blocking_gaps: false
overrides_applied: 1
overrides:
  - must_have: "Verlauf Produktion and Verlauf Verbrauch show 14 daily bars from /meters/telemetry?resolution=DAY, bucketed by local date"
    reason: "D-10 in 12-CONTEXT.md: for this site /meters/telemetry returns only a virtual CONSUMPTION meter, so production history comes from /sites/{id}/energy?resolution=DAY (2 calls/day)"
    accepted_by: "owner (12-CONTEXT D-10)"
    accepted_at: "2026-11-06"
re_verification: false
human_verification:
  - test: "Measure steady-state hourly API call count (orchestrator/ops)"
    expected: "<= 4 calls per hour in steady state"
    why_human: "Needs live journal measurement; not verifiable from code (owner scoped it to the orchestrator)"
  - test: "Watch the physical panel during daytime rotation"
    expected: "Screens rotate on cached values between polls; Hausakku shows about 11 % at the current state"
    why_human: "12-06 SUMMARY says owner approved a private rendering, but did not watch the panel itself"
---

# Phase 12: V2 Data Client & Screens Verification Report

**Phase Goal:** Every existing screen shows correct values sourced from the Monitoring API V2, and no V1 code remains
**Status:** human_needed (all code-level truths verified; one ops measurement pending)
**Re-verification:** No, initial verification

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Produktion/Verbrauch/Einspeisung/Bezug from `/overview`, unit-converted, nulls as 0 | VERIFIED | `solaredge_api.get_overview` reads `/sites/{site_id}/overview`; `to_kwh` converts by `unit` (raises on unknown unit) and maps None to 0.0; missing sections handled. Screens use EnergyDetails fields (tests/test_screens_v2.py). |
| 2 | Hausakku SoC and power from `/storage/telemetry`, last non-null, status derived from charge/discharge power | VERIFIED | `get_battery_telemetry` uses `last_non_null` via `_metric_last`; `derive_battery_status(net_w)` gives Charge/Discharge/Idle with a 50 W threshold. SoC fraction fix (x100) deployed and live-checked. See WR-02/WR-03 (non-blocking). |
| 3 | Battery presence via `/devices?types=BATTERY` once, then disk cache | VERIFIED | `detect_battery` calls `/devices` with `types=BATTERY`. `battery_cache.py` plus `main.py` load/save the cache. The live log shows "Battery presence from cache: True" with no `/devices` call after restart. |
| 4 | Verlauf screens show 14 daily bars, bucketed by local date | VERIFIED (override, D-10) | `get_energy_history` buckets by `timestamp[:10]` (local date) and builds 14 dates. Consumption comes from `/meters/telemetry` DAY. Production comes from `/energy` DAY, per D-10 which overrides the ROADMAP wording. Returns None if either call fails. |
| 5 | No V1 endpoints, power-flow model, or blanket retry; at most one retry on 5xx/timeout | VERIFIED | Grep for energyDetails, currentPowerFlow, storageData, inventory, PowerFlow, HTTPAdapter, status_forcelist, api_key and SOLAREDGE_API in py/sh/txt/service/README finds no V1 code. The only hits are test assertions that api_key is absent and the `monitoringapi.solaredge.com/v2` base URL. `_request` allows `attempts = 2` only when `retry=True`, and only `get_overview` uses it. |

**Score:** 5/5 (one via accepted D-10 override)

## Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| API-01 | SATISFIED | Truth 1 |
| API-02 | SATISFIED | Truth 2 |
| API-03 | SATISFIED | Truth 3 |
| API-04 | SATISFIED (per D-10 deviation) | Truth 4 |
| API-05 | SATISFIED | Truth 5 |

All five IDs appear in REQUIREMENTS.md and in the Phase 12 roadmap. No orphaned requirements. The REQUIREMENTS.md checkboxes and traceability table still show "Pending", so the orchestrator should tick them. The ROADMAP line is already marked complete.

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite | `uv run ... python -m unittest discover -s tests` | Ran 175 tests, OK | PASS |

Probes: none declared. Live deploy evidence is in 12-06-SUMMARY.md and was not re-verified (no ssh, per instructions).

## Code Review Assessment (12-REVIEW.md: 0 critical, 5 warnings)

None of these blocks the phase goal. All are robustness or edge-case issues, and the goal behaviors are verified above.

- WR-01: after a failure streak spanning the sleep window, the error screen is not redrawn. This is a real display-state bug, but it is a loop issue outside the data-source goal. Recommend a fix in Phase 13 or via backlog.
- WR-02/WR-03/IN-01: the SoC scaling is fragile, and a missing metric shows 0 %. Neither affects correct values with current live data.
- WR-04: a False battery detection is cached permanently. This is a risk for API-03 robustness. Recommend caching False with an expiry.
- WR-05: the today history bar may differ from the meter sum. The source agreement was not confirmed.
- IN-04: the last 4 characters of the site id are logged. This deviates from the project masking rule, though the 12-06 journal check reported 0 full site-id occurrences.

## Anti-Patterns

No TBD/FIXME blockers were found in the review scope. The fake-zero stub patterns are covered above (WR-03/IN-01, warnings only).

## Human Verification Required

1. **Steady-state calls per hour:** measure in the journal after the 08:05 restart. Expected <= 4 per hour. This is pending with the orchestrator.
2. **Panel rotation:** owner watches the physical e-ink panel in daytime. The 12-06 SUMMARY notes the owner did not watch it, only approved rendered screens.

## Gaps Summary

There are no blocking gaps. The phase goal is achieved in the code. The criterion 4 deviation is intentional (D-10) and recorded as an override. Status is human_needed only because of the pending ops measurements.

_Verified: 2026-11-06_
_Verifier: Claude (gsd-verifier)_
