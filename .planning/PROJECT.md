# SolarEdge Off-Grid Monitor

## What This Is

A Raspberry Pi Zero WH-powered e-ink display monitor that shows daily SolarEdge solar energy data — production, consumption, feed-in, and purchased energy — on a Waveshare 2.13" display. Modular Python application deployed via git pull + systemd with 4 focused screens, 4x supersampling for readability, and automated setup/deploy scripts.

## Core Value

Show the homeowner their solar energy state at a glance — production, consumption, feed-in, purchased — on a physical e-ink display that's always up to date.

## Requirements

### Validated

- ✓ Fetch SolarEdge site overview (daily energy, lifetime stats) — v1
- ✓ Fetch SolarEdge energy details (consumption, production, feed-in, purchased) — v1
- ✓ Fetch SolarEdge current power flow (grid, load, PV, storage, off-grid state) — v1
- ✓ Render data to Waveshare 2.13" V3 e-ink display via PIL — v1
- ✓ Cycle through multiple display screens sequentially — v1
- ✓ Time-gated operation (sleep between midnight and 6 AM) — v1
- ✓ Debug mode with PNG output for development without hardware — v1
- ✓ Clean modular architecture (separate API, display, config layers) — v1
- ✓ Environment-based configuration (no hardcoded credentials) — v1
- ✓ Git pull + systemd deployment to Raspberry Pi Zero WH — v1
- ✓ Improved display readability (larger fonts, better layout for 250x122) — v1
- ✓ Focused display screens with screen cycling (4 screens: Produktion, Verbrauch, Einspeisung, Bezug) — v1
- ✓ 5-minute polling interval with proper error handling and retry — v1
- ✓ Fresh git repository (no credential history) — v1
- ✓ Proper dependency management (requirements.txt with pinned versions) — v1
- ✓ Structured logging with appropriate log levels — v1
- ✓ Graceful shutdown handling (SIGTERM/SIGINT) — v1

### Active

(None — next milestone requirements TBD)

### Out of Scope

- Multi-display support — single Pi, single display
- Web dashboard or API — this is a dedicated hardware display
- Database or persistent storage — stateless monitor, fresh data each cycle
- Multiple SolarEdge sites — single site monitor
- Notifications or alerts — display-only

## Context

Shipped v1 with 1,736 lines of Python across 17 modules. Tech stack: Python 3.9+, Pillow, requests, python-dotenv, python-json-logger, Waveshare e-ink driver. Deployed on Raspberry Pi Zero WH (1 GHz, 512 MB) via systemd.

Known tech debt: PowerFlow data fetched but not displayed (reserved for v2), SiteOverview API method implemented but unused (reserved for v2).

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
| Fresh git repo instead of history rewrite | Simplest way to remove credentials, existing history has no significant value | ✓ Good |
| Environment variables for credentials | Standard practice, .env file for Pi deployment | ✓ Good |
| Git pull + systemd for deployment | Pi Zero WH too constrained for Docker/Kamal (512 MB RAM) | ✓ Good |
| 5-minute polling interval | SolarEdge data updates ~15 min, 5 min balances freshness vs API load | ✓ Good |
| Keep 2.13" display | User confirmed, improve readability through better font/layout choices | ✓ Good |
| Cycle through screens | User preference over single dashboard — keeps each screen focused and readable | ✓ Good |
| SolarEdge only | Strip VW, BMW, disk monitoring — focused single-purpose tool | ✓ Good |
| Sleep midnight-6AM | User confirmed current behavior, no solar production at night | ✓ Good |
| Frozen dataclasses for API models | Immutability prevents accidental state mutation | ✓ Good |
| LANCZOS downsampling via L-mode intermediate | High quality 4x scale-down for 1-bit e-ink output | ✓ Good |
| JSON structured logging | Machine-parseable logs for systemd journal and rotating file | ✓ Good |
| Europe/Berlin timezone hardcoded | Single-site monitor, no need for timezone configuration | ✓ Good |
| German screen labels | User's native language for at-a-glance reading | ✓ Good |

---
*Last updated: 2026-02-06 after v1 milestone*
