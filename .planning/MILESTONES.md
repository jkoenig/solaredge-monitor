# Project Milestones: SolarEdge Off-Grid Monitor

## v1 Refactoring (Shipped: 2026-02-06)

**Delivered:** Refactored 828-line monolithic script into clean, modular Python application with environment-based config, SolarEdge API client, 4 focused e-ink display screens, and systemd deployment automation.

**Phases completed:** 1-6 (13 plans total)

**Key accomplishments:**
- Stripped all non-solar integrations (VW, BMW, Time Machine) and 75+ unused display drivers, creating a fresh git repo with zero credential history
- Built environment-based configuration with validation, typed SolarEdge API client with retry logic, and frozen dataclass models
- Created 4 German-localized e-ink screens (Produktion, Verbrauch, Einspeisung, Bezug) with 4x supersampling and LANCZOS downsampling
- Implemented production polling loop with screen cycling, sleep mode, error recovery, and graceful shutdown
- Automated deployment with systemd service, install.sh for Pi provisioning, and deploy.sh for updates
- Comprehensive README documentation with setup, deployment, and troubleshooting guides

**Stats:**
- 78 files created/modified across 60 commits
- 1,736 lines of Python (application code, excluding drivers)
- 6 phases, 13 plans
- 2 days from start to ship (2026-02-05 to 2026-02-06)

**Git range:** `dd35335` (Initial commit) → `8aa7472` (tech debt fixes)

**What's next:** TBD

---

## v1.1 Forecast Screen (Shipped: 2026-02-11)

**Delivered:** Added solar production forecast screen using Forecast.Solar API, showing today's forecast with actual-vs-forecast progress bar and tomorrow's prediction.

**Phases completed:** 7-9 (4 plans, 8 tasks)

**Key accomplishments:**
- Forecast.Solar API client with 1-hour TTL caching and graceful failure handling (rate limits, network errors)
- "Prognose, heute" screen with actual-vs-forecast progress bar, overflow indicator for >100%, and tomorrow's forecast with delta
- Optional feature activation — forecast only shown when all 5 .env values configured (backward compatible)
- Complete documentation with screenshot and configuration instructions in README
- 9 screens total in rotation (up from 7 in v1.0)

**Stats:**
- 14 files created/modified across 10 commits
- 2,699 lines of Python (project total, up from 1,736)
- 3 phases, 4 plans, 8 tasks
- 6 days from start to ship (2026-02-05 to 2026-02-11)

**Git range:** `f612511` (forecast config) → `c03f2d9` (phase 9 complete)

**What's next:** TBD

---

