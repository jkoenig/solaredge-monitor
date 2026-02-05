# Coding Conventions

**Analysis Date:** 2026-02-04

## Naming Patterns

**Files:**
- Module files: `snake_case.py` format
- Examples: `se-overview.py`, `se-monitor2.py`, `epd_2in13_V3_test.py`
- Use hyphens for versioned displays: `se-monitor2.py`, `se-monitor.old.py`

**Functions:**
- Use `snake_case` for all function definitions
- Examples: `get_site_overview()`, `get_energy_details()`, `get_current_power_flow()`, `display()`, `get_free_disk_space_of_timemachine()`
- Prefix with action verbs: `get_`, `display`, `to_`

**Variables:**
- Use `snake_case` for local variables and parameters
- Examples: `api_key`, `site_id`, `hostname`, `username`, `sleep_timer`, `scale_factor`, `original_width`, `original_height`
- Global configuration variables in uppercase is NOT used - all uppercase constants mixed with lowercase
- Long descriptive names preferred: `self_consumption`, `feed_in_percentage`, `cruising_range_electric_km`

**Types:**
- No type hints used
- No dataclasses or TypedDicts
- Dynamic typing throughout

## Code Style

**Formatting:**
- Python 2/3 compatible shebang: `#!/usr/bin/python`
- UTF-8 encoding declared: `# -*- coding:utf-8 -*-`
- Spacing: Standard 4-space indentation (PEP 8)
- Line length: Not strictly enforced (flake8 ignores E501)

**Linting:**
- Tool: flake8 (configured in `weconnect/.flake8`)
- Key configuration: Ignores E501 (line too long)
- No Black formatter or strict style enforcement detected

**Import Organization:**

Order by standard Python convention:
1. Standard library imports (`logging`, `requests`, `datetime`, `sys`, `os`, `paramiko`, `time`, `traceback`)
2. Third-party imports (`PIL`, `weconnect`, `urllib.parse`, `asyncio`, `bimmer_connected`)
3. Local imports (conditional path appends for lib directory)

Example from `se-overview.py`:
```python
#!/usr/bin/python
# -*- coding:utf-8 -*-
debug = False

import logging
import requests
import datetime
import sys
import os
import paramiko
import time
import traceback

import datetime as dt
from PIL import Image,ImageDraw,ImageFont
from weconnect import wci
from urllib.parse import urlencode
import asyncio

fontsdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'fonts')
debugdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'debug')
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')

if os.path.exists(libdir):
    sys.path.append(libdir)

from bimmer_connected.account import MyBMWAccount
from bimmer_connected.api.regions import Regions
```

**Path Aliases:**
- No alias system used
- Direct path construction with `os.path.join()`
- Relative to script directory via `os.path.dirname(os.path.realpath(__file__))`

## Error Handling

**Patterns:**
- Generic broad exception handling with `try/except Exception as e`
- Most functions catch all exceptions: `except Exception as e:`
- Logging used for error reporting, not raising/propagating
- Return fallback values on error: lists of "n/a" strings, "n/a" strings, or empty structures

Example from `get_free_disk_space_of_timemachine()`:
```python
def get_free_disk_space_of_timemachine(hostname, username, password):
    try:
        ssh = paramiko.SSHClient()
        # ... implementation
        return usage_percentage
    except Exception as e:
        logging.info(f"An error occurred: {e}")
        return "n/a"
```

**Error Propagation:**
- Errors are NOT re-raised
- Errors are logged but execution continues
- Functions return safe defaults on exception
- For API calls: log error and return empty/fallback results

Example from `get_vw_state_of_charge()`:
```python
except Exception as e:
    logging.info(f"An error occurred: {e}")
    return ["n/a","n/a","n/a","n/a","n/a","n/a","n/a","n/a"]
```

## Logging

**Framework:** Python's built-in `logging` module

**Configuration:**
```python
logging.basicConfig(level=logging.DEBUG)
```

**Patterns:**
- Used throughout for informational messages
- Both `logging.info()` and `logging.error()` used interchangeably for errors
- Log messages include context and timestamps in debug files
- Debug mode writes API responses to debug text files with timestamps

Example:
```python
logging.info("Invoke SolarEdge API to get overview data")
logging.info(f"Last Update Time: {lastUpdateTime}")
logging.error(f"Fehler beim Importieren des Waveshare EPD Moduls: {e}")
```

**Debug Output:**
- When `debug = True`, API responses written to files:
  - `debug/solaredge-site-overview-results.txt`
  - `debug/solaredge-energyDetails-results.txt`
  - `debug/weconnect-vehicle-charging-results.txt`
- Display images saved to: `display/2-13inch-EInk-*.png`

## Comments

**When to Comment:**
- Comments in German and English mixed
- Inline comments for non-obvious logic
- Section headers with dashes: `# ------ Site Overview - Energy Production ----------`
- Minimal but present

**JSDoc/TSDoc:**
- Not used
- No docstrings on functions
- Only inline comments

Example:
```python
# Automatisch unbekannte Hosts zu known_hosts hinzufügen
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Index 0: on grid
# Index 1: off grid
grid_levels = ["\uE55B", "\uE560"]
```

## Function Design

**Size:** Mixed - some functions are 50+ lines (display functions), others are shorter (utility functions)

**Parameters:**
- Mix of parameters and global variables
- Global config variables used directly (api_key, site_id, hostname, etc.)
- Parameters used for context-specific data
- No kwargs or *args patterns

**Return Values:**
- Functions return lists of values (array unpacking pattern)
- Display functions return None (side effects only)
- API getters return lists in fixed order for unpacking

Example pattern:
```python
def get_site_overview():
    # ... processing
    results = [
        lastUpdateTime,
        lifeTimeEnergy,
        lifeTimeRevenue,
        # ... more values
    ]
    return results

# Called as:
display(get_energy_details())  # unpacked implicitly
```

## Module Design

**Exports:**
- No explicit `__all__` used
- All top-level functions are callable
- Global configuration variables at module top
- No classes used

**Barrel Files:**
- Not applicable - no barrel/index pattern
- Each script is standalone with its own config

**Script Execution:**
- Uses `if __name__ == "__main__":` pattern
- Main loop for continuous execution:
```python
if __name__ == "__main__":
    logging.info("SolarEdge Monitor started ...")

    functions = [
        lambda: display6(get_bmw_state_of_charge()),
        lambda: display3(get_current_power_flow()),
        # ...
    ]

    while True:
        current_hour = dt.datetime.now().hour
        if 6 <= current_hour < 24:
            for func in functions:
                func()
                time.sleep(sleep_timer)
        else:
            time.sleep(sleep_timer)
```

## Code Reuse

**Duplication Observed:**
- Display functions have repeated structure (display, display2, display3, display4, display5, display6)
- Each initializes EPD, creates image, draws content, resizes, displays
- Opportunity to refactor with a display factory pattern, but currently duplicated

**Conditional Imports:**
- Library path conditionally added: `if os.path.exists(libdir): sys.path.append(libdir)`
- Optional EPD import within try/except for debug mode flexibility

---

*Convention analysis: 2026-02-04*
