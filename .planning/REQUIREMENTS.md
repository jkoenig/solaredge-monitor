# Requirements: SolarEdge Off-Grid Monitor

**Defined:** 2026-02-12
**Core Value:** Show the homeowner their solar energy state at a glance on a physical e-ink display that's always up to date.

## v1.2 Requirements

Requirements for v1.2 Forecast Fix. Each maps to roadmap phases.

### API

- [ ] **API-01**: Forecast.Solar API response parsed correctly — fix KeyError on `watt_hours_day` by reading `data["result"]` directly (endpoint `/estimate/watthours/day/` returns flat date→Wh mapping, not nested under `watt_hours_day` key)

### Display

- [ ] **DISP-01**: Forecast screen uses identical layout grid as production/consumption screens — same margins, font sizes, spacing, bar rendering approach, and bottom breakdown positioning
- [ ] **DISP-02**: Forecast screen verified via debug PNG output matching visual style of other screens — consistent sharpness, whitespace, and typography

## Future Requirements

None for this milestone.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Hourly forecast breakdown | Keep screen simple, daily totals only (carried from v1.1) |
| Forecast accuracy tracking | Not needed — simple display, not analytics |
| Multiple forecast providers | Forecast.Solar sufficient for this use case |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| API-01 | — | Pending |
| DISP-01 | — | Pending |
| DISP-02 | — | Pending |

**Coverage:**
- v1.2 requirements: 3 total
- Mapped to phases: 0
- Unmapped: 3 ⚠️

---
*Requirements defined: 2026-02-12*
*Last updated: 2026-02-12 after initial definition*
