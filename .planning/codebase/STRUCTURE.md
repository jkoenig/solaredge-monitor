# Codebase Structure

**Analysis Date:** 2026-02-04

## Directory Layout

```
solaredge-offgrid-monitor/
├── se-overview.py              # Main application entry point
├── se-monitor2.py              # Alternative monitor script (legacy)
├── se-monitor.old.py           # Archived version
├── epd_2in13_V3_test.py        # Hardware display testing utility
├── lib/                        # Third-party and hardware libraries
│   └── waveshare_epd/          # E-ink display drivers (60+ device models)
│       ├── epd2in13_V3.py      # 2.13" e-ink display driver (primary)
│       ├── epd7in5bc.py        # 7.5" e-ink display driver
│       ├── DEV_Config_32.so    # 32-bit hardware abstraction binary
│       ├── DEV_Config_64.so    # 64-bit hardware abstraction binary
│       └── [50+ other EPD drivers...]
├── weconnect/                  # VW WeConnect vehicle integration
│   ├── wci.py                  # WeConnect OAuth and API client
│   ├── credentials.py          # VW account credentials (SECRETS)
│   ├── example.py              # Example usage of WeConnect API
│   └── example-with-cache.py   # Example with response caching
├── fonts/                      # TrueType fonts for display rendering
│   ├── Arial.ttf               # Regular font
│   ├── ArialBlack.ttf          # Bold font
│   └── FontAwesome6-Free-Solid-900.otf  # Icon font (battery, grid, plug icons)
├── debug/                      # API response logging and screenshots
│   ├── solaredge-site-overview-results.txt        # SolarEdge API responses
│   ├── solaredge-energyDetails-results.txt        # Energy meter data
│   ├── solaredge-currentPowerFlow-results.txt     # Power flow snapshots
│   └── weconnect-vehicle-charging-results.txt     # Vehicle state logs
├── display/                    # Screenshot and reference images
│   ├── 2-13inch-EInk-overview.png                 # Production/consumption view
│   ├── 2-13inch-EInk-power-flow.png               # Battery status display
│   ├── 2-13inch-EInk-grid-state.png               # ON/OFF grid indicator
│   ├── 2-13inch-EInk-timemachine-disk-usage.png   # Disk capacity view
│   ├── 2-13inch-EInk-weconnect-vehicle-charging.png  # VW charging state
│   ├── 2-13inch-EInk-bmw-i3s-charging.png         # BMW charging state
│   └── solaredge-logo.png                         # Logo asset
└── .planning/                  # GSD planning documents
    └── codebase/               # Architecture and structure docs
```

## Directory Purposes

**Root Directory:**
- Purpose: Python application entry points and configuration
- Contains: Three monitor scripts with different display layouts
- Key files: `se-overview.py` (primary), `se-monitor2.py` (legacy), test utilities

**`lib/waveshare_epd/`:**
- Purpose: Hardware abstraction for 60+ e-ink display models
- Contains: Device drivers (one Python module per display model), compiled C binaries for GPIO/SPI
- Key files: `epd2in13_V3.py` (active), others for compatibility
- Committed: Yes (third-party library)
- Generated: No

**`weconnect/`:**
- Purpose: VW vehicle API integration and authentication
- Contains: OAuth client implementation, credentials, example usage
- Key files: `wci.py` (WeConnectId class), `credentials.py` (secrets)
- Committed: Yes (custom implementation)
- Generated: No

**`fonts/`:**
- Purpose: TrueType font files for display rendering
- Contains: Arial font variants (regular/bold) + FontAwesome icon set
- Key files: `ArialBlack.ttf`, `FontAwesome6-Free-Solid-900.otf`
- Committed: Yes (binary assets)
- Generated: No

**`debug/`:**
- Purpose: API response logging and debug output
- Contains: Text logs of API responses, saved for troubleshooting
- Key files: SolarEdge/WeConnect response snapshots
- Committed: No (generated at runtime)
- Generated: Yes (append-only when `debug=True`)

**`display/`:**
- Purpose: Screenshot storage and visual reference
- Contains: PNG images of each display screen state, logo
- Key files: Screen captures matching display function outputs
- Committed: Yes (reference images)
- Generated: Partially (updated when debug mode saves screenshots)

## Key File Locations

**Entry Points:**
- `se-overview.py`: Primary application (runs in cron loop 6:00-24:00 hourly)
- `se-monitor2.py`: Alternative version with different display arrangement
- `epd_2in13_V3_test.py`: Hardware test utility (verify EPD communication)

**Configuration:**
- Top of `se-overview.py` (lines 32-62): Credentials, API keys, site IDs, hardware parameters
  - SolarEdge: `api_key`, `site_id`
  - WeConnect: `we_connect_email_address`, `we_connect_password`, `we_connect_vin`
  - BMW: `bmw_email_address`, `bmw_password`, `bmw_vin`
  - Hardware: `scale_factor=4`, `original_width=250`, `original_height=122`

**Core Logic:**
- `se-overview.py` (lines 69-829): Data fetching and display rendering
- `weconnect/wci.py` (lines 1-90): WeConnect OAuth client implementation
- `lib/waveshare_epd/epd2in13_V3.py`: Display driver with init/clear/display methods

**Testing:**
- `epd_2in13_V3_test.py`: Hardware initialization test
- `weconnect/example.py`: WeConnect API usage example
- `weconnect/example-with-cache.py`: Cached response example

## Naming Conventions

**Files:**
- Main monitors: `se-{descriptor}.py` (e.g., `se-overview.py`, `se-monitor2.py`)
- API modules: `{service}-{descriptor}.py` or class-based (e.g., `wci.py` for WeConnect)
- Test scripts: `{hardware}_{version}_test.py` (e.g., `epd_2in13_V3_test.py`)
- Drivers: `epd{width}in{height}{variant}.py` (e.g., `epd2in13_V3.py`)
- Log files: `{service}-{data_type}-results.txt` (e.g., `solaredge-energyDetails-results.txt`)

**Directories:**
- Third-party libraries: `lib/`
- External API clients: Named by service (`weconnect/`)
- Assets: Named by type (`fonts/`, `display/`)
- Utilities: Named by purpose (`debug/`)

**Functions:**
- Data fetchers: `get_{resource}()` (e.g., `get_site_overview()`, `get_current_power_flow()`)
- Display renderers: `display[N]()` where N is sequence order (display, display2-display6)
- Utilities: snake_case (e.g., `to_camel_case()`, `get_free_disk_space_of_timemachine()`)

**Variables:**
- Global config: UPPERCASE or camelCase (e.g., `api_key`, `scale_factor`, `original_width`)
- Local vars: snake_case (e.g., `energy_details`, `storage_status`, `usage_percentage`)
- Font objects: `font{size}` or `icon` (e.g., `font24`, `font30`, `icon`)

**Types:**
- Returned data: Tuples/lists (e.g., `results = [lastUpdateTime, lifeTimeEnergy, ...]`)
- Strings vs numbers: Mixed (no strict type enforcement, relies on API contracts)

## Where to Add New Code

**New Feature (e.g., add new vehicle type):**
- Primary code: `se-overview.py` - add new `get_*_state_of_charge()` function following pattern of `get_bmw_state_of_charge()` (lines 332-371)
- Display function: Add new `displayN()` function (increment N) with rendering logic
- Integration: Add lambda to `functions` list in `__main__` (line 813-820)
- Tests: Create vehicle-specific test in root or `weconnect/example.py`

**New Display Screen:**
- Implementation: `se-overview.py` - new `displayN()` function (follow pattern of existing display functions 373-808)
  - Init EPD hardware or use debug mode image save
  - Create high-res PIL Image object
  - Calculate text positions for centering (see display2/display3 for math)
  - Render icons from FontAwesome, text with fonts, scale down
- Data source: Call existing `get_*()` or create new one if needed
- Integration: Add lambda to `functions` list

**New Data Source (external API):**
- Implementation: `se-overview.py` - new `get_*()` function
- Pattern: Try-except wrapper, return list/tuple of processed values
- Error handling: Return all-"n/a" list on failure (see line 330, 371)
- Logging: Use `logging.info()` for progress, `logging.error()` for issues
- Debug output: Optional append to debug log file if needed

**New Device Driver:**
- Location: `lib/waveshare_epd/epd{W}in{H}{variant}.py`
- Template: Copy from similar model in same directory, update GPIO pins and register addresses
- Integration: Import in display function as needed (currently hardcoded to epd2in13_V3)

**Utilities:**
- Shared helpers: `se-overview.py` module-level functions (e.g., `to_camel_case()` at line 69)
- VW-specific utilities: `weconnect/wci.py` (WeConnectId class)
- Hardware utilities: Class methods in `lib/waveshare_epd/` drivers

## Special Directories

**`debug/`:**
- Purpose: Append-only API response logging for troubleshooting
- Generated: Yes (created at runtime)
- Committed: No (should be in `.gitignore`)
- Content: Text files with timestamped JSON responses from SolarEdge, WeConnect APIs
- Usage: Check when API structure changes break parsing

**`display/`:**
- Purpose: Visual reference and debug screenshot storage
- Generated: Partially (updated when `debug=True` and display functions run)
- Committed: Yes (reference images for documentation)
- Content: PNG files matching each display function output
- Usage: Verify rendering on target hardware matches screenshots

**`lib/waveshare_epd/__pycache__/`:**
- Purpose: Python bytecode cache
- Generated: Yes (automatic at runtime)
- Committed: No (should be in `.gitignore`)
- Content: .pyc and .so compiled modules

---

*Structure analysis: 2026-02-04*
