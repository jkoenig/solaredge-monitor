# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-04)

**Core value:** Show the homeowner their solar energy state at a glance — production, battery, grid, consumption — on a physical e-ink display that's always up to date.

**Current focus:** Phase 6 in progress — Deployment

## Current Position

Phase: 6 of 6 (Deployment)
Plan: 2 of 2 completed
Status: Phase complete
Last activity: 2026-02-06 — Completed 06-02-PLAN.md (Documentation and git configuration)

Progress: [████████████] 100% (13/13 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 13
- Average duration: 1.8 minutes
- Total execution time: 0.41 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 2 | 8.8 min | 4.4 min |
| 02 | 1 | 2.0 min | 2.0 min |
| 03 | 3 | 4.0 min | 1.3 min |
| 04 | 3 | 5.4 min | 1.8 min |
| 05 | 2 | 3.2 min | 1.6 min |
| 06 | 2 | 2.5 min | 1.3 min |

**Recent Trend:**
- Last 5 plans: 2.0 min, 2.0 min, 1.2 min, 1.2 min, 1.3 min
- Trend: Excellent (consistently sub-2.5 min)

*Updated after each plan completion*

## Accumulated Context

### Decisions

- Phase 1: Proceeded with fresh repository (user approved destruction of old history)
- Phase 1: Sanitized credential values from planning docs with [REDACTED-*] placeholders
- Phase 2: Use python-dotenv for .env file loading (12-factor app methodology)
- Phase 2: Single Config dataclass for all settings, not split by concern
- Phase 2: SOLAREDGE_ prefix for all environment variables
- Phase 2: Validate all errors at once before raising (operator fixes everything in one pass)
- Phase 2: Boolean parsing uses explicit string checking to avoid truthiness trap
- Phase 3: Use frozen dataclasses for immutability to prevent accidental state mutation
- Phase 3: Include fetched_at timestamp on all models using default_factory for safe defaults
- Phase 3: Use >= for requests (stable API) vs == for python-dotenv (already established)
- Phase 3: Use Optional[] type hints for Python 3.9 compatibility (not | union syntax)
- Phase 3: Retry only GET methods with status codes 429, 500, 502, 503, 504
- Phase 3: HTTP timeout 10 seconds per request to prevent hanging
- Phase 3: Exponential backoff 2s, 4s, 8s for transient API failures
- Phase 3: Display class receives debug_mode as constructor argument to avoid circular imports
- Phase 3: PNG files saved to ./debug/ folder with timestamp naming
- Phase 3: Render at 4x supersampling (1000x488) for high-quality e-ink output
- Phase 3: Load dotenv before importing Config to ensure environment variables available
- Phase 4: Font cache by (name, size) tuple to avoid repeated file I/O
- Phase 4: Font search chain: project fonts/ -> Raspberry Pi system fonts -> PIL default
- Phase 4: Percentage text rendered to right of bar for clarity (avoids white-on-black complexity)
- Phase 4: All drawing functions accept (draw, x, y, size) signature for consistency
- Phase 4: Complex screens use 140px values with icon breakdowns; simple screens use 180px centered values
- Phase 4: Bar percentage maxes: 20 kWh (production), 15 kWh (consumption), 10 kWh (feed-in/purchased)
- Phase 4: Battery energy calculated as delta from production/consumption/self-consumption/purchased/feed-in
- Phase 4: Unit text baseline-aligned to right of main values for professional typography
- Phase 4: LANCZOS via L-mode intermediate for quality downsampling (1-bit -> grayscale -> resize -> 1-bit)
- Phase 4: Debug PNG at full 1000x488 resolution; e-ink gets LANCZOS-scaled 250x122
- Phase 4: Pillow>=10.0.0,<11.0.0 for Python 3.9 compatibility
- Phase 5: JSON logging format for both stdout (systemd) and rotating file (10MB/5 backups)
- Phase 5: Log level validated against DEBUG/INFO/WARNING/ERROR/CRITICAL (case-insensitive)
- Phase 5: Error screen not registered in screens/__init__.py (called directly by main.py on failures)
- Phase 5: Use monotonic clock for poll scheduling (immune to system time changes)
- Phase 5: Interruptible sleep pattern checks shutdown_flag every second for responsive shutdown
- Phase 5: Show stale data on initial API failures, error screen only after 3 consecutive failures
- Phase 5: Sleep mode uses try/finally to guarantee display cleanup even on crashes
- Phase 5: Hardcode Europe/Berlin timezone per research recommendation
- Phase 5: Screen cycle holds on Produktion between polls (not continuous cycling)
- Phase 6: Restart=always for all exit codes (auto-recovery on crashes)
- Phase 6: RestartSec=10 with rate limiting (5 starts in 200s) per systemd best practices
- Phase 6: Absolute venv path in ExecStart (no activation needed)
- Phase 6: Journal logging via StandardOutput/StandardError (works with existing dual logging)
- Phase 6: User=pi for GPIO/SPI access (default Raspberry Pi groups)
- Phase 6: Idempotent install.sh checks (preserves .env, detects existing venv/SPI)
- Phase 6: Root user refusal in both scripts (must run as pi user)
- Phase 6: .gitignore now excludes .planning/ directory (development tooling, not for public repo)
- Phase 6: README uses English documentation despite German UI labels on screens
- Phase 6: README emphasizes install.sh for initial setup and deploy.sh for updates

### Pending Todos

None yet.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-02-06
Stopped at: Completed 06-02-PLAN.md (Documentation and git configuration) - Phase 6 complete
Resume file: None

---

*Last updated: 2026-02-06*
