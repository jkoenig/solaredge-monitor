# External Integrations

**Analysis Date:** 2026-02-04

## APIs & External Services

**Energy Monitoring:**
- SolarEdge API - Real-time solar production and power flow data
  - SDK/Client: `requests` library with direct REST calls
  - Auth: API key (hardcoded in `se-overview.py` line 32)
  - Endpoints used:
    - `/site/{site_id}/overview` - Daily energy stats (line 77)
    - `/site/{site_id}/energyDetails` - Detailed meter breakdown (line 136)
    - `/site/{site_id}/currentPowerFlow` - Real-time power distribution (line 201)

**Vehicle Integration - BMW:**
- BMW ConnectedDrive API - Vehicle battery state and charging status
  - SDK/Client: `bimmer_connected` library (imported line 27)
  - Auth: Email/password (hardcoded in `se-overview.py` lines 42-44)
  - Authentication: REST_OF_WORLD region via `Regions.REST_OF_WORLD` (line 337)
  - Methods:
    - `MyBMWAccount.get_vehicles()` - Retrieve vehicle list (line 338)
    - `Vehicle.fuel_and_battery` - Battery percentage, range, charging status (line 344)
  - VIN: `[REDACTED-VIN]` (hardcoded)

**Vehicle Integration - Volkswagen (WeConnect):**
- VW WeConnect API - ID vehicle battery and charging state
  - SDK/Client: Custom `weconnect.wci` module (location: `weconnect/wci.py`)
  - Auth: Email/password via OAuth-style login flow (hardcoded in `se-overview.py` lines 38-40)
  - Base URL: `https://emea.bff.cariad.digital/vehicle/v1` (weconnect/wci.py line 8)
  - Endpoints:
    - `/vehicles/{vin}/selectivestatus?jobs=charging` - Charging state (line 291)
  - VIN: `[REDACTED-VIN]` (hardcoded)
  - Data retrieved: charging state, SOC %, range, plug status, LED color

## Data Storage

**Databases:**
- None (all data is ephemeral or cached in-memory during execution)

**File Storage:**
- Local filesystem only
  - Debug files: `debug/solaredge-*.txt`, `debug/weconnect-*.txt` (append-only logs)
  - Display images: `display/*.png` (PNG output from e-ink rendering)
  - Fonts: `fonts/` directory (TrueType fonts, FontAwesome icons)

**Caching:**
- None persistent - data cached in-memory during function execution
- SolarEdge data cached in lists/tuples returned from `get_site_overview()`, `get_energy_details()`, `get_current_power_flow()` (lines 74-254)
- Vehicle data cached during session lifetime of vehicle API clients

## Authentication & Identity

**Auth Provider:**
- Custom implementations (no OAuth2 framework used)
- VW WeConnect: OAuth-like flow with redirect URI `weconnect://authenticated` (weconnect/wci.py line 14)
- BMW: Direct email/password via bimmer_connected library
- SolarEdge: Static API key in query parameters
- SSH: Basic username/password authentication to `timemachine.local` (line 257)

**Credential Management:**
- All credentials hardcoded in script files (security risk)
  - `se-overview.py` lines 32-45: All API keys, emails, passwords, VINs
  - `se-monitor2.py` lines 23-31: Duplicate credentials
  - No environment variable support detected
  - No external secret management (Vault, .env files, etc.)

## Monitoring & Observability

**Error Tracking:**
- None (no dedicated error tracking service)

**Logs:**
- Python `logging` module at DEBUG level (line 30)
- Output: Console and optional file writes to `debug/` directory
- SolarEdge responses: Logged to `debug/solaredge-site-overview-results.txt` (lines 81-83)
- WeConnect responses: Logged to `debug/weconnect-vehicle-charging-results.txt` (lines 295-298)
- Power flow responses: Logged to `debug/solaredge-currentPowerFlow-results.txt` (lines 204-207)

## CI/CD & Deployment

**Hosting:**
- Local execution on Raspberry Pi (ARMv7/ARMv8)
- No cloud deployment detected

**CI Pipeline:**
- None detected (no GitHub Actions, Jenkins, etc.)

**Execution Model:**
- Daemon process running indefinitely in loop (lines 822-828 in `se-overview.py`)
- Update frequency: 180 seconds (3 minutes) between API calls via `sleep_timer`
- Time-gated execution: Only runs between 06:00 and 24:00 hours (line 824)
- Typical deployment: `systemd` service or `cron` on Raspberry Pi

## Environment Configuration

**Required env vars:**
- None (all configuration hardcoded)

**Required credentials:**
- SolarEdge API key: `[REDACTED-API-KEY]`
- SolarEdge Site ID: `[REDACTED-SITE-ID]`
- SSH hostname: `timemachine.local`
- SSH username: `pi`
- SSH password: `[REDACTED-PASSWORD]`
- SSH mount point: `/mnt/backups`
- VW WeConnect email: `[REDACTED-EMAIL]`
- VW WeConnect password: `[REDACTED-PASSWORD]`
- VW WeConnect VIN: `[REDACTED-VIN]`
- BMW email: `[REDACTED-EMAIL]`
- BMW password: `[REDACTED-PASSWORD]`
- BMW VIN: `[REDACTED-VIN]`

**Secrets location:**
- Hardcoded in source files (SECURITY ISSUE)

## Webhooks & Callbacks

**Incoming:**
- None (application is pull-only)

**Outgoing:**
- None (application reads data only, does not send notifications or callbacks)

## Data Flow Summary

```
┌─────────────────────┐
│  SolarEdge Cloud    │─ REST API calls every 180s
│  (overview, power)  │  → retrieve energy production/consumption/power flow
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   se-overview.py    │
│  Main coordinator   │ ◄─ VW WeConnect API
└──────────┬──────────┘      OAuth login + vehicle status
           │
           ├─ SSH to timemachine.local ─────► disk usage check
           │
           ├─ Render display1 ──────┐
           ├─ Render display2 (SOC) ├──► Waveshare 2.13" e-ink
           ├─ Render display3 (Grid)│     (GPIO SPI)
           ├─ Render display4 (Disk)│
           ├─ Render display5 (VW)  │
           └─ Render display6 (BMW) ◄──── bimmer_connected API

Debug output → append to debug/*.txt files
Display output → display/*.png + e-ink rendering
```

---

*Integration audit: 2026-02-04*
