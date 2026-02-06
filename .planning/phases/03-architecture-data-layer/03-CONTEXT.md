# Phase 3: Architecture & Data Layer - Context

**Gathered:** 2026-02-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Restructure the monolithic se-overview.py into clean, importable modules with a SolarEdge API client. Create data models for API responses and a hardware abstraction layer for development without e-ink hardware.

</domain>

<decisions>
## Implementation Decisions

### Module structure
- Flat modules at project root: config.py, solaredge_api.py, models.py, display.py, main.py
- API module named `solaredge_api.py` (not generic `api.py`) to allow future additions like `weather_api.py`
- Entry point: `main.py` at root (run with `python main.py`)
- Data models in separate `models.py`, imported by API and display modules

### Data models
- Include `fetched_at` timestamp field on all data models for freshness tracking
- Use whatever units SolarEdge API returns, document them in model docstrings

### Hardware abstraction
- Auto-detect display backend: try importing e-ink driver, fall back to PNG if unavailable
- Debug PNG files saved to `./debug/` folder (gitignored)
- Verbose logging when rendering to PNG: "Rendered 250x122 to debug/screen_overview.png"
- No auto-open of PNG files — user opens manually

### Error handling
- API timeouts: retry 3 times with exponential backoff (2s, 4s, 8s)
- On complete failure: return None, continue polling (display shows stale data with "Offline" indicator)
- API client logs its own errors (warnings/errors), caller gets clean result or None
- HTTP timeout: 10 seconds per request

### Claude's Discretion
- Power flow dataclass structure (flat vs nested) — based on API response shape
- Energy data structure (separate vs combined with power flow) — based on how display uses it

</decisions>

<specifics>
## Specific Ideas

- Keep API module name specific (`solaredge_api.py`) to leave room for other service integrations (car, weather)
- Display shows stale data marked with "Offline" message when API unavailable, rather than blank screen

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-architecture-data-layer*
*Context gathered: 2026-02-06*
