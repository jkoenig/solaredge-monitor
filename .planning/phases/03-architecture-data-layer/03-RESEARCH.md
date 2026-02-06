# Phase 3: Architecture & Data Layer - Research

**Researched:** 2026-02-06
**Domain:** Python modular architecture, HTTP API clients, data modeling
**Confidence:** HIGH

## Summary

This phase restructures a monolithic Python script into clean, importable modules with clear dependency flow. The research focused on Python's standard approaches for module organization, HTTP client patterns with retry logic, typed data models using dataclasses, and hardware abstraction patterns.

The standard approach in modern Python (2026) is to use flat-layout modules for small projects, combine `requests` library with `urllib3.Retry` for HTTP resilience, leverage built-in `dataclasses` for typed models, and implement try-except import patterns for optional dependencies like hardware drivers.

Key findings support the user's decisions in CONTEXT.md: flat module structure at project root is appropriate for this scale, `dataclasses` with `frozen=True` and `field(default_factory=...)` are ideal for API response models, and try-except import pattern for e-ink driver fallback is the standard Python approach.

**Primary recommendation:** Use requests.Session with HTTPAdapter(Retry) for API client, frozen dataclasses with timestamps for data models, and ImportError-catching for hardware abstraction. Follow config → api → models → display → main dependency flow to prevent circular imports.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dataclasses | stdlib (3.7+) | Typed data models | Built-in, zero dependencies, officially recommended for structured data |
| requests | 2.x | HTTP client | De facto standard for HTTP in Python, simple API, universal adoption |
| urllib3 | 2.x (via requests) | Retry logic | Powers requests retry mechanism, battle-tested exponential backoff |
| python-dotenv | 1.x | .env file loading | Phase 2 decision, 12-factor app standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging | stdlib | Structured logging | Always - stdlib, no dependencies, hierarchical loggers |
| typing | stdlib (3.5+) | Type hints | Optional but recommended for IDE support and documentation |
| datetime | stdlib | Timestamp handling | API response parsing, fetched_at timestamps |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| requests | httpx | httpx adds async support but requires learning new API, requests is simpler for sync-only |
| dataclasses | pydantic | Pydantic adds validation but is heavy dependency (12+ deps), overkill for trusted API responses |
| urllib3.Retry | backoff decorator | backoff is more flexible but requires wrapping every function, Retry integrates at session level |

**Installation:**
```bash
# Already installed from Phase 2
pip install requests python-dotenv

# No new dependencies needed - dataclasses, logging, datetime are stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
solaredge-offgrid-monitor/
├── config.py              # Config dataclass (already exists from Phase 2)
├── models.py              # Data models for API responses
├── solaredge_api.py       # SolarEdge API client class
├── display.py             # Display rendering (hardware abstraction)
├── main.py                # Entry point, orchestrates everything
├── .env                   # Environment variables
├── lib/                   # Third-party e-ink driver (waveshare_epd)
├── debug/                 # PNG output for development (gitignored)
└── fonts/                 # Font files for display
```

**Dependency flow** (prevents circular imports):
```
config.py ──> solaredge_api.py ──> models.py ──> display.py ──> main.py
     ↓              ↓                   ↑              ↑
     └──────────────┴───────────────────┴──────────────┘
```

Key principles:
- **Left to right, never backward**: config is imported by all, main imports all but is never imported
- **Models are shared**: Both API and display import models, models import nothing except stdlib
- **Config is foundational**: Only imports stdlib, no project imports

### Pattern 1: HTTP Client with Retry
**What:** Session-based HTTP client with automatic retry on transient failures
**When to use:** Any HTTP API integration where network failures or server errors should be retried
**Example:**
```python
# Source: https://www.zenrows.com/blog/python-requests-retry (2026)
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

class SolarEdgeAPI:
    def __init__(self, api_key: str, site_id: str):
        self.api_key = api_key
        self.site_id = site_id
        self.base_url = "https://monitoringapi.solaredge.com"

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,                    # 3 retries total
            backoff_factor=2,           # 2s, 4s, 8s delays
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]     # Only retry safe methods
        )

        # Create session with retry adapter
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _request(self, endpoint: str, params: dict = None) -> dict | None:
        """Make API request with automatic retry.

        Returns:
            dict: JSON response on success
            None: On complete failure after retries
        """
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        params["api_key"] = self.api_key

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"API request failed: {endpoint} - {e}")
            return None
```

**Exponential backoff formula:**
```
delay = backoff_factor * (2 ** retry_number)
With backoff_factor=2: [2s, 4s, 8s]
```

### Pattern 2: Frozen Dataclasses for API Responses
**What:** Immutable data models with explicit types and automatic timestamp tracking
**When to use:** API response parsing where data should not be modified after creation
**Example:**
```python
# Source: https://docs.python.org/3/library/dataclasses.html
from dataclasses import dataclass, field
from datetime import datetime

@dataclass(frozen=True)
class PowerFlow:
    """Current power flow between system elements.

    Units: All power values in kW (as returned by SolarEdge API)
    """
    grid_power: float           # Negative = purchasing, Positive = feeding in
    load_power: float           # Current consumption
    pv_power: float            # Current PV production
    storage_power: float       # Negative = charging, Positive = discharging
    storage_status: str        # "Charge", "Discharge", "Idle"
    state_of_charge: int       # Battery SoC (0-100%)
    off_grid: bool             # True if disconnected from grid
    fetched_at: datetime = field(default_factory=datetime.now)

@dataclass(frozen=True)
class EnergyDetails:
    """Today's cumulative energy data.

    Units: All energy values in kWh (as returned by SolarEdge API)
    """
    production: float           # Total PV production today
    self_consumption: float    # Energy consumed from own production
    feed_in: float             # Energy exported to grid
    consumption: float         # Total consumption today
    purchased: float           # Energy purchased from grid
    fetched_at: datetime = field(default_factory=datetime.now)
```

**Why frozen:**
- Immutability prevents accidental modification
- Makes objects hashable (can use in sets/dicts)
- Signals intent: these are value objects, not mutable state

### Pattern 3: Hardware Abstraction via Import Fallback
**What:** Auto-detect available hardware driver, fall back to mock implementation
**When to use:** Optional hardware dependencies where code should work without physical device
**Example:**
```python
# Source: Python community pattern, AnyIO-style backend switching
import logging

# Try importing e-ink driver, fall back to PNG mock
try:
    from waveshare_epd import epd2in13_V3
    EINK_AVAILABLE = True
    logging.info("E-ink driver loaded - will render to physical display")
except ImportError:
    EINK_AVAILABLE = False
    logging.info("E-ink driver not found - will render to PNG files")

class Display:
    def __init__(self, debug_mode: bool = False):
        self.width = 250
        self.height = 122

        if not debug_mode and EINK_AVAILABLE:
            self.epd = epd2in13_V3.EPD()
            self.epd.init()
            self.backend = "eink"
        else:
            self.epd = None
            self.backend = "png"
            logging.info("Using PNG backend for development")

    def render(self, image):
        """Render image to display or save as PNG."""
        if self.backend == "eink":
            self.epd.display(self.epd.getbuffer(image))
        else:
            # PNG fallback
            import os
            os.makedirs("debug", exist_ok=True)
            filename = f"debug/screen_{datetime.now():%Y%m%d_%H%M%S}.png"
            image.save(filename)
            logging.info(f"Rendered {self.width}x{self.height} to {filename}")
```

### Pattern 4: API Client Method Structure
**What:** Consistent method structure for API endpoints with error handling
**When to use:** Every API client method that fetches data
**Example:**
```python
def get_current_power_flow(self) -> PowerFlow | None:
    """Fetch current power flow from SolarEdge API.

    Returns:
        PowerFlow: Current system state on success
        None: If API request fails after retries
    """
    endpoint = f"/site/{self.site_id}/currentPowerFlow"
    data = self._request(endpoint)

    if data is None:
        logging.warning("Failed to fetch power flow")
        return None

    try:
        # Parse API response into dataclass
        flow_data = data["siteCurrentPowerFlow"]

        # Determine off-grid state from connections
        off_grid = self._is_off_grid(flow_data["connections"])

        return PowerFlow(
            grid_power=float(flow_data["GRID"]["currentPower"]),
            load_power=float(flow_data["LOAD"]["currentPower"]),
            pv_power=float(flow_data["PV"]["currentPower"]),
            storage_power=float(flow_data["STORAGE"]["currentPower"]),
            storage_status=flow_data["STORAGE"]["status"],
            state_of_charge=int(flow_data["STORAGE"]["chargeLevel"]),
            off_grid=off_grid
        )
    except (KeyError, ValueError, TypeError) as e:
        logging.error(f"Failed to parse power flow response: {e}")
        return None
```

### Anti-Patterns to Avoid

- **Circular imports from shared state:** Don't have config import display to check debug mode while display imports config. Pass debug flag explicitly through constructors.
- **Mutable default values in dataclasses:** Never use `items: list = []`, always use `items: list = field(default_factory=list)` (Python 3.11+ raises ValueError, but keep for older versions)
- **Global session object:** Don't create `session = requests.Session()` at module level. Encapsulate in class so it can be mocked in tests.
- **Ignoring API rate limits:** SolarEdge allows 300 requests/day per site. With 5-minute polling, that's 288 requests/day - safe. Don't poll faster than necessary.
- **Retrying 4xx errors:** Only retry transient failures (429, 5xx, timeouts). Don't retry 401 (auth failed), 404 (endpoint not found), or other client errors.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retry logic | Custom sleep loops with manual backoff | `urllib3.Retry` with `HTTPAdapter` | Handles edge cases: Retry-After headers, jitter, connection pooling, thread safety |
| Data validation | Manual type checking with if/isinstance | `dataclasses` with type hints | Python's stdlib solution, IDE integration, automatic __init__, __repr__, __eq__ |
| Environment variable parsing | Manual os.environ.get() everywhere | Centralized Config dataclass | Already done in Phase 2, provides validation and type conversion |
| Exponential backoff | `time.sleep(2 ** attempt)` | `Retry(backoff_factor=2)` | urllib3 adds jitter, respects server Retry-After, handles max_delay |
| Connection pooling | Creating new requests per call | `requests.Session()` | Reuses TCP connections, massive performance win for repeated API calls |

**Key insight:** HTTP retry logic has 15+ edge cases (DNS failures, partial reads, TLS errors, redirect loops, etc.). urllib3.Retry handles all of them. Don't rebuild this.

## Common Pitfalls

### Pitfall 1: Circular Import from Config
**What goes wrong:** Display imports config to check debug mode, config imports display for logging, Python raises ImportError at startup.
**Why it happens:** Bi-directional dependencies between modules. Python imports are executed top-to-bottom - if module A imports B while B is importing A, one sees the other half-initialized.
**How to avoid:** Follow strict dependency flow: config → api → models → display → main. Pass config values as constructor arguments instead of importing config everywhere.
**Warning signs:** ImportError mentioning "cannot import name", "circular import", or "most likely due to a circular import"

Example fix:
```python
# BAD: display.py imports config
from config import Config
config = Config()
if config.debug:
    ...

# GOOD: display.py receives debug flag
class Display:
    def __init__(self, debug_mode: bool):
        self.debug = debug_mode
```

### Pitfall 2: Mutable Default in Dataclass
**What goes wrong:** Using `connections: list = []` as default causes all instances to share the same list. Modifying one affects all.
**Why it happens:** Default values are created once when class is defined, not per-instance. Lists, dicts, sets are mutable and shared.
**How to avoid:** Always use `field(default_factory=list)` for mutable defaults. Python 3.11+ raises ValueError automatically, but be explicit.
**Warning signs:** Dataclass instances mysteriously affecting each other, or ValueError: "mutable default ... is not allowed"

```python
# BAD
@dataclass
class Response:
    items: list = []  # ValueError in 3.11+, silent bug in 3.10

# GOOD
@dataclass
class Response:
    items: list = field(default_factory=list)
```

### Pitfall 3: Missing Timeout in Requests
**What goes wrong:** HTTP request hangs forever if server never responds. Script appears frozen, no error messages, no logging.
**Why it happens:** `requests.get(url)` without timeout waits indefinitely for response. Common in production when servers are overloaded.
**How to avoid:** Always set timeout parameter: `requests.get(url, timeout=10)`. Use tuple for separate connect/read timeouts: `timeout=(3.0, 10.0)`.
**Warning signs:** Script stops updating, no errors in logs, high memory usage from accumulating requests

```python
# BAD
response = self.session.get(url)

# GOOD
response = self.session.get(url, timeout=10)

# BETTER (separate connect and read timeouts)
response = self.session.get(url, timeout=(3.0, 10.0))
```

### Pitfall 4: Retrying Non-Idempotent Methods
**What goes wrong:** Retrying POST/PUT/DELETE can cause duplicate actions (double-charge, duplicate records).
**Why it happens:** Default Retry retries all methods. POST is not idempotent - running twice has different effect than once.
**How to avoid:** Specify `allowed_methods=["GET", "HEAD", "OPTIONS"]` in Retry configuration. Only retry safe methods.
**Warning signs:** Duplicate database records after network failures, "already exists" errors after retry

```python
# BAD (retries everything including POST)
retry_strategy = Retry(total=3, backoff_factor=2)

# GOOD (only retries safe methods)
retry_strategy = Retry(
    total=3,
    backoff_factor=2,
    allowed_methods=["GET", "HEAD", "OPTIONS"]
)
```

### Pitfall 5: Not Handling Missing Optional Fields
**What goes wrong:** KeyError when API response is missing expected field (e.g., STORAGE section when system has no battery).
**Why it happens:** API documentation may not be exhaustive, or field presence depends on hardware configuration.
**How to avoid:** Use dict.get() with defaults, or wrap parsing in try-except. Check SolarEdge docs for which fields are optional.
**Warning signs:** Script works on test system but crashes on different hardware configuration

```python
# BAD
storage_power = data["STORAGE"]["currentPower"]  # KeyError if no battery

# GOOD
storage_data = data.get("STORAGE", {})
storage_power = float(storage_data.get("currentPower", 0.0))
```

### Pitfall 6: Flat Module Import Ambiguity
**What goes wrong:** Running script as `python solaredge_api.py` for testing, then importing it elsewhere breaks because Python sees two different modules.
**Why it happens:** Python's import system treats `script.py` run directly differently than `import script`. `__name__` is `"__main__"` vs module name.
**How to avoid:** Never run modules directly except main.py. Use `if __name__ == "__main__":` guard for any module-level code. Write tests instead of running modules directly.
**Warning signs:** Module works when imported but fails when run directly, or vice versa

## Code Examples

Verified patterns from official sources:

### Complete API Client Structure
```python
# Source: https://www.zenrows.com/blog/python-requests-retry (2026)
# Source: https://docs.python.org/3/library/dataclasses.html
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from datetime import datetime
from models import PowerFlow, EnergyDetails

class SolarEdgeAPI:
    """Client for SolarEdge Monitoring API with automatic retry."""

    def __init__(self, api_key: str, site_id: str):
        """Initialize API client with retry configuration.

        Args:
            api_key: SolarEdge API key
            site_id: Site identifier
        """
        self.api_key = api_key
        self.site_id = site_id
        self.base_url = "https://monitoringapi.solaredge.com"

        # Configure retry: 3 attempts, exponential backoff (2s, 4s, 8s)
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )

        # Create session with retry adapter
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _request(self, endpoint: str, params: dict = None) -> dict | None:
        """Execute API request with retry and error handling.

        Logs errors internally, returns None on failure.
        Caller checks for None and continues with stale data.

        Args:
            endpoint: API endpoint path (e.g., "/site/123/overview")
            params: Additional query parameters

        Returns:
            dict: JSON response on success
            None: On complete failure after retries
        """
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        params["api_key"] = self.api_key

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logging.error(f"Timeout after 10s: {endpoint}")
            return None
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP error {e.response.status_code}: {endpoint}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {endpoint} - {e}")
            return None

    def get_current_power_flow(self) -> PowerFlow | None:
        """Fetch current power flow between system elements."""
        endpoint = f"/site/{self.site_id}/currentPowerFlow"
        data = self._request(endpoint)

        if data is None:
            return None

        try:
            flow = data["siteCurrentPowerFlow"]

            # Detect off-grid from connections
            off_grid = False
            for conn in flow.get("connections", []):
                if conn["from"].lower() != "grid":
                    off_grid = True
                    break

            return PowerFlow(
                grid_power=float(flow["GRID"]["currentPower"]),
                load_power=float(flow["LOAD"]["currentPower"]),
                pv_power=float(flow["PV"]["currentPower"]),
                storage_power=float(flow["STORAGE"]["currentPower"]),
                storage_status=flow["STORAGE"]["status"],
                state_of_charge=int(flow["STORAGE"]["chargeLevel"]),
                off_grid=off_grid
            )
        except (KeyError, ValueError, TypeError) as e:
            logging.error(f"Failed to parse power flow: {e}")
            return None
```

### Hardware Abstraction Pattern
```python
# Source: https://johal.in/anyio-python-abstract-asyncio-trio-backend-abstraction-2026/
# Pattern: Try-import with fallback, common in Python ecosystem
import logging
import os
from datetime import datetime
from PIL import Image

# Try to import e-ink driver
try:
    from waveshare_epd import epd2in13_V3
    EINK_AVAILABLE = True
except ImportError:
    EINK_AVAILABLE = False

class Display:
    """Hardware-abstracted display renderer.

    Auto-detects available backend:
    - E-ink hardware if waveshare_epd available
    - PNG files if not (development mode)
    """

    def __init__(self, debug_mode: bool = False):
        """Initialize display backend.

        Args:
            debug_mode: Force PNG backend even if e-ink available
        """
        self.width = 250
        self.height = 122

        # Auto-detect backend
        if not debug_mode and EINK_AVAILABLE:
            self.epd = epd2in13_V3.EPD()
            self.epd.init()
            self.epd.Clear(0xFF)
            self.backend = "eink"
            logging.info("Display: E-ink hardware")
        else:
            self.epd = None
            self.backend = "png"
            os.makedirs("debug", exist_ok=True)
            reason = "debug mode" if debug_mode else "driver not found"
            logging.info(f"Display: PNG backend ({reason})")

    def render(self, image: Image.Image, name: str = "screen"):
        """Render image to display or save as PNG.

        Args:
            image: PIL Image to render
            name: Base filename for PNG (ignored for e-ink)
        """
        if self.backend == "eink":
            self.epd.display(self.epd.getbuffer(image))
        else:
            filename = f"debug/{name}_{datetime.now():%Y%m%d_%H%M%S}.png"
            image.save(filename)
            logging.info(f"Rendered {self.width}x{self.height} to {filename}")

    def __del__(self):
        """Clean up e-ink driver on shutdown."""
        if self.backend == "eink" and self.epd:
            try:
                self.epd.sleep()
            except Exception:
                pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Monolithic scripts | Flat modules with clear boundaries | Ongoing best practice | Enables testing, reuse, maintenance |
| Manual retry loops | urllib3.Retry + HTTPAdapter | urllib3 1.0 (2014), popularized 2020+ | Handles edge cases automatically |
| Plain classes | dataclasses with frozen=True | Python 3.7 (2018), matured 3.10+ | Less boilerplate, better immutability |
| Boolean strings via bool() | Explicit string checking | Ongoing (bool("false") trap is old) | Prevents "false" being truthy |
| Global config module | Config dataclass passed explicitly | Modern Python patterns (2020+) | Avoids circular imports, testability |

**Deprecated/outdated:**
- `backoff_factor` without `status_forcelist`: Modern pattern always specifies which status codes to retry (avoid retrying 4xx)
- Running modules directly for testing: Use pytest instead, modules should only be imported
- `unsafe_hash=True` on dataclasses: Use `frozen=True` instead, which automatically enables hashing safely

## Open Questions

Things that couldn't be fully resolved:

1. **SolarEdge API field presence**
   - What we know: currentPowerFlow has GRID, LOAD, PV, STORAGE sections
   - What's unclear: Whether STORAGE is optional if system has no battery, or if all fields always present with 0 values
   - Recommendation: Use defensive parsing with .get() and defaults, test with actual API responses. User has battery so this is LOW priority.

2. **Optimal polling frequency**
   - What we know: SolarEdge updates every 5-15 minutes depending on inverter. Rate limit is 300 requests/day (one per 4.8 minutes).
   - What's unclear: Exact update frequency for user's system
   - Recommendation: User chose 5-minute polling in Phase 2 config (poll_interval=5). This is safe (288 requests/day < 300 limit) and matches typical inverter update rates. Test in production to see if data changes every 5 minutes.

3. **Error recovery strategy**
   - What we know: User decided "return None, continue polling, display shows stale data with Offline indicator"
   - What's unclear: How long to cache stale data before clearing display completely
   - Recommendation: Cache last successful response in main.py, pass age to display.py, show "Offline (X minutes ago)" message. If > 1 hour, consider clearing display.

## Sources

### Primary (HIGH confidence)
- [Python dataclasses official documentation](https://docs.python.org/3/library/dataclasses.html) - Decorator parameters, field(), frozen, defaults
- [urllib3 Retry documentation](https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html) - Retry class parameters, backoff formula
- [Python requests library (via search)](https://www.zenrows.com/blog/python-requests-retry) - Session + HTTPAdapter pattern, 2026 verified
- [DataCamp Python Circular Import Tutorial](https://www.datacamp.com/tutorial/python-circular-import) - Circular import causes and prevention
- [Python Packaging Guide - src vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) - When to use flat layout (updated January 2026)

### Secondary (MEDIUM confidence)
- [API Error Handling & Retry Strategies Python Guide 2026](https://easyparser.com/blog/api-error-handling-retry-strategies-python-guide) - Transient vs permanent errors, modern patterns
- [How to Retry Failed Python Requests 2026](https://www.zenrows.com/blog/python-requests-retry) - Complete HTTPAdapter examples
- [SolarEdge Interface GitHub](https://github.com/bertouttier/solaredge) - API rate limits (300/day), endpoints verification
- [Microsoft Learn SolarEdge API Connector](https://learn.microsoft.com/en-us/connectors/solaredgeip/) - currentPowerFlow endpoint structure
- [Python Module Architecture Best Practices](https://medium.com/@aman.deep291098/untangling-circular-dependencies-in-python-61316529c1f6) - Dependency flow, single responsibility principle

### Tertiary (LOW confidence)
- SolarEdge API PDF documentation - Could not parse PDF programmatically, verified endpoints via multiple secondary sources instead
- [AnyIO backend abstraction](https://johal.in/anyio-python-abstract-asyncio-trio-backend-abstraction-2026/) - Pattern inspiration for hardware abstraction (asyncio-specific, adapted concept)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are stdlib or established standards (requests, dataclasses)
- Architecture: HIGH - Flat layout, dependency flow, and retry patterns verified from official docs and 2026 sources
- Pitfalls: HIGH - Circular imports, mutable defaults, missing timeouts all verified from official Python docs and recent tutorials
- SolarEdge API specifics: MEDIUM - Endpoint structure verified from multiple sources, but official PDF was unparseable (relied on GitHub implementations and Microsoft docs)

**Research date:** 2026-02-06
**Valid until:** 2026-04-06 (60 days - Python stdlib patterns are stable, requests library is mature, SolarEdge API is stable)

**Notes:**
- User decisions from CONTEXT.md fully supported by research: flat module structure is standard for this scale, dataclasses are ideal for API models, try-except import pattern is Python standard
- No conflicts between user decisions and best practices found
- All recommendations are prescriptive and actionable for planner
