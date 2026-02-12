# Roadmap: SolarEdge Off-Grid Monitor

## Milestones

- ✅ **v1.0 MVP** — Phases 1-6 (shipped 2026-02-07)
- ✅ **v1.1 Forecast Screen** — Phases 7-9 (shipped 2026-02-11)
- 🚧 **v1.2 Forecast Fix** — Phase 10 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-6) — SHIPPED 2026-02-07</summary>

- [x] Phase 1: Cleanup & Fresh Repository (2/2 plans) — completed 2026-02-05
- [x] Phase 2: Configuration Foundation (1/1 plan) — completed 2026-02-05
- [x] Phase 3: Architecture & Data Layer (3/3 plans) — completed 2026-02-05
- [x] Phase 4: Display Layer (3/3 plans) — completed 2026-02-06
- [x] Phase 5: Operations (2/2 plans) — completed 2026-02-06
- [x] Phase 6: Deployment (2/2 plans) — completed 2026-02-06

</details>

<details>
<summary>✅ v1.1 Forecast Screen (Phases 7-9) — SHIPPED 2026-02-11</summary>

- [x] Phase 7: Forecast API Integration (2/2 plans) — completed 2026-02-07
- [x] Phase 8: Forecast Screen (1/1 plan) — completed 2026-02-07
- [x] Phase 9: Documentation (1/1 plan) — completed 2026-02-11

</details>

## 🚧 v1.2 Forecast Fix (In Progress)

**Milestone Goal:** Fix broken Forecast.Solar API parsing and align forecast screen visual style with all other screens.

### Phase 10: Forecast Fix
**Goal**: Forecast screen works correctly and visually matches other screens
**Depends on**: Phase 9
**Requirements**: API-01, DISP-01, DISP-02
**Success Criteria** (what must be TRUE):
  1. Forecast.Solar API response parses without KeyError (reads `data["result"]` directly instead of looking for nested 'watt_hours_day' key)
  2. Forecast screen uses identical layout grid as production/consumption screens (MARGIN=5, same font sizes, value+bar vertical centering, breakdown at CANVAS_H-MARGIN-110)
  3. Debug PNG output shows forecast screen with consistent visual style matching production/consumption screens (same whitespace, typography, alignment)
**Plans**: 1 plan

Plans:
- [ ] 10-01-PLAN.md — Fix API parsing and align forecast screen layout

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-6. MVP | v1.0 | 13/13 | Complete | 2026-02-07 |
| 7. Forecast API Integration | v1.1 | 2/2 | Complete | 2026-02-07 |
| 8. Forecast Screen | v1.1 | 1/1 | Complete | 2026-02-07 |
| 9. Documentation | v1.1 | 1/1 | Complete | 2026-02-11 |
| 10. Forecast Fix | v1.2 | 0/1 | Not started | - |

---

*Roadmap created: 2026-02-07*
*Last updated: 2026-02-12 (v1.2 roadmap created)*
