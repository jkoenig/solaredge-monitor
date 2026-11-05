# Requirements: SolarEdge Off-Grid Monitor — v2.0 SolarEdge API V2

**Defined:** 2026-11-05
**Core Value:** Show the homeowner their solar energy state at a glance on a physical e-ink display that's always up to date.
**Research:** .planning/research/V2-API.md

## v2.0 Requirements

### Anmeldung (AUTH)

- [ ] **AUTH-01**: Owner can authorize the app once from the Mac with a login script that opens the browser, catches the code on http://localhost:8765/callback and exchanges it for tokens (client ID/secret read from 1Password via `op`, item 7rboxat3in2tlx2ywilmsna5cy)
- [ ] **AUTH-02**: The login script places the token pair on se-monitor with mode 0600; from then on only the Pi refreshes tokens
- [ ] **AUTH-03**: The Pi refreshes the access token before it expires and persists the rotated refresh token atomically (write + rename, file lock) before using it
- [ ] **AUTH-04**: When the token is missing, invalid or refresh is rejected, the display shows "Login nötig"; the service keeps running and resumes fetching once new tokens are in place

### Daten (API)

- [ ] **API-01**: Produktion, Verbrauch, Einspeisung and Bezug screens are filled from `GET /v2/sites/{id}/overview`
- [ ] **API-02**: Hausakku screen shows state of charge and power from `/storage/telemetry`; charge/discharge/idle status is derived from the power values
- [ ] **API-03**: Battery presence is detected once via `/devices?types=BATTERY` and cached on disk
- [ ] **API-04**: Verlauf Produktion/Verbrauch screens get daily values from `/meters/telemetry?resolution=DAY`
- [ ] **API-05**: V1 code is removed, including power-flow and the blanket automatic retry on 429/5xx

### Kontingent (QUOTA)

- [ ] **QUOTA-01**: Fetch plan: overview every 30 min 07:00–20:00, storage hourly, history once a day; screens rotate on cached values in between
- [ ] **QUOTA-02**: A persistent counter on the Pi counts every API call, survives restarts, resets on a configurable billing day (default 5th) and stops all calls at 1800, keeping the last values on screen
- [ ] **QUOTA-03**: Calls per day are logged for verification

### Betrieb (OPS)

- [ ] **OPS-01**: The systemd unit starts only after time sync (`time-sync.target`)
- [ ] **OPS-02**: README and .env.example describe V2 setup, the login script and the re-login procedure after >14 days offline
- [ ] **OPS-03**: New version deployed on se-monitor and the display shows real values

## Future Requirements

- Token refresh credit cost and remaining-quota headers: revisit once real usage is measured (open questions in research)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Live power / power-flow | Advanced Monitoring only (Business Pro, $1000/month); returns 403 on Free |
| API key / Fleet access | Official docs: homeowners can only use OAuth Site Access |
| Re-enabling the watchdog check | Done afterwards in the home-watchdog repo (backlog 999.27) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 11 | Pending |
| AUTH-02 | Phase 11 | Pending |
| AUTH-03 | Phase 11 | Pending |
| AUTH-04 | Phase 11 | Pending |
| API-01 | Phase 12 | Pending |
| API-02 | Phase 12 | Pending |
| API-03 | Phase 12 | Pending |
| API-04 | Phase 12 | Pending |
| API-05 | Phase 12 | Pending |
| QUOTA-01 | Phase 13 | Pending |
| QUOTA-02 | Phase 13 | Pending |
| QUOTA-03 | Phase 13 | Pending |
| OPS-01 | Phase 14 | Pending |
| OPS-02 | Phase 14 | Pending |
| OPS-03 | Phase 14 | Pending |

**Coverage:**
- v2.0 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0

---
*Requirements defined: 2026-11-05*
*Last updated: 2026-11-05 after roadmap creation (phases 11-14)*
