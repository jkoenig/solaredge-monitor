#!/usr/bin/env python3
"""
SolarEdge Off-Grid Monitor - Main Entry Point

Production polling loop that:
- Fetches SolarEdge data every 5 minutes (configurable)
- Cycles through 4 display screens at 60 seconds each
- Sleeps between midnight and 6 AM (configurable)
- Shows error screen after 3 consecutive API failures
- Clears display on graceful shutdown (SIGTERM/SIGINT)

Run with: python3 main.py

Requires .env file with:
  SOLAREDGE_API_KEY=your_api_key
  SOLAREDGE_SITE_ID=your_site_id
"""

import logging
import signal
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from pathlib import Path

# Add lib/ to sys.path so waveshare_epd driver can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from dotenv import load_dotenv

# Load .env before importing Config (Config reads from environment)
load_dotenv()

from config import Config
from logging_setup import setup_logging
from solaredge_api import SolarEdgeAPI
from forecast_api import ForecastSolarAPI
from display import Display
from models import BatteryData, ForecastData
from screens import get_screens
from screens.error import render_error_screen


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


def fetch_data(api: SolarEdgeAPI, has_battery: bool = False, forecast_api: ForecastSolarAPI = None):
    """
    Fetch data from SolarEdge API.

    Returns:
        tuple: (energy_details, battery_data, history_data, forecast_data) - any may be None on failure
    """
    energy_details = api.get_energy_details()
    power_flow = api.get_current_power_flow()

    if energy_details:
        logging.debug(f"Fetched energy details: {energy_details}")
    if power_flow:
        logging.debug(f"Fetched power flow: {power_flow}")

    battery_data = None
    if has_battery and power_flow:
        storage = api.get_storage_data()
        battery_data = BatteryData(
            state_of_charge=power_flow.state_of_charge,
            status=power_flow.storage_status,
            internal_temp=storage["internal_temp"] if storage else 0.0,
            available_energy=storage["available_energy"] if storage else 0.0,
            power=storage["power"] if storage else 0.0,
        )
        logging.debug(f"Fetched battery data: {battery_data}")

    history_data = api.get_energy_history()
    if history_data:
        logging.debug(f"Fetched energy history: {len(history_data.dates)} days")

    forecast_data = None
    if forecast_api:
        raw_forecast = forecast_api.get_forecast()
        if raw_forecast:
            actual_prod = energy_details.production if energy_details else 0.0
            forecast_data = ForecastData(
                today_kwh=raw_forecast.today_kwh,
                tomorrow_kwh=raw_forecast.tomorrow_kwh,
                actual_production=actual_prod,
                fetched_at=raw_forecast.fetched_at,
            )
            logging.debug(f"Fetched forecast: today={forecast_data.today_kwh:.1f} kWh, tomorrow={forecast_data.tomorrow_kwh:.1f} kWh, actual={forecast_data.actual_production:.1f} kWh")

    return energy_details, battery_data, history_data, forecast_data


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
        logging.info(f"Displaying screen: {name}")

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

    # Create API client and display
    api = SolarEdgeAPI(config.api_key, config.site_id)
    display = Display(debug_mode=config.debug)
    logging.info(f"Display initialized (backend: {display.backend})")

    # Detect battery at startup
    battery_detected = api.has_battery()
    logging.info(f"Battery detected: {battery_detected}")

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

    # Build dynamic screen list
    screens = get_screens(has_battery=battery_detected, has_forecast_config=has_forecast)
    screen_names = [name for _, _, name in screens]
    logging.info(f"Screen rotation: {', '.join(screen_names)}")

    # Initialize polling state
    consecutive_failures = 0
    MAX_FAILURES = 3
    last_successful_energy = None
    last_successful_battery = None
    last_successful_history = None
    last_successful_forecast = None
    poll_interval_seconds = config.poll_interval * 60
    in_sleep = False
    next_poll = time.monotonic()  # Poll immediately on startup

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
                    next_poll = time.monotonic()  # Force immediate poll after wake

            # Check if it's time to poll
            now = time.monotonic()
            if now < next_poll:
                interruptible_sleep(1)
                continue

            # Fetch data
            logging.info("Starting poll cycle")
            energy_details, battery_data, history_data, forecast_data = fetch_data(api, has_battery=battery_detected, forecast_api=forecast_api)

            if energy_details is not None:
                # Successful poll
                consecutive_failures = 0
                last_successful_energy = energy_details
                if battery_data is not None:
                    last_successful_battery = battery_data
                if history_data is not None:
                    last_successful_history = history_data
                if forecast_data is not None:
                    last_successful_forecast = forecast_data
                logging.info(
                    f"Poll successful - Production: {energy_details.production:.2f} kWh, "
                    f"Consumption: {energy_details.consumption:.2f} kWh, "
                    f"Feed-in: {energy_details.feed_in:.2f} kWh, "
                    f"Purchased: {energy_details.purchased:.2f} kWh"
                )

                # Build screen cycle with appropriate data per screen
                cycle = []
                for render_fn, data_key, name in screens:
                    if data_key == "energy":
                        cycle.append((render_fn, energy_details, name))
                    elif data_key == "battery" and battery_data:
                        cycle.append((render_fn, battery_data, name))
                    elif data_key == "history" and (history_data or last_successful_history):
                        cycle.append((render_fn, history_data or last_successful_history, name))
                    elif data_key == "forecast" and forecast_data:
                        cycle.append((render_fn, forecast_data, name))

                run_screen_cycle(display, cycle)

            else:
                # Poll failed
                consecutive_failures += 1
                logging.warning(
                    f"Poll failed (consecutive failures: {consecutive_failures}/{MAX_FAILURES})"
                )

                if consecutive_failures >= MAX_FAILURES:
                    # Show error screen after threshold
                    logging.error(
                        f"API unreachable after {MAX_FAILURES} consecutive failures, "
                        f"displaying error screen"
                    )
                    error_image = render_error_screen()
                    display.render(error_image, "error")
                elif last_successful_energy is not None:
                    # Show stale data before threshold
                    logging.info("Showing stale data from last successful poll")
                    stale_cycle = []
                    for render_fn, data_key, name in screens:
                        if data_key == "energy":
                            stale_cycle.append((render_fn, last_successful_energy, name))
                        elif data_key == "battery" and last_successful_battery:
                            stale_cycle.append((render_fn, last_successful_battery, name))
                        elif data_key == "history" and last_successful_history:
                            stale_cycle.append((render_fn, last_successful_history, name))
                        elif data_key == "forecast" and last_successful_forecast:
                            stale_cycle.append((render_fn, last_successful_forecast, name))
                    run_screen_cycle(display, stale_cycle)

            # Schedule next poll
            next_poll += poll_interval_seconds

            # If we fell behind (long cycle), reset to now + interval
            if next_poll < time.monotonic():
                logging.warning(
                    "Poll cycle took longer than interval, resetting schedule"
                )
                next_poll = time.monotonic() + poll_interval_seconds

    finally:
        # Always runs: clean shutdown
        logging.info("Shutting down, clearing display")
        display.clear()
        display.sleep()
        logging.info("Shutdown complete")


if __name__ == "__main__":
    main()
