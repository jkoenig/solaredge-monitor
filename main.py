#!/usr/bin/env python3
"""
SolarEdge Off-Grid Monitor - Main Entry Point

Production loop that:
- Reads V2 data through the OAuth token file (no API key). Interim cadence
  (Phase 13 replaces it): overview every 30 minutes between 07:00 and 20:00
  by default, storage hourly, history daily, temperature twice daily, and an
  hourly backoff after 3 failed overview rounds
- Cycles through the cached screens at 60 seconds each; between polls the
  display keeps rotating on cached values without any API call
- Sleeps outside the configured window (default 20:00 to 07:00)
- Shows error screen after 3 consecutive failed overview rounds
- Shows "Login nötig" (and makes no calls) while the OAuth token is missing,
  corrupt or rejected; resumes automatically when the token file or .env changes
- Clears display on graceful shutdown (SIGTERM/SIGINT)

Run with: python3 main.py

The site id comes from the token file; client id/secret are written to .env
by the Mac login script.
"""

import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from pathlib import Path

# Add lib/ to sys.path so waveshare_epd driver can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from dotenv import load_dotenv

# Load .env before importing Config (Config reads from environment)
load_dotenv(interpolate=False)

from config import Config
from logging_setup import setup_logging
from solaredge_api import SolarEdgeAPI, SITE_TZ
from fetch_schedule import FetchPlan
from battery_cache import load_battery_cache, save_battery_cache
from fetcher import DataCache, fetch_round, build_cycle
from forecast_api import ForecastSolarAPI
from display import Display
from screens import get_screens
from screens.error import render_error_screen, render_login_required_screen
from token_store import TokenStore, TokenFileWatcher, LoginRequired, TransientAuthError

# Interval for checking token file / .env while login is needed (D-12)
TOKEN_CHECK_INTERVAL_SECONDS = 60


# Module-level state
shutdown_flag = False


def signal_handler(signum, frame):
    """Signal handler for graceful shutdown."""
    global shutdown_flag
    shutdown_flag = True
    signal_name = signal.Signals(signum).name
    logging.info(f"Received signal {signal_name}, initiating graceful shutdown")


def is_sleep_time(config: Config) -> bool:
    """
    Check if current time is within configured sleep window.

    Handles midnight-crossing sleep windows (e.g., 23:00 to 06:00).
    Returns False if sleep_start == sleep_end (no sleep window).

    Timezone: Europe/Berlin (hardcoded per research recommendation)
    """
    tz = ZoneInfo("Europe/Berlin")
    now = datetime.now(tz)
    hour = now.hour

    start = config.sleep_start_hour
    end = config.sleep_end_hour

    # No sleep window if start == end
    if start == end:
        return False

    # Handle midnight-crossing
    if start <= end:
        # Normal window: e.g., 0 to 6
        return start <= hour < end
    else:
        # Crosses midnight: e.g., 23 to 6 means (hour >= 23) or (hour < 6)
        return hour >= start or hour < end


def interruptible_sleep(seconds: float) -> bool:
    """
    Sleep for specified seconds, checking shutdown_flag every second.

    Returns:
        True if sleep completed normally
        False if interrupted by shutdown
    """
    end_time = time.time() + seconds
    while time.time() < end_time:
        if shutdown_flag:
            return False
        time.sleep(min(1.0, end_time - time.time()))
    return True


def init_site_clients(config: Config, token_store: TokenStore, site_id: str, has_forecast: bool):
    """Create the SolarEdge client, read the battery cache and build the screen list.

    Makes no API call: detection runs in fetch_round (DEVICES job) when unknown.
    """
    api = SolarEdgeAPI(token_store)
    cached = load_battery_cache(config.battery_cache_file, site_id)
    battery_known = cached is not None
    has_battery = bool(cached)
    if battery_known:
        logging.info(f"Battery presence from cache: {has_battery}")
    else:
        logging.info("Battery presence unknown, will detect")
    screens = get_screens(has_battery=has_battery, has_forecast_config=has_forecast)
    screen_names = [name for _, _, name in screens]
    logging.info(f"Screen rotation: {', '.join(screen_names)}")
    return api, has_battery, battery_known, screens


MAX_FAILURES = 3


@dataclass
class LoopState:
    """Mutable state of the polling loop."""
    config: Any
    token_store: Any
    api: Any
    plan: Any
    cache: Any
    screens: list
    has_battery: bool
    battery_known: bool
    site_id: str
    forecast_api: Any = None
    has_forecast: bool = False
    next_poll: float = 0.0
    poll_interval_seconds: float = 1800.0
    consecutive_failures: int = 0


def run_iteration(state: LoopState, display, now_mono: float) -> bool:
    """One loop iteration: poll if due, then rotate cached screens.

    Returns True if a screen cycle ran. LoginRequired propagates.
    """
    if now_mono >= state.next_poll:
        now_local = datetime.now(SITE_TZ)
        if state.plan.due(now_local, state.has_battery, state.battery_known):
            logging.info("Starting poll cycle")
            # Refresh token if close to expiry (keeps the 14-day chain alive)
            try:
                state.token_store.get_access_token()
            except TransientAuthError as e:
                logging.warning(f"Token refresh deferred: {e}")
            state.token_store.warn_if_grant_expiring()

            result = fetch_round(
                state.api, state.plan, state.cache, now_local,
                state.has_battery, state.battery_known, state.forecast_api,
            )

            if result.battery_detected is not None:
                detected = result.battery_detected
                save_battery_cache(state.config.battery_cache_file, state.site_id, detected)
                changed = detected != state.has_battery
                state.has_battery = detected
                state.battery_known = True
                if changed:
                    state.screens = get_screens(
                        has_battery=detected, has_forecast_config=state.has_forecast
                    )
                logging.info(f"Battery detected: {detected}")

            if result.overview_ok:
                state.consecutive_failures = 0
                e = state.cache.energy
                logging.info(
                    f"Poll successful - Production: {e.production:.2f} kWh, "
                    f"Consumption: {e.consumption:.2f} kWh, "
                    f"Feed-in: {e.feed_in:.2f} kWh, "
                    f"Purchased: {e.purchased:.2f} kWh"
                )
            else:
                state.consecutive_failures += 1
                logging.warning(
                    f"Poll failed (consecutive failures: {state.consecutive_failures}/{MAX_FAILURES})"
                )
                if state.consecutive_failures == MAX_FAILURES:
                    logging.error(
                        f"API unreachable after {MAX_FAILURES} consecutive failures, "
                        f"displaying error screen"
                    )
                    display.render(render_error_screen(), "error")

        # Schedule next poll
        state.next_poll += state.poll_interval_seconds
        if state.next_poll < time.monotonic():
            logging.warning("Poll cycle took longer than interval, resetting schedule")
            state.next_poll = time.monotonic() + state.poll_interval_seconds

    if state.consecutive_failures >= MAX_FAILURES:
        return False
    if state.cache.energy is not None:
        run_screen_cycle(display, build_cycle(state.screens, state.cache))
        return True
    return False


def run_screen_cycle(display: Display, cycle: list) -> None:
    """
    Cycle through screens, displaying each for 60 seconds.

    Args:
        cycle: list of (render_fn, data, name) tuples to display

    Breaks immediately if shutdown signal received during any sleep.
    """
    for screen_fn, data, name in cycle:
        if shutdown_flag:
            break

        # Render screen
        image = screen_fn(data)
        display.render(image, name)
        logging.debug(f"Displaying screen: {name}")

        # Wait 60 seconds (interruptible)
        if not interruptible_sleep(60):
            logging.info(f"Screen cycle interrupted during {name}")
            break


def main():
    """Main polling loop."""
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Setup structured JSON logging early (before Config so validation errors use JSON format)
    setup_logging("INFO")

    # Load and validate configuration
    try:
        config = Config()
    except ValueError as e:
        logging.error(f"Configuration validation failed: {e}")
        sys.exit(1)

    # Adjust log level to configured value
    logging.getLogger().setLevel(config.log_level)

    # Log startup info
    logging.info("SolarEdge Off-Grid Monitor starting")
    config.log_startup()

    # Create display
    display = Display(debug_mode=config.debug)
    logging.info(f"Display initialized (backend: {display.backend})")

    # Token store (API client is created lazily once a usable token exists)
    token_store = TokenStore(
        config.token_file, config.client_id, config.client_secret, env_file=config.env_file
    )
    watcher = TokenFileWatcher(config.token_file, config.env_file)
    state = None
    initialized_site_id = None
    site_mismatch_logged = False

    # Detect forecast configuration
    has_forecast = config.has_forecast_config()
    forecast_api = None
    if has_forecast:
        forecast_api = ForecastSolarAPI(
            lat=config.forecast_lat,
            lon=config.forecast_lon,
            tilt=config.forecast_tilt,
            azimuth=config.forecast_azimuth,
            kwp=config.forecast_kwp,
        )
        logging.info("Forecast enabled: Forecast.Solar API client initialized")
    else:
        logging.info("Forecast disabled: incomplete FORECAST_* configuration")

    # Initialize polling state
    poll_interval_seconds = config.poll_interval * 60
    in_sleep = False
    next_poll = time.monotonic()  # Poll immediately on startup
    login_needed = False
    login_screen_shown = False
    next_token_check = 0.0

    def enter_login_state(reason: str) -> None:
        nonlocal login_needed, next_token_check
        logging.warning(f"Login required: {reason}")
        login_needed = True
        watcher.reset()
        next_token_check = time.monotonic() + TOKEN_CHECK_INTERVAL_SECONDS

    try:
        token_store.load()
    except LoginRequired as e:
        enter_login_state(e.reason)

    try:
        while not shutdown_flag:
            # Check sleep window
            if is_sleep_time(config):
                if not in_sleep:
                    logging.info("Entering sleep mode (display off until wake time)")
                    display.clear()
                    in_sleep = True
                # Sleep for 60 seconds then check again
                interruptible_sleep(60)
                continue
            else:
                if in_sleep:
                    logging.info("Waking from sleep mode")
                    in_sleep = False
                    login_screen_shown = False  # redraw after display.clear()
                    next_poll = time.monotonic()  # Force immediate poll after wake
                    if state is not None:
                        state.next_poll = next_poll

            # Login-needed state: only the login screen, no calls (D-07..D-09)
            if login_needed:
                if not login_screen_shown:
                    display.render(render_login_required_screen(), "login")
                    login_screen_shown = True
                if time.monotonic() >= next_token_check:
                    next_token_check = time.monotonic() + TOKEN_CHECK_INTERVAL_SECONDS
                    if watcher.has_changed():
                        logging.info("Token file or .env changed, re-checking login")
                        token_store.reload_credentials()
                        try:
                            token_store.get_access_token()
                            logging.info("Login OK, resuming")
                            login_needed = False
                            login_screen_shown = False
                            if state is not None:
                                state.consecutive_failures = 0
                                state.next_poll = time.monotonic()
                            next_poll = time.monotonic()
                        except LoginRequired as e:
                            logging.warning(f"Login still required: {e.reason}")
                        except TransientAuthError as e:
                            logging.warning(f"Token check deferred, resuming: {e}")
                            login_needed = False
                            login_screen_shown = False
                            next_poll = time.monotonic()
                            if state is not None:
                                state.next_poll = next_poll
                interruptible_sleep(1)
                continue

            try:
                token_site_id = token_store.site_id
            except LoginRequired as e:
                enter_login_state(e.reason)
                continue
            if initialized_site_id != token_site_id:
                api, has_battery, battery_known, screens = init_site_clients(
                    config, token_store, token_site_id, has_forecast
                )
                new_state = LoopState(
                    config=config,
                    token_store=token_store,
                    api=api,
                    plan=FetchPlan(),
                    cache=DataCache(),
                    screens=screens,
                    has_battery=has_battery,
                    battery_known=battery_known,
                    site_id=token_site_id,
                    forecast_api=forecast_api,
                    has_forecast=has_forecast,
                    next_poll=state.next_poll if state is not None else next_poll,
                    poll_interval_seconds=poll_interval_seconds,
                )
                state = new_state
                initialized_site_id = token_site_id
            if config.site_id and config.site_id != token_site_id and not site_mismatch_logged:
                logging.warning("Configured SOLAREDGE_SITE_ID differs from token site id; using token site id")
                site_mismatch_logged = True

            try:
                ran = run_iteration(state, display, time.monotonic())
            except LoginRequired as e:
                enter_login_state(e.reason)
                continue
            if not ran:
                interruptible_sleep(1)

    finally:
        # Always runs: clean shutdown
        logging.info("Shutting down, clearing display")
        display.clear()
        display.sleep()
        logging.info("Shutdown complete")


if __name__ == "__main__":
    main()
