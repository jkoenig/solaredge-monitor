# Codebase Concerns

**Analysis Date:** 2026-02-04

## Security Concerns

**Hardcoded Credentials:**
- Issue: All API keys, passwords, and credentials are embedded directly in source code
- Files: `se-overview.py` (lines 32-44), `se-monitor2.py` (lines 23-31)
- Impact: Credentials are exposed in version control history and any code repository access. This includes:
  - SolarEdge API key: `[REDACTED-API-KEY]`
  - WeConnect email and password for VW vehicle
  - BMW email and password
  - SSH credentials for time machine backup server (pi@timemachine.local)
- Remediation: Move all credentials to environment variables or a `.env` file (added to `.gitignore`). Use `os.environ.get()` to load at runtime.

**SSH with Known Credentials:**
- Issue: SSH credentials passed in plain function calls without verification
- Files: `se-overview.py` (lines 256-285), `se-monitor2.py` (lines 217-245)
- Impact: SSH connections use hardcoded credentials. No host key verification besides auto-add policy.
- Remediation: Use SSH key authentication instead of passwords. Implement proper host key verification.

## Tech Debt

**Code Duplication Across Files:**
- Issue: Significant duplication between `se-overview.py` (828 lines) and `se-monitor2.py` (620 lines)
- Files:
  - `se-overview.py` - Main production code (or intended to be)
  - `se-monitor2.py` - Appears to be an earlier version with similar functionality
  - `se-monitor.old.py` - Archived version
- Impact: Maintenance burden - bug fixes or feature updates must be applied to multiple files. Risk of inconsistency between versions.
- Content overlap:
  - `get_site_overview()` - nearly identical
  - `get_energy_details()` - nearly identical
  - `get_current_power_flow()` - nearly identical
  - `get_free_disk_space_of_timemachine()` - identical
  - `get_vw_state_of_charge()` - identical
  - Multiple `displayN()` functions with repeated logic
- Remediation: Consolidate into single main file. Move common functions to shared module.

**Monolithic Script Design:**
- Issue: All code is in a single 828-line script with mixed concerns (API calls, display rendering, SSH operations, data processing)
- Files: `se-overview.py`
- Impact:
  - Difficult to test individual components
  - Hard to reuse functions in other projects
  - Display logic, API logic, and system operations all tightly coupled
- Remediation: Refactor into modules: `api_client.py`, `display_renderer.py`, `system_utils.py`, with main orchestration in `monitor.py`

**Global Variables:**
- Issue: Heavy reliance on module-level globals that are set once and used throughout
- Files: `se-overview.py` (lines 32-62), `se-monitor2.py` (lines 23-35)
- Examples: `api_key`, `site_id`, `hostname`, `username`, `password`, `we_connect_email_address`, scale factors, font definitions
- Impact: Functions are not self-contained, harder to test, state is implicit
- Remediation: Pass configuration as parameters or load from config class/dataclass

**Font Initialization on Module Load:**
- Issue: All fonts loaded at module level during import
- Files: `se-overview.py` (lines 53-62)
- Impact:
  - If any font file is missing, entire module fails to import
  - Font paths are hardcoded with assumptions about working directory
  - Scale factor coupled to global state
- Remediation: Lazy-load fonts, implement proper font manager class with error handling

## Known Issues

**TODO: Battery Icon Index Out of Range (100% Battery):**
- Location: `se-overview.py` line 489
- Problem: When state of charge is 100%, the calculated index becomes 4, but battery_levels array only has indices 0-4. The comment explicitly states "100% icon does not work, when index = 4"
- Trigger: Battery state of charge = 100%
- Current code:
  ```python
  battery_levels = ["\uF244", "\uF243", "\uF242", "\uF241", "\u1F50B"]
  index = int(state_of_charge / (100 / (len(battery_levels) - 1)))
  # TODO: 100% icon does not work, when index = 4
  ```
- Actual impact: Index 4 exists, so probably no crash, but icon may render incorrectly
- Fix approach: Cap index to len(battery_levels) - 1, or adjust calculation to prevent reaching 4

**API Response Assumes Data Exists:**
- Issue: No validation that API responses contain expected fields before accessing nested values
- Files: `se-overview.py` (lines 86-110), `se-monitor2.py` (lines 49-74)
- Impact: If API response is incomplete or error format, KeyError will occur and caught as generic Exception
- Examples:
  - `data["overview"]["lastUpdateTime"]` accessed directly without checking if "overview" key exists
  - `data['energyDetails']['meters']` accessed without confirming meters list exists
  - `response_data["siteCurrentPowerFlow"]["GRID"]["currentPower"]` deeply nested access

**Infinite Loop Without Proper Shutdown:**
- Location: `se-overview.py` (lines 822-828), `se-monitor2.py` (lines 618-621)
- Problem: While loop with only time.sleep() between iterations. No graceful shutdown mechanism beyond KeyboardInterrupt on display functions.
- Impact: Process cannot be stopped cleanly by external signals (except keyboard interrupt). No cleanup of SSH connections, API clients, or hardware resources.
- Trigger: Running monitor continuously
- Remediation: Implement signal handlers for SIGTERM/SIGINT, context managers for resource cleanup

**Hardcoded Display Hardware Class:**
- Location: `se-overview.py` (line 378), `se-monitor2.py` (line 294)
- Problem: Hardcoded import of `epd2in13_V3.EPD()` only. No support for different display hardware without code changes.
- Impact: Cannot use different display devices without modifying code and redeploying
- Remediation: Implement display factory pattern, read device type from configuration

## Error Handling Gaps

**Bare Exception Catches with Minimal Response:**
- Files: `se-overview.py`, `se-monitor2.py` throughout
- Pattern: `except Exception as e: print(f"An error occurred: {e}")`
- Issues:
  - No error categorization (network error vs API error vs missing file)
  - No recovery strategy (retry, fallback, skip)
  - No logging to persistent storage
  - May catch and hide unexpected errors (programmer mistakes, not just runtime issues)
- Examples in `se-overview.py`:
  - Line 128-129: `get_site_overview()` catches all exceptions
  - Line 195-196: `get_energy_details()` catches all exceptions
  - Line 253-254: `get_current_power_flow()` catches all exceptions
  - Line 369-371: `get_bmw_state_of_charge()` catches all exceptions

**Missing Return Value Handling:**
- Location: Throughout both scripts
- Problem: Functions return data to display functions, but display functions never validate input
- Examples:
  - `display()` receives list from `get_energy_details()` but doesn't verify correct number of elements
  - `display2()` through `display6()` all assume received data is complete
  - If API call fails, error handler returns `["n/a","n/a",...]` list, but display code still tries to use as numbers

**API Rate Limiting Not Handled:**
- Issue: No backoff or rate limiting for API calls
- Files: `se-overview.py` (get_site_overview, get_energy_details, get_current_power_flow)
- Impact: SolarEdge API enforces rate limits. Continuous hammering could result in 403/429 responses with no recovery strategy
- Remediation: Implement exponential backoff, cache responses, respect Retry-After headers

## Performance Bottlenecks

**Synchronous SSH Operations:**
- Location: `se-overview.py` (lines 256-285)
- Problem: SSH connection happens during main loop, blocks all other operations while waiting for response
- Impact: If time machine is slow or unreachable, 30+ second hang in display loop
- Trigger: `get_free_disk_space_of_timemachine()` in main loop
- Remediation: Run SSH operations in separate thread or async context, implement timeout

**Multiple Redundant Display Cycles:**
- Location: `se-overview.py` (lines 813-829)
- Problem: Each function calls display independently. Functions are called sequentially with sleep between each.
  - `display6()` - BMW charge state
  - `display3()` - On/off grid
  - `display5()` - VW charge state
  - `display2()` - House battery
  - `display()` - Energy overview
  - `display4()` - Disk usage
- Impact:
  - Each cycle makes ~6 API calls (site_overview, energy_details, power_flow called multiple times)
  - With 180-second sleep between functions, full cycle takes ~18 minutes
  - VW and BMW APIs called every 3 minutes even if vehicle is unplugged
- Remediation: Batch API calls, cache results for 5-10 minutes, update display based on data change not on timer

**Repeated Font Loading Per Display:**
- Location: `se-overview.py` (lines 374-387, 466-477, etc.)
- Problem: `se-monitor2.py` reloads fonts on EVERY display() call instead of caching at module level
- Impact: File I/O for font loading happens 6 times per cycle
- Remediation: Load fonts once at startup, store in instance or module cache

## Fragile Areas

**Display Position Hardcoding:**
- Location: `se-overview.py` (lines 1-70 and throughout display functions)
- Problem: All pixel coordinates are hardcoded magic numbers scattered throughout display functions
- Impact:
  - Changing layout requires finding dozens of magic numbers
  - No reusable layout system
  - Hard to test display logic
  - Easy to introduce off-by-one alignment errors
- Remediation: Create layout configuration objects or use a templating system

**Icon/Unicode Character Assumptions:**
- Location: `se-overview.py` (lines 486, 554, 685, 762), `se-monitor2.py` (line 397, etc.)
- Problem: Unicode characters for FontAwesome icons hardcoded as escape sequences
- Examples: `"\uF244"`, `"\uE55B"`, `"\u1F50B"`
- Impact:
  - No mapping of what each character represents
  - If font version changes, icons may change or disappear
  - Hard to audit which icons are used
- Remediation: Create icon registry/mapping with named constants

**Regex/String Parsing Fragile to API Changes:**
- Location: `se-overview.py` (line 225-235) - relies on string comparison
- Problem: Code checks `if from_device.lower() == "grid"` but API could change case or spelling
- Impact: Logic for detecting off-grid state could fail silently if API changes format
- Remediation: Add API response validation/schema, create constants for expected values

**BMW Integration Incomplete:**
- Location: `se-overview.py` (lines 332-371)
- Problem:
  - Uses global `account` variable with NameError check (lines 334-338)
  - Assumes account persists across function calls
  - No connection pooling or session reuse
  - Returns different tuple structure (4 elements) vs VW (8 elements)
- Impact: Inconsistent data structures, difficult to extend, fragile state management
- Remediation: Implement API client class with proper session management

## Test Coverage Gaps

**No Automated Tests:**
- Issue: No test directory, no test framework, no unit tests
- Impact: Refactoring is risky. Cannot verify fixes for reported issues.
- Files affected: All `.py` files in main directory

**Display Logic Untested:**
- Issue: Image rendering and layout has no validation
- Impact: UI changes could break display without detection. The TODO bug at line 489 went unnoticed.

**API Response Handling Untested:**
- Issue: No mock tests for API failures or unexpected responses
- Impact: Unknown how code behaves with missing fields, rate limits, or network errors

**Integration Untested:**
- Issue: No integration tests for SSH, API chaining, or full cycle
- Impact: Unknown if complete monitor cycle works end-to-end

## Scaling Limits

**Single-Device Display Only:**
- Limitation: Hardcoded to specific 2.13" e-ink display model (`epd2in13_V3`)
- Impact: Cannot add multiple displays or different device types without code modification
- Scaling path: Implement display abstraction/factory

**Sequential Processing:**
- Limitation: All API calls happen one at a time, main loop blocks
- Impact: 18+ minute full cycle with 180-second sleeps. If any call is slow, entire cycle delays.
- Scaling path: Implement async/thread pool for concurrent API calls

**Credentials Storage:**
- Limitation: All credentials hardcoded. Cannot scale to multiple instances/configurations
- Impact: Each deployment requires code modification. Cannot use in CI/CD without exposing secrets.
- Scaling path: Move to environment variables, secrets manager, or configuration files

## Dependencies at Risk

**WeConnect Library Usage:**
- Package: `weconnect` (imported from local `weconnect/` directory)
- Risk: Local import suggests either outdated or modified version
- Impact: Unknown if this matches current WeConnect API
- Status: Need to verify version compatibility

**Bimmer Connected Library:**
- Package: `bimmer_connected`
- Risk: Only used for BMW integration, requires setup but only called in one place
- Status: Initialization pattern is fragile (global account variable with NameError check)

**Paramiko SSH Library:**
- Package: `paramiko`
- Risk: No version pinning, SSH with passwords
- Status: Should use key-based auth or async SSH

**Pillow Image Library:**
- Package: `PIL/Pillow`
- Status: Standard, but version should be pinned

**Font Files:**
- Risk: FontAwesome OTF file path hardcoded, file must exist at runtime
- Status: No fallback if font missing

## Configuration Management

**No Configuration File:**
- Issue: All configuration is hardcoded in Python files
- Impact: Cannot change behavior without code modification
- Examples that should be configurable:
  - API keys and credentials
  - Sleep interval (180 seconds)
  - Display device type
  - SSH host/username/password
  - Font paths
  - Display refresh sequence
- Remediation: Create `config.yaml` or `.env` file with all settings

**Inconsistent Between Versions:**
- Issue: `se-overview.py` and `se-monitor2.py` have different defaults:
  - `se-overview.py`: debug = False (line 3)
  - `se-monitor2.py`: debug = True (line 35)
  - Function call sequences differ: `se-overview.py` includes BMW and disk usage; `se-monitor2.py` includes only VW and disk usage

## Code Quality Issues

**Mixed German and English:**
- Locations: `se-overview.py` has German comments mixed with English
- Examples: "Verbrauch" (consumption), "Von Sonne" (from sun), "Ins Netz" (into grid)
- Impact: Hard to maintain for non-German speakers, inconsistent documentation style

**Inconsistent Naming Conventions:**
- Functions use snake_case (correct) but inconsistent abbreviations:
  - `get_bmw_state_of_charge()` vs `get_vw_state_of_charge()` (brand before function)
  - `display2()` through `display6()` (numbered rather than descriptive names)
  - `se-overview.py` vs `se-monitor2.py` (unclear which is production)

**Commented-Out Code:**
- Location: `se-overview.py` (lines 750-755) - commented result array in display6()
- Impact: Dead code accumulation, confusing maintenance

**Magic Numbers:**
- Throughout display functions: pixel positions (92, 175, 225), scale factors (4), timeouts (sleep(2))
- No named constants for these values

---

*Concerns audit: 2026-02-04*
