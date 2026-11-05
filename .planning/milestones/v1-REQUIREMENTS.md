# Requirements Archive: v1 Refactoring

**Archived:** 2026-02-06
**Status:** SHIPPED

This is the archived requirements specification for v1.
For current requirements, see `.planning/REQUIREMENTS.md` (created for next milestone).

---

## v1 Requirements

### Architecture (ARCH)

- [x] **ARCH-01**: Application split into separate modules: config, API clients, display rendering, main loop
- [x] **ARCH-02**: No circular dependencies between modules — clear dependency flow: config -> API -> models -> display -> main
- [x] **ARCH-03**: Each module importable and testable independently
- [x] **ARCH-04**: Hardware abstraction layer — mock display for development without physical e-ink

### Configuration (CFG)

- [x] **CFG-01**: All credentials loaded from environment variables or .env file (no hardcoded secrets)
- [x] **CFG-02**: Configuration validated at startup with clear error messages for missing values
- [x] **CFG-03**: .env.example file documenting all required environment variables
- [x] **CFG-04**: .gitignore updated to exclude .env files and other sensitive data

### Data Sources (DATA)

- [x] **DATA-01**: SolarEdge API client fetches current power flow (grid, load, PV, storage, off-grid state)
- [x] **DATA-02**: SolarEdge API client fetches site overview (daily energy, lifetime stats)
- [x] **DATA-03**: SolarEdge API client fetches energy details (consumption, production, feed-in, purchased)
- [x] **DATA-04**: API client handles errors gracefully — returns None/defaults on failure, never crashes
- [x] **DATA-05**: API responses use typed data models (dataclasses or similar) instead of raw lists/tuples

### Cleanup (CLN)

- [x] **CLN-01**: VW WeConnect integration removed entirely (code, imports, credentials)
- [x] **CLN-02**: BMW ConnectedDrive integration removed entirely (code, imports, credentials)
- [x] **CLN-03**: Time Machine disk monitoring removed entirely (SSH, Paramiko, credentials)
- [x] **CLN-04**: Unused Waveshare display drivers removed (keep only epd2in13_V3)
- [x] **CLN-05**: Fresh git repository with no credential history

### Display (DISP)

- [x] **DISP-01**: Display rendering separated from data fetching — display functions receive data models, not raw API responses
- [x] **DISP-02**: Screen cycling through focused display screens (number and content TBD — to be refined after SolarEdge panel review)
- [x] **DISP-03**: Improved font sizes for readability on 250x122 display (minimum 14px labels, 24px+ data)
- [x] **DISP-04**: Debug mode outputs PNG files for development without hardware
- [x] **DISP-05**: 4x supersampling maintained (render at 1000x488, scale to 250x122)

### Operations (OPS)

- [x] **OPS-01**: 5-minute polling interval (configurable via environment variable)
- [x] **OPS-02**: Time-gated operation — sleep between midnight and 6 AM
- [x] **OPS-03**: Structured logging with appropriate log levels (INFO for normal operation, DEBUG for development)
- [x] **OPS-04**: Graceful shutdown on SIGTERM/SIGINT (clean display state)
- [x] **OPS-05**: Proper dependency management via requirements.txt or pyproject.toml with pinned versions

### Deployment (DEP)

- [x] **DEP-01**: Deployment via git pull on Raspberry Pi Zero WH
- [x] **DEP-02**: systemd service file for automatic startup and restart
- [x] **DEP-03**: Setup script or documentation for initial Pi provisioning (SPI enable, dependencies, venv)

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLN-01 | Phase 1 | Complete |
| CLN-02 | Phase 1 | Complete |
| CLN-03 | Phase 1 | Complete |
| CLN-04 | Phase 1 | Complete |
| CLN-05 | Phase 1 | Complete |
| CFG-01 | Phase 2 | Complete |
| CFG-02 | Phase 2 | Complete |
| CFG-03 | Phase 2 | Complete |
| CFG-04 | Phase 2 | Complete |
| ARCH-01 | Phase 3 | Complete |
| ARCH-02 | Phase 3 | Complete |
| ARCH-03 | Phase 3 | Complete |
| ARCH-04 | Phase 3 | Complete |
| DATA-01 | Phase 3 | Complete |
| DATA-02 | Phase 3 | Complete |
| DATA-03 | Phase 3 | Complete |
| DATA-04 | Phase 3 | Complete |
| DATA-05 | Phase 3 | Complete |
| DISP-01 | Phase 4 | Complete |
| DISP-02 | Phase 4 | Complete |
| DISP-03 | Phase 4 | Complete |
| DISP-04 | Phase 4 | Complete |
| DISP-05 | Phase 4 | Complete |
| OPS-01 | Phase 5 | Complete |
| OPS-02 | Phase 5 | Complete |
| OPS-03 | Phase 5 | Complete |
| OPS-04 | Phase 5 | Complete |
| OPS-05 | Phase 5 | Complete |
| DEP-01 | Phase 6 | Complete |
| DEP-02 | Phase 6 | Complete |
| DEP-03 | Phase 6 | Complete |

---

## Milestone Summary

**Shipped:** 25 of 25 v1 requirements
**Adjusted:** None
**Dropped:** None

---
*Archived: 2026-02-06 as part of v1 milestone completion*
