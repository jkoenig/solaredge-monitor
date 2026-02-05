# Requirements

**Project:** SolarEdge Off-Grid Monitor
**Version:** v1 (Refactoring Milestone)
**Updated:** 2026-02-04

## v1 Requirements

### Architecture (ARCH)

- [ ] **ARCH-01**: Application split into separate modules: config, API clients, display rendering, main loop
- [ ] **ARCH-02**: No circular dependencies between modules — clear dependency flow: config → API → models → display → main
- [ ] **ARCH-03**: Each module importable and testable independently
- [ ] **ARCH-04**: Hardware abstraction layer — mock display for development without physical e-ink

### Configuration (CFG)

- [ ] **CFG-01**: All credentials loaded from environment variables or .env file (no hardcoded secrets)
- [ ] **CFG-02**: Configuration validated at startup with clear error messages for missing values
- [ ] **CFG-03**: .env.example file documenting all required environment variables
- [ ] **CFG-04**: .gitignore updated to exclude .env files and other sensitive data

### Data Sources (DATA)

- [ ] **DATA-01**: SolarEdge API client fetches current power flow (grid, load, PV, storage, off-grid state)
- [ ] **DATA-02**: SolarEdge API client fetches site overview (daily energy, lifetime stats)
- [ ] **DATA-03**: SolarEdge API client fetches energy details (consumption, production, feed-in, purchased)
- [ ] **DATA-04**: API client handles errors gracefully — returns None/defaults on failure, never crashes
- [ ] **DATA-05**: API responses use typed data models (dataclasses or similar) instead of raw lists/tuples

### Cleanup (CLN)

- [ ] **CLN-01**: VW WeConnect integration removed entirely (code, imports, credentials)
- [ ] **CLN-02**: BMW ConnectedDrive integration removed entirely (code, imports, credentials)
- [ ] **CLN-03**: Time Machine disk monitoring removed entirely (SSH, Paramiko, credentials)
- [ ] **CLN-04**: Unused Waveshare display drivers removed (keep only epd2in13_V3)
- [ ] **CLN-05**: Fresh git repository with no credential history

### Display (DISP)

- [ ] **DISP-01**: Display rendering separated from data fetching — display functions receive data models, not raw API responses
- [ ] **DISP-02**: Screen cycling through focused display screens (number and content TBD — to be refined after SolarEdge panel review)
- [ ] **DISP-03**: Improved font sizes for readability on 250x122 display (minimum 14px labels, 24px+ data)
- [ ] **DISP-04**: Debug mode outputs PNG files for development without hardware
- [ ] **DISP-05**: 4x supersampling maintained (render at 1000x488, scale to 250x122)

### Operations (OPS)

- [ ] **OPS-01**: 5-minute polling interval (configurable via environment variable)
- [ ] **OPS-02**: Time-gated operation — sleep between midnight and 6 AM
- [ ] **OPS-03**: Structured logging with appropriate log levels (INFO for normal operation, DEBUG for development)
- [ ] **OPS-04**: Graceful shutdown on SIGTERM/SIGINT (clean display state)
- [ ] **OPS-05**: Proper dependency management via requirements.txt or pyproject.toml with pinned versions

### Deployment (DEP)

- [ ] **DEP-01**: Deployment via git pull on Raspberry Pi Zero WH
- [ ] **DEP-02**: systemd service file for automatic startup and restart
- [ ] **DEP-03**: Setup script or documentation for initial Pi provisioning (SPI enable, dependencies, venv)

## v2 Requirements (Deferred)

- Single comprehensive screen option (alternative to cycling)
- Trend indicators (up/down arrows comparing to previous reading)
- Self-sufficiency ratio display
- Icon-based status indicators (battery, grid, solar icons)
- API response caching to prevent rate limit exhaustion
- Container-based deployment (if Pi hardware upgraded)
- GitHub-hosted repository (after fresh repo created)

## Out of Scope

- VW WeConnect integration — not a solar monitor feature, removed
- BMW ConnectedDrive integration — not a solar monitor feature, removed
- Time Machine disk monitoring — not a solar monitor feature, removed
- Docker/Kamal deployment — Pi Zero WH too constrained (512MB RAM, 1GHz)
- Web dashboard or API — dedicated hardware display only
- Database or persistent storage — stateless monitor
- Multiple SolarEdge sites — single site monitor
- Notifications or alerts — display-only
- Graphs/charts on display — 250x122 too small
- Historical data visualization — focus on current state

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLN-01 | Phase 1 | Pending |
| CLN-02 | Phase 1 | Pending |
| CLN-03 | Phase 1 | Pending |
| CLN-04 | Phase 1 | Pending |
| CLN-05 | Phase 1 | Pending |
| CFG-01 | Phase 2 | Pending |
| CFG-02 | Phase 2 | Pending |
| CFG-03 | Phase 2 | Pending |
| CFG-04 | Phase 2 | Pending |
| ARCH-01 | Phase 3 | Pending |
| ARCH-02 | Phase 3 | Pending |
| ARCH-03 | Phase 3 | Pending |
| ARCH-04 | Phase 3 | Pending |
| DATA-01 | Phase 3 | Pending |
| DATA-02 | Phase 3 | Pending |
| DATA-03 | Phase 3 | Pending |
| DATA-04 | Phase 3 | Pending |
| DATA-05 | Phase 3 | Pending |
| DISP-01 | Phase 4 | Pending |
| DISP-02 | Phase 4 | Pending |
| DISP-03 | Phase 4 | Pending |
| DISP-04 | Phase 4 | Pending |
| DISP-05 | Phase 4 | Pending |
| OPS-01 | Phase 5 | Pending |
| OPS-02 | Phase 5 | Pending |
| OPS-03 | Phase 5 | Pending |
| OPS-04 | Phase 5 | Pending |
| OPS-05 | Phase 5 | Pending |
| DEP-01 | Phase 6 | Pending |
| DEP-02 | Phase 6 | Pending |
| DEP-03 | Phase 6 | Pending |

---
*Last updated: 2026-02-04*
