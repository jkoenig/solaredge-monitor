# Milestone v1: Refactoring

**Status:** SHIPPED 2026-02-06
**Phases:** 1-6
**Total Plans:** 13

## Overview

Transform a 828-line monolithic script into a clean, modular Python application. Remove non-solar integrations (VW, BMW, Time Machine), extract configuration into environment variables, separate display rendering from data fetching, improve readability with larger fonts, and deploy via git pull + systemd to Raspberry Pi Zero WH with e-ink display.

## Phases

### Phase 1: Cleanup & Fresh Repository
**Goal**: Remove all non-solar code and create fresh repository with no credential history
**Depends on**: Nothing (first phase)
**Requirements**: CLN-01, CLN-02, CLN-03, CLN-04, CLN-05
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md -- Remove non-solar code, files, and unused Waveshare drivers
- [x] 01-02-PLAN.md -- Create fresh git repository with no credential history

**Success Criteria:**
  1. VW WeConnect code and credentials completely removed from codebase
  2. BMW ConnectedDrive code and credentials completely removed from codebase
  3. Time Machine SSH monitoring code and credentials completely removed from codebase
  4. Only epd2in13_V3 driver remains in Waveshare library (60+ unused drivers removed)
  5. Fresh git repository exists with no credential history in any commit

---

### Phase 2: Configuration Foundation
**Goal**: All credentials and configuration loaded from environment variables with validation
**Depends on**: Phase 1
**Requirements**: CFG-01, CFG-02, CFG-03, CFG-04
**Plans**: 1 plan

Plans:
- [x] 02-01-PLAN.md -- Config dataclass with env loading, validation, .env.example, and requirements.txt

**Success Criteria:**
  1. Application reads all credentials from environment variables or .env file (zero hardcoded values)
  2. Application validates configuration at startup and exits with clear error messages if required values missing
  3. .env.example file documents all required environment variables with descriptions
  4. .gitignore excludes .env files and sensitive data

---

### Phase 3: Architecture & Data Layer
**Goal**: Modular codebase with clean separation and SolarEdge API integration
**Depends on**: Phase 2
**Requirements**: ARCH-01, ARCH-02, ARCH-03, ARCH-04, DATA-01, DATA-02, DATA-03, DATA-04, DATA-05
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md -- Create data models (PowerFlow, EnergyDetails, SiteOverview) and add requests dependency
- [x] 03-02-PLAN.md -- Create SolarEdge API client with retry logic and error handling
- [x] 03-03-PLAN.md -- Create display hardware abstraction and main.py entry point

**Success Criteria:**
  1. Application split into separate modules: config, API clients, display rendering, main loop
  2. Each module can be imported and tested independently without circular dependencies
  3. Hardware abstraction layer allows development without physical e-ink (mock display works)
  4. SolarEdge API client fetches power flow, site overview, and energy details with graceful error handling
  5. API responses use typed data models (dataclasses) instead of raw lists/tuples

---

### Phase 4: Display Layer
**Goal**: Readable e-ink display with improved fonts and development-friendly debug mode
**Depends on**: Phase 3
**Requirements**: DISP-01, DISP-02, DISP-03, DISP-04, DISP-05
**Plans**: 3 plans

Plans:
- [x] 04-01-PLAN.md -- Rendering utilities (fonts, icons, bars)
- [x] 04-02-PLAN.md -- Screen renderers (Produktion, Verbrauch, Einspeisung, Bezug)
- [x] 04-03-PLAN.md -- Display LANCZOS downsampling, Pillow dependency, visual verification

**Success Criteria:**
  1. Display rendering separated from data fetching (display functions receive data models)
  2. Screen cycling implemented through focused display screens
  3. Fonts improved for readability (minimum 14px labels, 24px+ data values)
  4. Debug mode outputs PNG files for development without hardware
  5. 4x supersampling maintained (render at 1000x488, scale to 250x122)

---

### Phase 5: Operations
**Goal**: Production-ready operational behavior with proper polling, logging, and shutdown
**Depends on**: Phase 4
**Requirements**: OPS-01, OPS-02, OPS-03, OPS-04, OPS-05
**Plans**: 2 plans

Plans:
- [x] 05-01-PLAN.md -- Logging setup, config extensions, error screen renderer
- [x] 05-02-PLAN.md -- Production polling loop with screen cycling, sleep mode, and graceful shutdown

**Success Criteria:**
  1. Application polls every 5 minutes (configurable via environment variable)
  2. Application sleeps between midnight and 6 AM (time-gated operation)
  3. Structured logging with INFO for normal operation, DEBUG for development
  4. Application handles SIGTERM/SIGINT gracefully (clears display state before exit)
  5. Dependencies managed via requirements.txt with pinned versions

---

### Phase 6: Deployment
**Goal**: Deployment automation via git pull with systemd service on Raspberry Pi Zero WH
**Depends on**: Phase 5
**Requirements**: DEP-01, DEP-02, DEP-03
**Plans**: 2 plans

Plans:
- [x] 06-01-PLAN.md -- systemd service file, install script, and deploy script
- [x] 06-02-PLAN.md -- .gitignore update and full README documentation

**Success Criteria:**
  1. Application deploys via git pull on Raspberry Pi Zero WH
  2. systemd service file enables automatic startup and restart on failure
  3. Setup documentation guides initial Pi provisioning (SPI enable, dependencies, venv setup)

---

## Milestone Summary

**Key Decisions:**
- Fresh git repo instead of history rewrite (simplest credential removal)
- Environment variables with SOLAREDGE_ prefix and python-dotenv
- Frozen dataclasses for immutable API response models
- 4x supersampling with LANCZOS downsampling for e-ink quality
- German-localized screen labels (Produktion, Verbrauch, Einspeisung, Bezug)
- JSON structured logging with rotating file handler
- Interruptible sleep pattern for responsive shutdown
- systemd with Restart=always and rate limiting
- Europe/Berlin timezone hardcoded per research recommendation

**Issues Resolved:**
- Credential exposure in git history (fresh repo)
- 828-line monolithic script (split into 17 modules)
- Unreadable fonts on e-ink display (4x supersampling + larger fonts)
- 75+ unused Waveshare drivers (reduced to 1)

**Technical Debt Resolved (post-audit):**
- Logging initialization ordering fixed (setup_logging before Config)
- Legacy se-overview.py removed

**Technical Debt Remaining:**
- PowerFlow data fetched but not displayed on any screen (reserved for v2)
- SiteOverview API method implemented but never called (reserved for v2)

---

_For current project status, see .planning/ROADMAP.md_
