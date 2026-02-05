# SolarEdge Off-Grid Monitor

## What This Is

A Raspberry Pi Zero WH-powered e-ink display monitor that shows real-time SolarEdge solar energy data — production, battery state, grid status, and consumption. Deployed via git pull + systemd to a single Raspberry Pi Zero WH (1 GHz, 512 MB RAM) with a Waveshare 2.13" e-ink display. Focused on readability and clean architecture.

## Core Value

Show the homeowner their solar energy state at a glance — production, battery, grid, consumption — on a physical e-ink display that's always up to date.

## Requirements

### Validated

- ✓ Fetch SolarEdge site overview (daily energy, lifetime stats) — existing
- ✓ Fetch SolarEdge energy details (consumption, production, feed-in, purchased) — existing
- ✓ Fetch SolarEdge current power flow (grid, load, PV, storage, off-grid state) — existing
- ✓ Render data to Waveshare 2.13" V3 e-ink display via PIL — existing
- ✓ Cycle through multiple display screens sequentially — existing
- ✓ Time-gated operation (sleep between midnight and 6 AM) — existing
- ✓ Debug mode with PNG output for development without hardware — existing

### Active

- [ ] Clean modular architecture (separate API, display, config layers)
- [ ] Environment-based configuration (no hardcoded credentials)
- [ ] Git pull + systemd deployment to Raspberry Pi Zero WH
- [ ] Improved display readability (larger fonts, better layout for 250x122)
- [ ] Focused display screens with screen cycling (content TBD)
- [ ] 5-minute polling interval with proper error handling and retry
- [ ] Fresh git repository (no credential history)
- [ ] Proper dependency management (requirements.txt with pinned versions)
- [ ] Structured logging with appropriate log levels
- [ ] Graceful shutdown handling (SIGTERM/SIGINT)

### Out of Scope

- VW WeConnect integration — removing, not a solar monitor feature
- BMW ConnectedDrive integration — removing, not a solar monitor feature
- Time Machine disk usage monitoring — removing, not a solar monitor feature
- Multi-display support — single Pi, single display
- Web dashboard or API — this is a dedicated hardware display
- Database or persistent storage — stateless monitor, fresh data each cycle
- Multiple SolarEdge sites — single site monitor
- Notifications or alerts — display-only

## Context

- Existing codebase is a working MVP (828-line monolithic script) generated with an older AI
- All code in a single `se-overview.py` with hardcoded credentials, duplicated display functions, and mixed concerns
- VW, BMW, and SSH integrations account for ~40% of code and will be removed entirely
- Current fonts are too small for the 250x122 pixel display — readability is poor
- Waveshare e-ink driver library (`lib/waveshare_epd/`) includes 60+ unused drivers — only `epd2in13_V3` is needed
- SolarEdge monitoring API updates roughly every 15 minutes, so 5-minute polling is sufficient
- Credentials are baked into git history — requires a fresh repo to publish safely on GitHub
- Display uses 4x supersampling (render at 1000x488, scale down to 250x122) for quality
- Target hardware: Raspberry Pi Zero WH (1 GHz, 512 MB RAM) — too constrained for Docker/Kamal

## Constraints

- **Hardware**: Waveshare 2.13" V3 e-ink display (250x122 pixels, 1-bit black/white) — fixed display size
- **Platform**: Raspberry Pi Zero WH (ARM, 1 GHz, 512 MB RAM) — very constrained, no Docker
- **API**: SolarEdge monitoring API — rate limits apply, ~15 min data freshness
- **Display**: SPI/GPIO access required directly (no container layer)
- **Network**: Pi needs network access for API calls
- **Deployment**: Git pull + systemd (SSH access to Pi from development machine)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fresh git repo instead of history rewrite | Simplest way to remove credentials, existing history has no significant value | — Pending |
| Environment variables for credentials | Standard practice, .env file for Pi deployment | — Pending |
| Git pull + systemd for deployment | Pi Zero WH too constrained for Docker/Kamal (512 MB RAM) | — Pending |
| 5-minute polling interval | SolarEdge data updates ~15 min, 5 min balances freshness vs API load | — Pending |
| Keep 2.13" display | User confirmed, improve readability through better font/layout choices | — Pending |
| Cycle through screens | User preference over single dashboard — keeps each screen focused and readable | — Pending |
| SolarEdge only | Strip VW, BMW, disk monitoring — focused single-purpose tool | — Pending |
| Sleep midnight-6AM | User confirmed current behavior, no solar production at night | — Pending |

---
*Last updated: 2026-02-04 after roadmap creation*
