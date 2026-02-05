# Architecture

**Analysis Date:** 2026-02-04

## Pattern Overview

**Overall:** Monolithic Script-Based Architecture with External API Integration

**Key Characteristics:**
- Single entry point (`se-overview.py`) executing modular display functions in sequence
- Data fetching from multiple external APIs (SolarEdge, WeConnect, BMW)
- Rendering results to e-ink display hardware via Waveshare library
- Time-controlled execution loop (6:00-24:00 hours)
- No persistent state management or database layer

## Layers

**API Integration Layer:**
- Purpose: Fetch real-time data from external services
- Location: `se-overview.py` functions: `get_site_overview()`, `get_energy_details()`, `get_current_power_flow()`, `get_vw_state_of_charge()`, `get_bmw_state_of_charge()`, `get_free_disk_space_of_timemachine()`
- Contains: HTTP requests to SolarEdge REST API, WeConnect vehicle API via `weconnect/wci.py`, BMW MyBMWAccount SDK, SSH/Paramiko for remote disk queries
- Depends on: `requests`, `weconnect.wci`, `bimmer_connected`, `paramiko`
- Used by: Main event loop, display functions

**Data Processing Layer:**
- Purpose: Transform and aggregate API responses into display-ready data structures
- Location: Within each `get_*()` function in `se-overview.py` (lines 74-372)
- Contains: Unit conversions (kWh to MWh), percentage calculations, state parsing from JSON responses
- Depends on: API layer output
- Used by: Display rendering layer

**Hardware Abstraction Layer:**
- Purpose: Abstract e-ink display hardware communication
- Location: `lib/waveshare_epd/` - contains EPD device drivers (`epd2in13_V3.py` and 60+ others)
- Contains: Device-specific initialization, image buffering, display update methods
- Depends on: PIL Image library, hardware GPIO via DEV_Config binaries
- Used by: Display rendering layer

**Display Rendering Layer:**
- Purpose: Create visual layouts and render to e-ink display
- Location: `se-overview.py` functions: `display()`, `display2()` through `display6()`
- Contains: Image creation (PIL), text positioning calculations, font management, icon rendering via FontAwesome
- Depends on: Hardware abstraction layer, PIL, font files from `fonts/`
- Used by: Main event loop

**Configuration Layer:**
- Purpose: Centralize credentials and parameters
- Location: Top of `se-overview.py` (lines 32-62): API keys, site IDs, credentials, mount points, display scaling
- Contains: Hard-coded secrets, hardware parameters (scale_factor=4, 250x122 display size), timing (sleep_timer=180)
- Depends on: None (loaded at module initialization)
- Used by: All other layers

## Data Flow

**Main Execution Cycle:**

1. **Initialization** (lines 810-820)
   - Load credentials and configuration
   - Load fonts and create imaging objects
   - Create lambda function list for display sequence

2. **Time Check** (line 824)
   - Query current hour
   - Skip execution between 00:00-06:00 (rest period)

3. **API Data Fetch** (per display cycle)
   - Call `get_site_overview()` → Returns 10-element list [lastUpdateTime, lifeTimeEnergy, lifeTimeRevenue, ...]
   - Call `get_energy_details()` → Returns 5-element list [self_consumption, consumption, production, feed_in, purchased]
   - Call `get_current_power_flow()` → Returns 7-element list [grid_power, load_power, pv_power, storage_status, storage_power, soc, off_grid_bool]
   - Call `get_vw_state_of_charge()` → Returns 8-element list from WeConnect vehicle API
   - Call `get_bmw_state_of_charge()` → Returns 4-element list from BMW API
   - Call `get_free_disk_space_of_timemachine()` → Returns string via SSH

4. **Display Rendering** (sequentially with 180-second delays)
   - `display()` → Overview grid with production/consumption bar chart
   - `display2()` → Centered battery charge level (Hausakku)
   - `display3()` → Grid state (ON/OFF)
   - `display4()` → Time Machine disk usage
   - `display5()` → VW e-Golf charging state (Gisela)
   - `display6()` → BMW i3s charging state

5. **Hardware Output**
   - Image scaled to 4x resolution for rendering quality
   - Scaled back to 250x122 native display size
   - Sent to EPD hardware via `epd.display(epd.getbuffer(image))`
   - 2-second hardware latency between displays

**State Management:**
- No persistent state between cycles
- Each 180-second cycle fetches fresh API data
- Display parameters calculated fresh from API responses (percentages, conversions)
- Global variables: `original_width`, `original_height`, font objects

## Key Abstractions

**API Response Wrapper:**
- Purpose: Normalize diverse API responses into consistent tuple/list format
- Examples: `get_site_overview()` returns 10-element list, `get_energy_details()` returns 5-element list
- Pattern: Extract nested JSON paths, perform unit conversions, return as simple tuples for display functions

**Display Function Pattern:**
- Purpose: Encapsulate rendering logic for each display screen
- Examples: `display()`, `display2()` through `display6()`
- Pattern: Accept data tuple, create PIL Image object, calculate text positioning for centering, render icons and text, optionally save debug PNG

**Hardware Device Abstraction:**
- Purpose: Provide consistent interface to different e-ink display models
- Examples: Classes in `lib/waveshare_epd/` (EPD class per model: epd2in13_V3, epd7in5bc, etc.)
- Pattern: init(), clear(), display(buffer), with consistent method signatures across 60+ device drivers

## Entry Points

**Main Script:**
- Location: `se-overview.py`
- Triggers: System cron or manual execution
- Responsibilities: Load config, fetch all API data, render 6 display screens in sequence, sleep 180 seconds, repeat 6:00-24:00

**Test/Debug Script:**
- Location: `epd_2in13_V3_test.py`
- Triggers: Manual execution for hardware testing
- Responsibilities: Test e-ink display communication without API fetches

**Alternative Monitor:**
- Location: `se-monitor2.py`
- Triggers: Legacy version (not actively maintained)
- Responsibilities: Similar to se-overview.py but with different display layout (uses epd2in13_V3 specifically)

## Error Handling

**Strategy:** Try-except wrapping with fallback values

**Patterns:**
- API failures: Return default values ("n/a" strings or empty lists) to prevent cascade failures
- Missing device: Catch `ModuleNotFoundError` when Waveshare EPD not available, return without display
- Soft failures: Log errors via logging module but continue execution loop
- SSH timeouts: Return "n/a" for disk usage if Paramiko connection fails (line 284-285)

**Specific Examples:**
- `get_site_overview()` (line 128-129): Catches all exceptions, returns None implicitly
- `get_bmw_state_of_charge()` (line 369-371): Returns ["n/a","n/a","n/a","n/a"] on any error
- Display functions (e.g., line 459-460): Catch and log errors but continue to next display cycle

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` module with DEBUG level
- Pattern: `logging.info()` for progress updates, `logging.error()` for failures
- Configuration: Set at module load (line 30): `logging.basicConfig(level=logging.DEBUG)`

**Validation:**
- Approach: Minimal validation; assumes API responses are well-formed
- Pattern: Direct dictionary key access without existence checks (e.g., line 88: `data["overview"]["lastUpdateTime"]`)
- Risk: KeyError if API response structure changes unexpectedly

**Authentication:**
- Credentials stored as module-level constants (lines 32-44)
- SolarEdge: API key in query string
- WeConnect: Email/password with token refresh via `wci.WeConnectId` class (handles OAuth flow internally)
- BMW: Email/password with SDK-managed session (bimmer_connected library)
- Paramiko SSH: Username/password for Time Machine remote

**Timing:**
- Main loop sleep: 180 seconds between display cycles
- Hardware display latency: 2 seconds between EPD updates
- Time gating: Only execute 06:00-24:00 (skip 00:00-06:00)
- No request rate limiting on external APIs

---

*Architecture analysis: 2026-02-04*
