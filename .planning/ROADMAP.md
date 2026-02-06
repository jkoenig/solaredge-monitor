# Roadmap: SolarEdge Off-Grid Monitor

## Milestones

- ✅ **v1.0 MVP** - Phases 1-6 (shipped 2026-02-07)
- 🚧 **v1.1 Forecast Screen** - Phases 7-9 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-6) - SHIPPED 2026-02-07</summary>

Initial implementation of e-ink display monitor with 7 screens showing daily SolarEdge energy data.

**Key deliverables:**
- Waveshare 2.13" e-ink display integration
- 7 screens: production, consumption, feed_in, purchased, battery (auto-detected), history_production, history_consumption
- SolarEdge API client with retry logic
- 4x supersampling rendering pipeline
- Systemd deployment on Raspberry Pi Zero WH

**Plans completed:** 13 plans (0.41 hours total, 1.8 min average)

</details>

### 🚧 v1.1 Forecast Screen (In Progress)

**Milestone Goal:** Add solar production forecast screen using Forecast.Solar API, showing today's forecast with progress bar and tomorrow's prediction.

#### Phase 7: Forecast API Integration
**Goal**: App fetches and caches forecast data from Forecast.Solar API
**Depends on**: Phase 6 (v1.0 complete)
**Requirements**: FCST-01, FCST-02, FCST-03, FCST-04, CONF-01, CONF-02
**Success Criteria** (what must be TRUE):
  1. User can configure forecast parameters (lat, lon, tilt, azimuth, kWp) in .env and app reads them
  2. App fetches today's and tomorrow's production forecasts from Forecast.Solar API when config is present
  3. Forecast data is cached for 1 hour to stay within free tier rate limits (12 req/hour)
  4. App continues to run and show other screens if Forecast.Solar API fails or rate limit is hit
  5. Forecast screen only appears in rotation when all 5 forecast .env values are configured
**Plans:** 2 plans

Plans:
- [x] 07-01-PLAN.md — Config fields, ForecastData model, .env.example
- [x] 07-02-PLAN.md — Forecast.Solar API client with TTL cache, main loop wiring

#### Phase 8: Forecast Screen
**Goal**: Display shows "Prognose, heute" screen with forecast value, progress bar, and tomorrow's forecast
**Depends on**: Phase 7
**Requirements**: DISP-01, DISP-02, DISP-03
**Success Criteria** (what must be TRUE):
  1. User sees "Prognose, heute" screen in rotation showing today's forecast as the main number (kWh)
  2. Progress bar shows actual production vs forecast with percentage label (e.g., "62% der Prognose erreicht")
  3. Tomorrow's forecast is displayed in bottom breakdown area (e.g., "Morgen: 8.4 kWh")
  4. Screen follows unified layout grid (MARGIN=5, headline Arial 60, value ArialBlack 120, bar 40px tall)
**Plans:** 1 plan

Plans:
- [ ] 08-01-PLAN.md — Forecast screen renderer with model wiring and screen registration

#### Phase 9: Documentation
**Goal**: Documentation reflects new forecast screen configuration and usage
**Depends on**: Phase 8
**Requirements**: DOCS-01, DOCS-02
**Success Criteria** (what must be TRUE):
  1. User can see forecast configuration instructions in README with all 5 required .env variables
  2. User can copy forecast environment variables from .env.example as a template
  3. README includes screenshot of "Prognose, heute" screen showing how forecast appears
**Plans**: TBD

Plans: (TBD)

## Progress

**Execution Order:**
Phases execute in numeric order: 7 → 8 → 9

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-6. MVP | v1.0 | 13/13 | Complete | 2026-02-07 |
| 7. Forecast API Integration | v1.1 | 2/2 | Complete | 2026-02-07 |
| 8. Forecast Screen | v1.1 | 0/1 | Not started | - |
| 9. Documentation | v1.1 | 0/TBD | Not started | - |

---

*Roadmap created: 2026-02-07*
*Last updated: 2026-02-07 (Phase 7 complete)*
