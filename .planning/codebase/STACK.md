# Technology Stack

**Analysis Date:** 2026-02-04

## Languages

**Primary:**
- Python 3.9.5 - All application logic, API interactions, and display rendering

## Runtime

**Environment:**
- Python 3.9+ runtime for Raspberry Pi OS (Linux ARM)
- Runs as a long-running daemon process

**Package Manager:**
- pip (default Python package manager)
- No lockfile detected (manual dependency management)

## Frameworks & Libraries

**Core HTTP & API:**
- `requests` - HTTP client for REST API calls (SolarEdge API, BMW API)
- `asyncio` - Async I/O for BMW bimmer_connected library

**Image Processing & Display:**
- `Pillow (PIL)` - Image creation, drawing, font rendering
- `waveshare_epd` - Custom driver library for Waveshare 2.13" e-ink displays
  - Location: `lib/waveshare_epd/`
  - Includes display control, hardware SPI, GPIO management
  - Compiled binaries for 32-bit and 64-bit ARM (`.so` files)

**Vehicle Integration:**
- `bimmer_connected` - BMW vehicle API client (location: `lib/bimmer_connected/`)
  - Provides fuel and battery state, charging status
- `weconnect` - Custom VW WeConnect API wrapper (location: `weconnect/wci.py`)
  - Handles authentication and vehicle status for VW ID vehicles

**System Integration:**
- `paramiko` - SSH client for remote disk usage queries over SSH

**Logging:**
- Python standard `logging` module - Configured at DEBUG level

## Key Dependencies

**Critical:**
- `requests` [2.x] - REST API communication (SolarEdge, BMW, VW)
- `Pillow (PIL)` [8.x+] - Image rendering and font handling for e-ink display
- `paramiko` [2.x+] - SSH connection for remote Raspberry Pi disk queries
- `bimmer_connected` - BMW vehicle state and battery management
- `weconnect` (custom) - VW WeConnect API authentication and data retrieval

**Hardware:**
- Waveshare 2.13" e-ink display (2.13inch_V3) with SPI interface
- RPi GPIO pins: 17 (RST), 25 (DC), 8 (CS), 24 (BUSY), 18 (PWR), 10 (MOSI), 11 (SCLK)

**Display Assets:**
- TrueType fonts: `Arial.ttf`, `ArialBlack.ttf` (location: `fonts/`)
- FontAwesome 6 Free Solid 900 (`FontAwesome6-Free-Solid-900.otf`) for icons

## Configuration

**Environment:**
- No `.env` file detected
- Credentials and configuration hardcoded in main scripts:
  - `se-overview.py` (lines 32-46): SolarEdge API key, site ID, SSH credentials, VW/BMW account credentials
  - `se-monitor2.py` (lines 23-31): Identical credential configuration

**Build:**
- No build configuration files (pure Python)
- Direct script execution via `python se-overview.py`

## Platform Requirements

**Development:**
- Python 3.9+
- pip package manager
- Git (version control)
- Text editor/IDE

**Production:**
- Raspberry Pi (ARMv7 or ARMv8 architecture)
- Raspbian/Raspberry Pi OS (Linux)
- SPI interface enabled for display communication
- GPIO access (not running as root required - configured via sysfs)
- Network connectivity for API calls
- SSH access to remote Raspberry Pi (for disk usage monitoring)

**Hardware:**
- Raspberry Pi 3B+ or higher (tested on Pi hardware)
- Waveshare 2.13" e-ink display V3
- 3.3V SPI interface
- GPIO pins as defined in `lib/waveshare_epd/epdconfig.py`

## External API Requirements

**Endpoints:**
- `https://monitoringapi.solaredge.com/` - SolarEdge monitoring API
- `https://emea.bff.cariad.digital/` - VW WeConnect API (EU region)
- BMW ConnectedDrive API (via bimmer_connected library)

**Authentication:**
- SolarEdge: API key (hardcoded: `[REDACTED-API-KEY]`)
- VW WeConnect: Email/password credentials (hardcoded)
- BMW: Email/password credentials (hardcoded)
- SSH: Username/password for remote disk checks (hardcoded)

---

*Stack analysis: 2026-02-04*
