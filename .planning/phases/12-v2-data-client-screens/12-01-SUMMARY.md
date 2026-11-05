---
phase: 12-v2-data-client-screens
plan: 01
subsystem: screens-models
tags: [models, screens, v2-contract, tests]
requires: []
provides:
  - EnergyDetails.to_storage / from_pv / from_storage (kWh, default 0.0)
  - tests/test_screens_v2.py render tests
affects: [12-03, 12-04]
key-files:
  modified: [models.py, screens/production.py, screens/consumption.py]
  created: [tests/test_screens_v2.py]
requirements: [API-01, API-02]
completed: 2026-11-05
---

# Phase 12 Plan 01: V2 data contract and screens Summary

EnergyDetails gained direct overview breakdown fields, and Produktion/Verbrauch now show them instead of remainder derivations.

## Tasks

1. Extended EnergyDetails (to_storage, from_pv, from_storage, default 0.0) and updated model docstrings (commit d2f6ee8).
2. production.py "In Akku" uses data.to_storage; consumption.py "Von PV"/"Von Akku" use from_pv/from_storage, legend percentage uses from_pv (guarded by consumption > 0). Added tests/test_screens_v2.py (7 tests: production, consumption incl. zero, battery idle/charge/discharge, history across DST). Commit 6bf2203. Full suite: 63 tests OK.

PowerFlow and SiteOverview were left in models.py for 12-03 to remove.

## Deviations from Plan

None - plan executed as written. Layout, fonts and labels unchanged; battery.py and history.py untouched.

## Known Stubs

None.

## Self-Check: PASSED
