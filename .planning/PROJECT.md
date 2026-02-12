# SolarEdge Off-Grid Monitor

## What This Is

A Raspberry Pi Zero WH-powered e-ink display monitor that shows daily SolarEdge solar energy data — production, consumption, feed-in, purchased energy, battery state, and solar production forecast — on a Waveshare 2.13" display. Modular Python application with 9 screens, 4x supersampling, and optional Forecast.Solar integration.

## Core Value

Show the homeowner their solar energy state at a glance — production, consumption, feed-in, purchased — on a physical e-ink display that's always up to date.

## Requirements

### Validated

- ✓ Fetch SolarEdge site overview (daily energy, lifetime stats) — v1.0
- ✓ Fetch SolarEdge energy details (consumption, production, feed-in, purchased) — v1.0
- ✓ Fetch SolarEdge current power flow (grid, load, PV, storage, off-grid state) — v1.0
- ✓ Render data to Waveshare 2.13" V3 e-ink display via PIL — v1.0
- ✓ Cycle through multiple display screens sequentially — v1.0
- ✓ Time-gated operation (sleep between midnight and 6 AM) — v1.0
- ✓ Debug mode with PNG output for development without hardware — v1.0
- ✓ Clean modular architecture (separate API, display, config layers) — v1.0
- ✓ Environment-based configuration (no hardcoded credentials) — v1.0
- ✓ Git pull + systemd deployment to Raspberry Pi Zero WH — v1.0
- ✓ Improved display readability (larger fonts, better layout for 250x122) — v1.0
- ✓ Focused display screens with screen cycling (4 screens: Produktion, Verbrauch, Einspeisung, Bezug) — v1.0
- ✓ 5-minute polling interval with proper error handling and retry — v1.0
- ✓ Fresh git repository (no credential history) — v1.0
- ✓ Proper dependency management (requirements.txt with pinned versions) — v1.0
- ✓ Structured logging with appropriate log levels — v1.0
- ✓ Graceful shutdown handling (SIGTERM/SIGINT) — v1.0
- ✓ Forecast.Solar API integration (today + tomorrow production forecast) — v1.1
- ✓ "Prognose, heute" display screen with actual vs forecast progress bar and tomorrow's forecast — v1.1
- ✓ Forecast configuration via .env (lat, lon, tilt, azimuth, kWp) — v1.1
- ✓ Hourly forecast caching (Forecast.Solar free tier: 12 req/hour) — v1.1

- ✓ Forecast.Solar API response parsed correctly (reads flat `data["result"]` mapping) — v1.2
- ✓ Forecast screen layout aligned with production/consumption screens (identical grid, fonts, spacing) — v1.2
- ✓ Forecast screen verified via debug PNG output matching visual style of other screens — v1.2

### Active

(No active requirements — all milestones shipped)

### Out of Scope

- Multi-display support — single Pi, single display
- Web dashboard or API — this is a dedicated hardware display
- Database or persistent storage — stateless monitor, fresh data each cycle
- Multiple SolarEdge sites — single site monitor
- Notifications or alerts — display-only
- Paid Forecast.Solar tier — free tier sufficient (today + tomorrow, 12 req/hour)
- Solcast integration — only 10 req/day on free tier, too restrictive
- Hourly forecast breakdown — keep screen simple, daily totals only

## Context

Shipped v1.2 with ~2,700 lines of Python across 20 modules, 9 display screens. Tech stack: Python 3.9+, Pillow, requests, python-dotenv, python-json-logger, Waveshare e-ink driver. Deployed on Raspberry Pi Zero WH (1 GHz, 512 MB) via systemd.

Screens: Produktion, Verbrauch, Einspeisung, Bezug, Hausakku (auto-detected), Prognose (optional, Forecast.Solar), Verlauf Produktion, Verlauf Verbrauch.

Known tech debt: PowerFlow data fetched but not displayed (reserved for future), SiteOverview API method implemented but unused (reserved for future).

Future ideas from requirements: PowerFlow display (real-time watts), SiteOverview screen (lifetime stats).

## Constraints

- **Hardware**: Waveshare 2.13" V3 e-ink display (250x122 pixels, 1-bit black/white) — fixed display size
- **Platform**: Raspberry Pi Zero WH (ARM, 1 GHz, 512 MB RAM) — very constrained, no Docker
- **API**: SolarEdge monitoring API — rate limits apply, ~15 min data freshness
- **API**: Forecast.Solar free tier — 12 req/hour, today + tomorrow only
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
| Forecast.Solar free tier | Sufficient for daily forecast (today + tomorrow), 12 req/hour | ✓ Good |
| TTL cache for forecast API | 1-hour cache prevents exceeding rate limits, caches None to avoid hammering | ✓ Good |
| Optional forecast feature | All 5 .env values required for atomic activation, backward compatible | ✓ Good |
| Manual bar drawing for forecast | draw_horizontal_bar auto-appends percentage — custom legend needed for forecast | ✓ Good |
| Fixed-text sizing for bar labels | Matches production.py pattern, makes layout data-independent | ✓ Good |
| Save docs screenshots at canvas resolution | 1000x488 for documentation, 250x122 only for display pipeline | ✓ Good |

---
*Last updated: 2026-02-12 after v1.2 milestone complete*
