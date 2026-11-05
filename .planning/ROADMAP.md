# Roadmap: SolarEdge Off-Grid Monitor

## Milestones

- ✅ **v1.0 MVP** — Phases 1-6 (shipped 2026-02-07)
- ✅ **v1.1 Forecast Screen** — Phases 7-9 (shipped 2026-02-11)
- ✅ **v1.2 Forecast Fix** — Phase 10 (shipped 2026-02-12)
- 🚧 **v2.0 SolarEdge API V2** — Phases 11-14 (in progress)

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

<details>
<summary>✅ v1.2 Forecast Fix (Phase 10) — SHIPPED 2026-02-12</summary>

- [x] Phase 10: Forecast Fix (2/2 plans) — completed 2026-02-12

Plans:

- [x] 10-01-PLAN.md — Fix API parsing and forecast screen layout
- [x] 10-02-PLAN.md — Regenerate docs screenshot at correct resolution (gap closure)

</details>

### 🚧 v2.0 SolarEdge API V2 (Phases 11-14)

**Milestone goal:** The monitor shows real data again, fetched from the SolarEdge Monitoring API V2 via OAuth2, permanently below 2,000 calls per month.

- [x] **Phase 11: OAuth Login & Token Store** - One-time Mac login puts tokens on the Pi; the Pi refreshes them safely and shows "Login nötig" when it can't (completed 2026-11-05)
- [ ] **Phase 12: V2 Data Client & Screens** - All screens are filled from V2 endpoints; V1 code and blanket retry are gone
- [ ] **Phase 13: Fetch Plan & Quota Guard** - Calls follow a daytime schedule with cached screen rotation and a persistent counter that hard-stops at 1,800
- [ ] **Phase 14: Docs & Deployment** - systemd waits for time sync, README/.env.example cover V2, and se-monitor shows real values

## Phase Details

### Phase 11: OAuth Login & Token Store

**Goal**: The owner logs in once from the Mac, and from then on the Pi holds a valid token chain on its own, or clearly says it needs a new login
**Depends on**: Phase 10 (existing app)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Success Criteria** (what must be TRUE):

  1. Running the login script on the Mac opens the SolarEdge consent page in the browser, catches the redirect on http://localhost:8765/callback (with or without `state`), and exchanges the code for a token pair using client ID/secret read from 1Password via `op`
  2. After the script finishes, the token file exists on se-monitor with mode 0600, and the Mac keeps no refreshing copy
  3. When the access token is near expiry, the Pi refreshes it and the rotated refresh token is on disk (tmp file + fsync + rename, under a file lock) before the new access token is used; killing the process mid-refresh never leaves an unreadable token file
  4. With a missing, corrupt or rejected token (token endpoint 400/401), the display shows "Login nötig", the service stays up, and it resumes fetching on its own once a fresh token file is placed on the Pi

**Plans**: 5 plans

Plans:
**Wave 1**

- [x] 11-01-PLAN.md — Token store: atomic locked persist, refresh with rotation, LoginRequired signal, watcher, grant warning (wave 1)
- [x] 11-02-PLAN.md — Mac login script scripts/solaredge_login.py (op, browser callback, exchange, scp to Pi, .env secrets) (wave 1)
- [x] 11-03-PLAN.md — "Login nötig" screen, config OAuth fields, gitignore/.env.example (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 11-04-PLAN.md — main.py login-needed state, lazy site init, token-file pick-up, smoke test (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 11-05-PLAN.md — Deploy + real login on se-monitor, live verification (wave 3, checkpoint)

**UI hint**: yes

### Phase 12: V2 Data Client & Screens

**Goal**: Every existing screen shows correct values sourced from the Monitoring API V2, and no V1 code remains
**Depends on**: Phase 11
**Requirements**: API-01, API-02, API-03, API-04, API-05
**Success Criteria** (what must be TRUE):

  1. Produktion, Verbrauch, Einspeisung and Bezug show today's values from `GET /v2/sites/{id}/overview`, correctly converted from the returned `unit` and with null fields shown as 0
  2. Hausakku shows state of charge and power from `/storage/telemetry` (last non-null value), with Laden/Entladen/Ruhe derived from charge vs discharge power
  3. Battery presence is detected via `/devices?types=BATTERY` once and read from a disk cache on later starts (no inventory call on restart)
  4. Verlauf Produktion and Verlauf Verbrauch show 14 daily bars from `/meters/telemetry?resolution=DAY`, bucketed by local date
  5. The codebase contains no V1 endpoints, no power-flow model/fetch, and no blanket urllib3 retry on 429/5xx (at most one retry on 5xx/timeout)

**Plans**: 6 plans

Plans:
**Wave 1**

- [x] 12-01-PLAN.md — EnergyDetails breakdown fields + Produktion/Verbrauch use direct values, screen render tests (wave 1)
- [x] 12-02-PLAN.md — FetchPlan interim cadence (D-07) + battery presence disk cache (wave 1)

**Wave 2**

- [x] 12-03-PLAN.md — V2 client on TokenStore: overview, storage telemetry/status, devices, 14-day history; one retry on 5xx/timeout; V1 models removed (wave 2)
- [x] 12-04-PLAN.md — fetcher.py (fetch_round, today-bar patch, build_cycle) + config D-07 defaults, API key removed (wave 2)

**Wave 3**

- [x] 12-05-PLAN.md — main.py wiring (battery cache, FetchPlan, rotation on cached values) + repo-wide V1 gate (wave 3)

**Wave 4**

- [ ] 12-06-PLAN.md — Live deploy on se-monitor with owner go-ahead, read-only journal checks, display check (wave 4, checkpoint)
**UI hint**: yes

### Phase 13: Fetch Plan & Quota Guard

**Goal**: The monitor stays permanently within the 2,000-credit monthly budget while still looking up to date during the day
**Depends on**: Phase 12
**Requirements**: QUOTA-01, QUOTA-02, QUOTA-03
**Success Criteria** (what must be TRUE):

  1. Between 07:00 and 20:00 the overview is fetched every 30 min, storage telemetry hourly and history once a day; outside that window no data calls are made, and the display keeps rotating on cached values in between
  2. Every API call (including token refreshes and retries) increments a persistent counter that survives a service restart and resets on the configured billing day (default 5th)
  3. At 1,800 counted calls all API calls stop and the last values stay on screen until the counter resets
  4. The log shows the number of calls per day, so a day's total can be checked against the SolarEdge console

**Plans**: TBD

### Phase 14: Docs & Deployment

**Goal**: The V2 version runs on se-monitor from boot, and the setup and re-login procedure is documented
**Depends on**: Phase 13
**Requirements**: OPS-01, OPS-02, OPS-03
**Success Criteria** (what must be TRUE):

  1. The systemd unit starts only after `time-sync.target` (confirmed with `systemctl show` on se-monitor after a reboot)
  2. README and .env.example describe the V2 setup, how to run the login script, and the re-login procedure after more than 14 days offline
  3. The new version is deployed on se-monitor and the physical display shows real values that match monitoring.solaredge.com for the same day

**Plans**: TBD

## Progress

**Execution Order:** 11 → 12 → 13 → 14

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-6. MVP | v1.0 | 13/13 | Complete | 2026-02-07 |
| 7. Forecast API Integration | v1.1 | 2/2 | Complete | 2026-02-07 |
| 8. Forecast Screen | v1.1 | 1/1 | Complete | 2026-02-07 |
| 9. Documentation | v1.1 | 1/1 | Complete | 2026-02-11 |
| 10. Forecast Fix | v1.2 | 2/2 | Complete | 2026-02-12 |
| 11. OAuth Login & Token Store | v2.0 | 5/5 | Complete    | 2026-11-05 |
| 12. V2 Data Client & Screens | v2.0 | 5/6 | In Progress|  |
| 13. Fetch Plan & Quota Guard | v2.0 | 0/? | Not started | - |
| 14. Docs & Deployment | v2.0 | 0/? | Not started | - |

---

*Roadmap created: 2026-02-07*
*Last updated: 2026-11-05 (v2.0 SolarEdge API V2 phases 11-14 added)*
