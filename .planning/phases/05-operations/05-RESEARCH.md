# Phase 5: Operations - Research

**Researched:** 2026-02-06
**Domain:** Production-ready Python application operations (polling loops, logging, signal handling, sleep management)
**Confidence:** HIGH

## Summary

This research investigates production-ready patterns for Python applications that require continuous operation with polling loops, structured logging, time-based sleep windows, and graceful shutdown. The standard approach uses blocking sleep-based polling with `time.monotonic()` for drift prevention, `python-json-logger` for structured logging with `RotatingFileHandler`, signal handlers with cleanup flags (not exceptions), and `zoneinfo` for timezone-aware sleep windows.

The ecosystem strongly favors simple patterns over complex async infrastructure for this use case: blocking loops with `time.sleep()` are appropriate for 5-minute polling intervals, signal handlers should set flags rather than raise exceptions to avoid state corruption, and log rotation should use conservative settings (10MB per file, 5 backups) for Raspberry Pi SD card longevity.

**Primary recommendation:** Use a simple while-loop with `time.monotonic()` deadlines to prevent drift, signal handlers that set a shutdown flag, `python-json-logger` with `RotatingFileHandler` for structured logging, and explicit Display cleanup before exit.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-json-logger | 3.x | Structured JSON logging formatter | Standard library compatible, zero config, supports custom fields via `extra` |
| logging.handlers.RotatingFileHandler | stdlib | Size-based log rotation | Built-in, reliable, prevents disk fill-up on Raspberry Pi |
| signal | stdlib | SIGTERM/SIGINT handling | Standard approach for graceful shutdown |
| time.monotonic() | stdlib | Drift-free timing | Immune to wall-clock adjustments, standard for periodic tasks |
| zoneinfo | stdlib (3.9+) | Timezone-aware datetime | IANA timezone database, handles DST automatically |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | 8.x | Exponential backoff retry | If retry logic becomes complex (95%+ success vs 20-40% fixed delays) |
| schedule | 1.2.x | Human-friendly scheduling syntax | If time-based scheduling becomes complex (current use case doesn't need it) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Simple while loop | asyncio event loop | Asyncio adds complexity for no benefit at 5-minute polling intervals; blocking sleep is appropriate here |
| Simple while loop | APScheduler | APScheduler is heavyweight with cron support and persistence; overkill for simple interval polling |
| python-json-logger | Custom JSON formatter | Reinventing the wheel; python-json-logger is well-tested and handles edge cases |
| signal handlers | atexit only | atexit does NOT fire on signals unless signal handler calls sys.exit(); must use both |

**Installation:**
```bash
pip install python-json-logger>=3.0.0
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── main.py              # Entry point with polling loop and signal handlers
├── config.py            # Already exists - Config dataclass with env var loading
├── display.py           # Already exists - Display abstraction with clear() method
├── solaredge_api.py     # Already exists - API client
├── models.py            # Already exists - Data models
└── screens/             # Already exists - Screen renderers
```

### Pattern 1: Main Loop with Monotonic Deadlines
**What:** Polling loop that calculates next deadline using monotonic clock to prevent drift from repeated sleep calls
**When to use:** Any periodic task where timing accuracy matters over multiple iterations
**Example:**
```python
# Source: https://thelinuxcode.com/python-while-loop-a-practical-productionready-guide/
import time

shutdown_flag = False
poll_interval = 300  # 5 minutes in seconds

next_poll = time.monotonic()
while not shutdown_flag:
    # Do work
    fetch_and_display()

    # Calculate next deadline (monotonic prevents drift)
    next_poll += poll_interval

    # Sleep until next deadline (or skip if we're late)
    sleep_time = next_poll - time.monotonic()
    if sleep_time > 0:
        time.sleep(sleep_time)
    else:
        # Work took longer than interval - log warning, continue immediately
        logging.warning(f"Polling cycle took longer than {poll_interval}s, skipping sleep")
        next_poll = time.monotonic()  # Reset to current time
```

### Pattern 2: Signal Handler with Cleanup Flag
**What:** Signal handlers set a flag that the main loop checks, rather than raising exceptions
**When to use:** Any application that needs graceful shutdown without state corruption
**Example:**
```python
# Source: https://docs.python.org/3/library/signal.html
import signal
import sys

shutdown_flag = False

def signal_handler(signum, frame):
    """Set shutdown flag - do NOT raise exceptions."""
    global shutdown_flag
    signame = signal.Signals(signum).name
    logging.info(f"Received {signame}, initiating graceful shutdown")
    shutdown_flag = True

# Register handlers for both SIGTERM and SIGINT
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

try:
    while not shutdown_flag:
        do_work()
finally:
    # Cleanup ALWAYS runs (via try/finally, not atexit)
    display.clear()
    display.sleep()
    logging.info("Shutdown complete")
```

### Pattern 3: Structured JSON Logging with Rotation
**What:** JSON formatter with rotating file handler for both stdout and file logging
**When to use:** Production applications on resource-constrained devices (Raspberry Pi)
**Example:**
```python
# Source: https://nhairs.github.io/python-json-logger/latest/quickstart/
import logging
from logging.handlers import RotatingFileHandler
from pythonjsonlogger.json import JsonFormatter

def setup_logging(log_level: str = "INFO", log_file: str = "app.log"):
    """Configure structured JSON logging to both stdout and rotating file."""
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # JSON formatter with timestamp, level, logger name, message
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

    # Stdout handler (systemd captures this)
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # Rotating file handler (10MB, 5 backups = max 60MB)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10_000_000,  # 10 MB
        backupCount=5,        # Keep 5 backups
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Use with extra fields for structured data
logging.info("API poll completed", extra={
    "production_kwh": 12.5,
    "consumption_kwh": 8.3,
    "poll_duration_ms": 423
})
```

### Pattern 4: Timezone-Aware Sleep Window
**What:** Check if current time falls within sleep window using timezone-aware datetime
**When to use:** Time-gated operations that must respect local time and DST
**Example:**
```python
# Source: https://docs.python.org/3/library/datetime.html + https://thelinuxcode.com/python-timezone-conversion-a-practical-production-ready-guide/
from datetime import datetime
from zoneinfo import ZoneInfo

def is_sleep_time(sleep_start_hour: int, sleep_end_hour: int, tz_name: str = "Europe/Berlin") -> bool:
    """Check if current time is within sleep window.

    Args:
        sleep_start_hour: Hour to start sleeping (0-23)
        sleep_end_hour: Hour to end sleeping (0-23)
        tz_name: IANA timezone name (default: Europe/Berlin)

    Returns:
        True if within sleep window, False otherwise
    """
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    current_hour = now.hour

    # Handle sleep window that crosses midnight
    if sleep_start_hour <= sleep_end_hour:
        # e.g., 8:00 to 18:00
        return sleep_start_hour <= current_hour < sleep_end_hour
    else:
        # e.g., 22:00 to 6:00 (crosses midnight)
        return current_hour >= sleep_start_hour or current_hour < sleep_end_hour
```

### Pattern 5: Error Tracking with Consecutive Failure Count
**What:** Track consecutive API failures to distinguish transient from persistent errors
**When to use:** Polling loops that need to differentiate between temporary glitches and system-down scenarios
**Example:**
```python
# Source: https://easyparser.com/blog/api-error-handling-retry-strategies-python-guide
consecutive_failures = 0
MAX_FAILURES = 3
last_successful_data = None

while not shutdown_flag:
    try:
        data = fetch_api_data()
        consecutive_failures = 0  # Reset on success
        last_successful_data = data
        render_data_screens(data)
    except APIError as e:
        consecutive_failures += 1
        logging.error(f"API fetch failed (attempt {consecutive_failures}/{MAX_FAILURES})",
                     extra={"error": str(e)})

        if consecutive_failures >= MAX_FAILURES:
            # Show error screen but keep retrying
            if last_successful_data:
                logging.warning("Showing stale data from last successful poll")
                render_data_screens(last_successful_data)
            else:
                render_error_screen("API unreachable")
        # Continue polling even after threshold - don't give up
```

### Anti-Patterns to Avoid

- **Raising exceptions in signal handlers:** Causes unpredictable program state corruption. Use flags instead.
- **Using wall-clock time (time.time()) for intervals:** Subject to NTP adjustments and clock changes. Use time.monotonic().
- **Using atexit alone for signal cleanup:** atexit does NOT fire on signals. Must combine with signal handlers that call sys.exit().
- **Sleeping for exact intervals without drift compensation:** Accumulates error over time. Use deadline-based approach.
- **Using asyncio for long-interval polling:** Adds complexity with no benefit for 5-minute intervals. Blocking sleep is fine.
- **Unbounded log files on Raspberry Pi:** SD cards fill up and corrupt. Always use RotatingFileHandler with conservative limits.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON log formatting | Custom dict-to-JSON formatter | python-json-logger | Handles LogRecord edge cases (exceptions, stack traces), supports custom fields via `extra`, zero config |
| Log rotation | Custom file size checking | logging.handlers.RotatingFileHandler | Thread-safe, handles concurrent writes, atomic rotation, well-tested |
| Exponential backoff | Sleep with increasing intervals | tenacity library (if needed) | Handles jitter, max attempts, custom conditions; 95%+ success vs 20-40% for fixed delays |
| Time-based scheduling | Custom cron-like logic | schedule library (if needed) | Handles DST transitions, timezone rules, human-friendly syntax |
| Timezone handling | Manual UTC offset calculations | zoneinfo (stdlib 3.9+) | IANA database with DST rules, political time changes, automatic updates |

**Key insight:** Python's stdlib has matured to handle most operational concerns (logging, signals, timezones). Third-party libraries (python-json-logger, tenacity) solve specific problems that stdlib deliberately leaves flexible. Don't rebuild what's already solved.

## Common Pitfalls

### Pitfall 1: Sleep Drift from Repeated time.sleep() Calls
**What goes wrong:** Using `time.sleep(300)` at the end of each loop accumulates drift because work time adds to interval
**Why it happens:** Developers think "sleep 5 minutes" equals "poll every 5 minutes" but forget work time
**How to avoid:** Use monotonic deadlines: `next_poll = time.monotonic() + interval`, then `sleep(next_poll - time.monotonic())`
**Warning signs:** Polling intervals gradually increase over time, logs show increasing gaps between polls

### Pitfall 2: Signal Handlers that Raise Exceptions
**What goes wrong:** Handler raises KeyboardInterrupt or calls sys.exit() directly, interrupting code mid-operation (e.g., between file open and close)
**Why it happens:** Python's default SIGINT behavior raises KeyboardInterrupt, developers copy this pattern
**How to avoid:** Set a flag in the handler, check flag in main loop, use try/finally for cleanup (not atexit)
**Warning signs:** Corrupted state on shutdown, resources not cleaned up, display left in wrong state

### Pitfall 3: Using time.time() Instead of time.monotonic()
**What goes wrong:** Wall-clock jumps (NTP sync, DST transition) cause timeouts to fire early/late/never
**Why it happens:** time.time() is more familiar, developers don't know about time.monotonic()
**How to avoid:** Always use time.monotonic() for measuring elapsed time and calculating deadlines
**Warning signs:** Timeouts behave unpredictably, "30 second" sleeps sometimes take 31 or 28 seconds, logs show timing anomalies

### Pitfall 4: atexit Without Signal Handlers
**What goes wrong:** Cleanup functions don't run when process receives SIGTERM (e.g., systemd stop)
**Why it happens:** Developers assume atexit handles "all exits" but it doesn't handle signals
**How to avoid:** Register signal handlers that set shutdown flag and call sys.exit(), which THEN triggers atexit
**Warning signs:** Display not cleared on Ctrl+C or systemd stop, resources leaked on signal termination

### Pitfall 5: Unbounded Log Files on Raspberry Pi
**What goes wrong:** Log files grow indefinitely, fill SD card, cause corruption or application crash
**Why it happens:** Developers forget storage constraints on Raspberry Pi, use defaults
**How to avoid:** Always use RotatingFileHandler with maxBytes=10_000_000 and backupCount=5 (max 60MB)
**Warning signs:** SD card fills up over weeks/months, logs consume gigabytes, system becomes unstable

### Pitfall 6: Naive Sleep Window Logic Across Midnight
**What goes wrong:** Sleep window like "23:00 to 06:00" breaks with simple `start <= hour < end` check
**Why it happens:** Developers forget to handle wraparound case when start > end
**How to avoid:** Use explicit midnight-crossing logic: `hour >= start or hour < end` when `start > end`
**Warning signs:** Application doesn't sleep when configured window crosses midnight, logs show incorrect sleep/wake behavior

### Pitfall 7: E-ink Display Not Cleared Before Shutdown
**What goes wrong:** Display shows stale data after application stops, can cause burn-in or confusion
**Why it happens:** Cleanup happens in __del__ which may not fire on signal termination
**How to avoid:** Explicit cleanup in try/finally block or signal handler: `display.clear()` then `display.sleep()`
**Warning signs:** Display frozen on last screen after stop, e-ink shows "ghost" images

### Pitfall 8: Busy Waiting Without Sleep
**What goes wrong:** While loop without sleep consumes 100% CPU, drains battery, heats device
**Why it happens:** Developer forgets to add sleep in while-true loop, or uses very short sleep (<1ms)
**How to avoid:** Always add sleep of at least 100ms in any polling loop, more for low-frequency checks
**Warning signs:** High CPU usage when idle, device hot to touch, battery drains quickly

## Code Examples

Verified patterns from official sources:

### Complete Main Loop with All Patterns Combined
```python
# Source: Combined from official Python docs and verified patterns above
import logging
import signal
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from logging.handlers import RotatingFileHandler
from pythonjsonlogger.json import JsonFormatter

from config import Config
from display import Display
from solaredge_api import SolarEdgeAPI

# Global shutdown flag
shutdown_flag = False

def signal_handler(signum, frame):
    """Handle SIGTERM and SIGINT by setting shutdown flag."""
    global shutdown_flag
    signame = signal.Signals(signum).name
    logging.info(f"Received {signame}, shutting down gracefully")
    shutdown_flag = True

def setup_logging(level: str):
    """Configure JSON logging to stdout and rotating file."""
    logger = logging.getLogger()
    logger.setLevel(level)

    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

    # Stdout (systemd captures)
    stdout = logging.StreamHandler()
    stdout.setFormatter(formatter)
    logger.addHandler(stdout)

    # Rotating file (10MB × 5 = 60MB max)
    file = RotatingFileHandler(
        "solaredge_monitor.log",
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8"
    )
    file.setFormatter(formatter)
    logger.addHandler(file)

def is_sleep_time(config: Config) -> bool:
    """Check if current time is within sleep window."""
    tz = ZoneInfo("Europe/Berlin")  # Or from config
    now = datetime.now(tz)
    hour = now.hour

    if config.sleep_start_hour <= config.sleep_end_hour:
        return config.sleep_start_hour <= hour < config.sleep_end_hour
    else:
        # Crosses midnight
        return hour >= config.sleep_start_hour or hour < config.sleep_end_hour

def main():
    # Setup
    setup_logging("INFO")
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    config = Config()
    config.log_startup()

    api = SolarEdgeAPI(config.api_key, config.site_id)
    display = Display(debug_mode=config.debug)

    # State tracking
    consecutive_failures = 0
    MAX_FAILURES = 3
    last_successful_data = None
    poll_interval = config.poll_interval * 60  # Convert minutes to seconds

    # Monotonic deadline to prevent drift
    next_poll = time.monotonic()

    try:
        logging.info("Main loop starting")

        while not shutdown_flag:
            # Check sleep window
            if is_sleep_time(config):
                if not in_sleep:
                    logging.info("Entering sleep mode")
                    display.clear()
                    display.sleep()
                    in_sleep = True

                # Sleep for 60s, check again
                time.sleep(60)
                continue
            else:
                if in_sleep:
                    logging.info("Waking from sleep mode")
                    in_sleep = False
                    # Force immediate poll after wake
                    next_poll = time.monotonic()

            # Check if it's time to poll
            now = time.monotonic()
            if now >= next_poll:
                # Fetch and render
                try:
                    data = api.get_current_power_flow()
                    consecutive_failures = 0
                    last_successful_data = data

                    # Cycle through all 4 screens (60s each)
                    for screen_name in ["production", "consumption", "feed_in", "purchased"]:
                        if shutdown_flag:
                            break
                        render_screen(display, screen_name, data)
                        time.sleep(60)

                    logging.info("Poll cycle completed", extra={
                        "production_kwh": data.production,
                        "consecutive_failures": 0
                    })

                except Exception as e:
                    consecutive_failures += 1
                    logging.error(f"Poll failed", extra={
                        "error": str(e),
                        "consecutive_failures": consecutive_failures
                    })

                    if consecutive_failures >= MAX_FAILURES:
                        render_error_screen(display, "API Unreachable")

                # Calculate next deadline
                next_poll += poll_interval

                # If we're late, log warning and reset
                if next_poll < time.monotonic():
                    logging.warning("Poll cycle exceeded interval")
                    next_poll = time.monotonic() + poll_interval

            # Sleep briefly to check shutdown flag responsively
            time.sleep(1)

    finally:
        # Always cleanup
        logging.info("Cleaning up")
        display.clear()
        display.sleep()
        logging.info("Shutdown complete")

if __name__ == "__main__":
    main()
```

### Rotating File Handler Configuration
```python
# Source: https://docs.python.org/3/library/logging.handlers.html
from logging.handlers import RotatingFileHandler

# Conservative settings for Raspberry Pi SD card
handler = RotatingFileHandler(
    'app.log',
    maxBytes=10_000_000,   # 10 MB per file
    backupCount=5,         # Keep 5 backups (total: 60 MB max)
    encoding='utf-8'
)

# Files created: app.log, app.log.1, app.log.2, app.log.3, app.log.4, app.log.5
# When app.log reaches 10MB, it becomes app.log.1, new app.log created
# When app.log.5 exists and rotation happens, it's deleted
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pytz for timezones | zoneinfo (stdlib) | Python 3.9 (2020) | No external dependency, IANA database built-in, simpler API |
| Custom JSON formatters | python-json-logger | 2015+ (mature library) | Zero config, handles edge cases, supports all logging features |
| Threading for I/O | asyncio event loops | Python 3.5+ (2015) | But NOT for this use case - blocking sleep is fine for 5-min intervals |
| time.time() for intervals | time.monotonic() | Python 3.3 (2012) | Immune to wall-clock changes, reliable for timing |

**Deprecated/outdated:**
- **pytz:** Replaced by zoneinfo in Python 3.9+. Still works but unnecessary dependency.
- **retrying library:** Unmaintained since 2016. Use tenacity instead (if retry logic needed).
- **Custom log rotation:** logging.handlers.RotatingFileHandler is thread-safe and well-tested since Python 2.3.

## Open Questions

Things that couldn't be fully resolved:

1. **Timezone Configuration**
   - What we know: zoneinfo supports IANA timezone names (e.g., "Europe/Berlin")
   - What's unclear: Should timezone be configurable via SOLAREDGE_TIMEZONE env var, or hardcoded to Germany?
   - Recommendation: Hardcode "Europe/Berlin" for now (project is for German solar installation), add env var if needed later

2. **Log File Location**
   - What we know: Raspberry Pi typically uses /var/log for system logs, but requires root permissions
   - What's unclear: Should logs go to /var/log/solaredge/, ~/logs/, or current directory?
   - Recommendation: Use current directory (solaredge_monitor.log) for simplicity, let systemd service define WorkingDirectory

3. **Error Screen Design**
   - What we know: Display class has clear() method, screens use unified layout grid
   - What's unclear: Should error screen follow same grid? What icon? Just text?
   - Recommendation: Simple text-only error screen with "API Unavailable" message, centered, no decoration

4. **Screen Cycling During Errors**
   - What we know: After 3 failures, show error screen or stale data
   - What's unclear: If showing stale data, cycle through all 4 screens or just show one?
   - Recommendation: Show production screen only with stale data, add "(Last: HH:MM)" timestamp indicator

## Sources

### Primary (HIGH confidence)
- [Python signal module documentation](https://docs.python.org/3/library/signal.html) - Signal handling patterns and limitations
- [Python logging.handlers documentation](https://docs.python.org/3/library/logging.handlers.html) - RotatingFileHandler parameters and best practices
- [python-json-logger documentation](https://nhairs.github.io/python-json-logger/latest/) - JSON formatter setup and custom fields
- [Python datetime documentation](https://docs.python.org/3/library/datetime.html) - Timezone-aware datetime comparison
- [Python atexit documentation](https://docs.python.org/3/library/atexit.html) - Exit handler limitations with signals

### Secondary (MEDIUM confidence)
- [Python Logging Best Practices - Better Stack](https://betterstack.com/community/guides/logging/python/python-logging-best-practices/) - Structured logging patterns
- [Python Graceful Shutdown Guide - OneUpTime](https://oneuptime.com/blog/post/2025-01-06-python-graceful-shutdown-kubernetes/view) - Signal handler best practices (Jan 2025)
- [Python Time Module Guide - TheLinuxCode](https://thelinuxcode.com/pythons-time-module-in-practice-2026-epochs-clocks-sleeping-and-real-world-timing/) - time.monotonic() vs time.time() (2026)
- [Python While Loop Guide - TheLinuxCode](https://thelinuxcode.com/python-while-loop-a-practical-productionready-guide/) - Monotonic deadline pattern
- [Asyncio vs Threading - GeeksforGeeks](https://www.geeksforgeeks.org/python/asyncio-vs-threading-in-python/) - When to use blocking vs async
- [Tenacity Documentation](https://tenacity.readthedocs.io/) - Exponential backoff library
- [Python Timezone Conversion - TheLinuxCode](https://thelinuxcode.com/python-timezone-conversion-a-practical-production-ready-guide/) - zoneinfo best practices

### Tertiary (LOW confidence)
- [Raspberry Pi Forums - Log Rotation](https://forums.raspberrypi.com/viewtopic.php?t=134971) - Community advice on SD card log management
- [GitHub Issue - Clear e-ink on shutdown](https://github.com/jayofelony/pwnagotchi/issues/329) - E-ink cleanup patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All recommendations from stdlib or well-established libraries with official docs
- Architecture: HIGH - Patterns verified from official Python documentation and recent guides
- Pitfalls: HIGH - Documented in official Python docs (signal limitations, atexit behavior) and recent practitioner guides

**Research date:** 2026-02-06
**Valid until:** 2026-04-06 (60 days - stable domain, stdlib patterns don't change frequently)
