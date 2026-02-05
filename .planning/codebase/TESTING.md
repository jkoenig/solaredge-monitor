# Testing Patterns

**Analysis Date:** 2026-02-04

## Test Framework

**Runner:**
- No formal test framework (pytest, unittest, nose) detected
- No test runner configuration files (pytest.ini, tox.ini, setup.cfg)
- Tests are ad-hoc and manual

**Assertion Library:**
- None - no automated assertions in codebase

**Run Commands:**
- No automated test commands
- Testing done via manual script execution
- `epd_2in13_V3_test.py` run directly as `python epd_2in13_V3_test.py`

## Test File Organization

**Location:**
- Test files placed at root level alongside source code
- Example: `epd_2in13_V3_test.py` at `/Users/jean-pierrekoenig/Documents/Projects/solaredge-offgrid-monitor/`
- No dedicated test directory
- No separation between test and source

**Naming:**
- Pattern: `{module}_test.py`
- Example: `epd_2in13_V3_test.py`
- Files are executable scripts (shebang `#!/usr/bin/python`)

**Structure:**
```
solaredge-offgrid-monitor/
├── se-overview.py                # Main source
├── se-monitor2.py                # Alternative implementation
├── epd_2in13_V3_test.py          # Hardware test
└── .planning/codebase/           # Configuration docs
```

## Test Structure

**Test File Example:**

`epd_2in13_V3_test.py` is an integration test for e-ink display hardware:

```python
#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import logging
from waveshare_epd import epd2in13_V3
import time
from PIL import Image,ImageDraw,ImageFont
import traceback

logging.basicConfig(level=logging.DEBUG)

try:
    logging.info("epd2in13_V3 Demo")

    epd = epd2in13_V3.EPD()
    logging.info("init and Clear")
    epd.init()
    epd.Clear(0xFF)

    # Drawing on the image
    font15 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 15)
    font24 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 24)

    logging.info("1.Drawing on the image...")
    image = Image.new('1', (epd.height, epd.width), 255)
    draw = ImageDraw.Draw(image)

    # ... test operations ...

    logging.info("Clear...")
    epd.init()
    epd.Clear(0xFF)

    logging.info("Goto Sleep...")
    epd.sleep()

except IOError as e:
    logging.info(e)

except KeyboardInterrupt:
    logging.info("ctrl + c:")
    epd2in13_V3.epdconfig.module_exit(cleanup=True)
    exit()
```

**Patterns:**
- **Initialization:** Setup logging and import modules conditionally
- **Execution:** Sequential test steps with logging between each
- **Cleanup:** Explicit cleanup on KeyboardInterrupt (Ctrl+C)
- **Error Handling:** Try/except for IOError and keyboard interruption
- **Visual Verification:** Tests output images and display them

## Mocking

**Framework:** None - no mocking library used (unittest.mock, pytest-mock, etc.)

**Patterns:**
- No mock objects or fixtures
- Tests operate against real hardware (`epd2in13_V3.EPD()`)
- No stubbing of API calls in test suite
- Development mode uses debug flag for conditional behavior

Example conditional behavior:
```python
# From se-overview.py - conditional display based on debug flag
if debug == False:
    try:
        from waveshare_epd import epd2in13_V3
        epd = epd2in13_V3.EPD()
        epd.init()
        epd.Clear(0xFF)
    except ModuleNotFoundError as e:
        logging.error(f"Fehler beim Importieren des Waveshare EPD Moduls: {e}")
        return
else:
    image.show()  # Show in PIL image viewer instead
    image.save("display/2-13inch-EInk-overview.png")  # Save to file
```

**What to Mock:**
- Currently nothing is mocked - tests use real dependencies
- Future: Could mock `requests` for API calls to avoid network dependency
- Future: Could mock display hardware for headless testing

**What NOT to Mock:**
- Core business logic (energy calculations)
- Image drawing operations (visual correctness critical)
- Device initialization (hardware integration testing)

## Fixtures and Factories

**Test Data:**
- No test fixtures or factories
- Tests use real API responses
- Configuration values hardcoded in scripts

From `se-overview.py`:
```python
api_key = "[REDACTED-API-KEY]"
site_id = "[REDACTED-SITE-ID]"
hostname = "timemachine.local"
username = "pi"
password = "[REDACTED-PASSWORD]"
```

**Location:**
- Configuration at top of each module
- Debug files saved to: `debug/` directory
- Test images saved to: `display/` directory

## Coverage

**Requirements:**
- No coverage enforcement detected
- No .coveragerc file
- No coverage targets or thresholds

**View Coverage:**
- Not applicable - no automated coverage tools configured

## Test Types

**Unit Tests:**
- Not used
- No isolated function testing
- No test framework for unit testing

**Integration Tests:**
- Hardware integration test: `epd_2in13_V3_test.py`
- Tests e-ink display initialization, rendering, and display
- Sequential steps verify hardware integration
- Visual verification via image output to files and display viewer

**E2E Tests:**
- End-to-end test is the main script execution: `se-overview.py`
- Requires real hardware (e-ink display, SSH access, API credentials)
- Runs continuously in production with 180-second intervals
- Schedules execution between 6 AM and midnight

## Logging for Testing

**Framework:** Python's built-in `logging` module

**Debug Mode:**
- Global `debug` flag controls behavior:
  ```python
  debug = False  # set to True for local development
  ```

**API Response Capture:**
- When `debug = True`, API responses logged to files with timestamps
- Enables offline testing and debugging:
  - `debug/solaredge-site-overview-results.txt`
  - `debug/solaredge-energyDetails-results.txt`
  - `debug/weconnect-vehicle-charging-results.txt`

**Display Output:**
- Images saved to `display/` directory when in debug mode:
  - `display/2-13inch-EInk-overview.png`
  - `display/2-13inch-EInk-power-flow.png`
  - `display/2-13inch-EInk-grid-state.png`
  - `display/2-13inch-EInk-timemachine-disk-usage.png`
  - `display/2-13inch-EInk-weconnect-vehicle-charging.png`
  - `display/2-13inch-EInk-bmw-i3s-charging.png`

## Manual Testing Approach

Since no automated test framework exists, testing is done manually:

1. **Hardware Testing:**
   - Run `epd_2in13_V3_test.py` to verify display hardware
   - Visual inspection of rendered output
   - Verify cleanup on Ctrl+C

2. **Development Testing:**
   - Set `debug = True` in main script
   - Run with `python se-overview.py`
   - Verify output images in `display/` directory using image viewer
   - Check API responses in `debug/` directory

3. **Production Testing:**
   - Set `debug = False` in main script
   - Run with `python se-overview.py` on target hardware (Raspberry Pi)
   - Visual inspection of e-ink display output
   - Monitor logs for errors

## Current Gaps

**Missing:**
- Unit tests for API parsing logic
- Integration tests for third-party APIs (SolarEdge, WeConnect, BMW)
- Mock fixtures for offline development
- Automated assertion suite
- Test data factories or builders
- Performance/load testing
- Error path testing (network failures, invalid responses)
- Regression test suite

**Risk Areas Without Tests:**
- Energy calculation transformations (round, division, percentages)
- API response parsing and null value handling
- Image rendering coordinates and scaling calculations
- Status string parsing and comparison (lower(), "connected" checks)

---

*Testing analysis: 2026-02-04*
