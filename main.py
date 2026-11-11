#!/usr/bin/env python3
"""
SolarEdge Off-Grid Monitor - Main Entry Point

Production loop that:
- Reads V2 data through the OAuth token file (no API key). Cadence: by day
  (07:00 to 20:00 by default) overview every 30 minutes, storage hourly,
  history daily, temperature twice; at night only the battery storage at
  about 23:00/02:00/05:00
- Cycles through the cached screens at 60 seconds each, day and night: the
  display is never cleared at night and keeps rotating on cached values
  between polls without any API call
- Persistent call counter with soft brake at 1,500 and hard stop at 1,800
  calls per billing cycle; while stopped, no calls are made and the
  "Kontingent aufgebraucht" info screen is the last rotation entry
- Logs one INFO line per day with the previous day's call totals
- Shows error screen after 3 consecutive failed overview rounds
- Shows "Login nötig" (and makes no calls) while the OAuth token is missing,
  corrupt or rejected; resumes automatically when the token file or .env changes
- Clears the display only on graceful shutdown (SIGTERM/SIGINT)

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
from battery_cache import (
    is_false_expired,
    load_battery_cache_entry,
    save_battery_cache,
)
from fetcher import (
    DataCache,
    fetch_round,
    build_cycle,
    export_fetch_state,
    restore_fetch_state,
)
from call_counter import CallCounter, QuotaBlocked, HARD_LIMIT, try_lock_counter
from forecast_api import ForecastSolarAPI
from display import Display
from screens import get_screens
from screens.error import (
    render_error_screen,
    render_login_required_screen,
    render_quota_exhausted_screen,
)
from token_store import TokenStore, TokenFileWatcher, LoginRequired, TransientAuthError

# Interval for checking token file / .env while login is needed (D-12)
TOKEN_CHECK_INTERVAL_SECONDS = 60

# Name of the quota info screen in the rotation
QUOTA_SCREEN_NAME = "Kontingent"


# Module-level state
shutdown_flag = False


def signal_handler(signum, frame):
    """Signal handler for graceful shutdown."""
    global shutdown_flag
    shutdown_flag = True
    signal_name = signal.Signals(signum).name
    logging.info(f"Received signal {signal_name}, initiating graceful shutdown")


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
    entry = load_battery_cache_entry(config.battery_cache_file, site_id)
    has_battery, checked_at = entry if entry is not None else (False, None)
    if entry is not None and not has_battery and is_false_expired(checked_at):
        logging.info("Cached 'no battery' expired, will detect")
        entry = None
    battery_known = entry is not None
    if battery_known:
        logging.info(f"Battery presence from cache: {has_battery}")
    else:
        logging.info("Battery presence unknown, will detect")
    screens = get_screens(has_battery=has_battery, has_forecast_config=has_forecast)
    screen_names = [name for _, _, name in screens]
    logging.info(f"Screen rotation: {', '.join(screen_names)}")
    return api, has_battery, battery_known, screens, checked_at


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
    error_screen_shown: bool = False
    battery_checked_at: Any = None  # epoch of the last detection (None = unknown)
    counter: Any = None


def run_iteration(state: LoopState, display, now_mono: float) -> bool:
    """One loop iteration: poll if due, then rotate cached screens.

    Returns True if a screen cycle ran. LoginRequired propagates.
    """
    now_local = datetime.now(SITE_TZ)
    if state.counter is not None:
        for line in state.counter.pop_day_summaries(now_local):
            logging.info(line)
        mode = state.counter.state(now_local)
    else:
        mode = "ok"

    if now_mono >= state.next_poll:
        if (
            state.battery_known
            and not state.has_battery
            and is_false_expired(state.battery_checked_at)
        ):
            # A cached "no battery" is only trusted for 7 days (one /devices call).
            logging.info("Cached 'no battery' expired, will re-detect")
            state.battery_known = False
        if state.plan.due(now_local, state.has_battery, state.battery_known, mode):
            logging.info("Starting poll cycle")
            # Refresh token if close to expiry (keeps the 14-day chain alive)
            try:
                state.token_store.get_access_token()
            except (TransientAuthError, QuotaBlocked) as e:
                logging.warning(f"Token refresh deferred: {e}")
            state.token_store.warn_if_grant_expiring()

            result = fetch_round(
                state.api, state.plan, state.cache, now_local,
                state.has_battery, state.battery_known, state.forecast_api,
                quota_mode=mode,
            )

            if result.battery_detected is not None:
                detected = result.battery_detected
                save_battery_cache(state.config.battery_cache_file, state.site_id, detected)
                changed = detected != state.has_battery
                state.has_battery = detected
                state.battery_known = True
                state.battery_checked_at = time.time()
                if changed:
                    state.screens = get_screens(
                        has_battery=detected, has_forecast_config=state.has_forecast
                    )
                logging.info(f"Battery detected: {detected}")

            if state.counter is not None:
                state.counter.save_fetch_state(export_fetch_state(state.plan, state.cache))
                # A monthly 429 may have stopped the counter during this round (D-11)
                mode = state.counter.state(now_local)

            if result.overview_ok:
                state.consecutive_failures = 0
                state.error_screen_shown = False
                e = state.cache.energy
                logging.info(
                    f"Poll successful - Production: {e.production:.2f} kWh, "
                    f"Consumption: {e.consumption:.2f} kWh, "
                    f"Feed-in: {e.feed_in:.2f} kWh, "
                    f"Purchased: {e.purchased:.2f} kWh"
                )
            elif result.overview_attempted and mode != "stopped":
                state.consecutive_failures += 1
                logging.warning(
                    f"Poll failed (consecutive failures: {state.consecutive_failures}/{MAX_FAILURES})"
                )
                if state.consecutive_failures >= MAX_FAILURES and not state.error_screen_shown:
                    logging.error(
                        f"API unreachable after {state.consecutive_failures} consecutive failures, "
                        f"displaying error screen"
                    )
                    display.render(render_error_screen(), "error")
                    state.error_screen_shown = True

        # Schedule next poll
        state.next_poll += state.poll_interval_seconds
        if state.next_poll < time.monotonic():
            logging.warning("Poll cycle took longer than interval, resetting schedule")
            state.next_poll = time.monotonic() + state.poll_interval_seconds

    stopped = mode == "stopped"
    if stopped:
        # The stop supersedes the API error screen (UI-SPEC)
        state.consecutive_failures = 0
        state.error_screen_shown = False
    if state.consecutive_failures >= MAX_FAILURES and not stopped:
        return False
    cycle = build_cycle(state.screens, state.cache) if state.cache.energy is not None else []
    if stopped:
        cycle.append(
            (render_quota_exhausted_screen, state.counter.next_reset(now_local), QUOTA_SCREEN_NAME)
        )
    if cycle:
        run_screen_cycle(display, cycle)
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

    # Persistent call counter (soft brake / hard stop, daily summary)
    if not try_lock_counter(config.call_counter_file, hold=True):
        logging.error(
            "Call counter file is locked by another process; refusing to start "
            "(a second writer would corrupt the call count)"
        )
        sys.exit(1)
    counter = CallCounter(config.call_counter_file, billing_day=config.billing_day)
    logging.info(
        f"Call budget: {counter.cycle_total()}/{HARD_LIMIT} this cycle, "
        f"state {counter.state()}, next reset {counter.next_reset()}"
    )

    # Token store (API client is created lazily once a usable token exists)
    token_store = TokenStore(
        config.token_file, config.client_id, config.client_secret,
        env_file=config.env_file, counter=counter,
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
                                state.error_screen_shown = False
                                state.next_poll = time.monotonic()
                            next_poll = time.monotonic()
                        except LoginRequired as e:
                            logging.warning(f"Login still required: {e.reason}")
                        except (TransientAuthError, QuotaBlocked) as e:
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
                api, has_battery, battery_known, screens, checked_at = init_site_clients(
                    config, token_store, token_site_id, has_forecast
                )
                plan = FetchPlan(
                    night_start_hour=config.sleep_start_hour,
                    night_end_hour=config.sleep_end_hour,
                )
                cache = DataCache()
                restore_fetch_state(
                    plan, cache, counter.fetch_state(), datetime.now(SITE_TZ)
                )
                new_state = LoopState(
                    config=config,
                    token_store=token_store,
                    api=api,
                    plan=plan,
                    cache=cache,
                    counter=counter,
                    screens=screens,
                    has_battery=has_battery,
                    battery_known=battery_known,
                    battery_checked_at=checked_at,
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
