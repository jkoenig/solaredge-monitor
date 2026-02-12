"""Forecast.Solar API client with TTL caching.

This module provides a client for the Forecast.Solar API with automatic caching
to respect rate limits. The TTL cache ensures actual HTTP requests only happen
once per hour, regardless of how frequently get_forecast() is called.

The client handles all errors gracefully by logging and returning None, allowing
the application to continue without forecast data when the API is unavailable or
rate-limited.
"""

import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Callable, Any
import requests

from models import ForecastData


# Module-level cache for TTL decorator
_cache = {}


def ttl_cache(ttl_seconds: int = 3600) -> Callable:
    """Cache decorator with time-to-live (TTL).

    Caches function results (including None) for ttl_seconds. This prevents
    hammering the API when it's rate-limited or failing.

    Args:
        ttl_seconds: Cache lifetime in seconds (default: 3600 = 1 hour)

    Returns:
        Decorated function that caches results
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Build cache key from function name + args + kwargs
            cache_key = (func.__name__, args, tuple(sorted(kwargs.items())))

            # Check cache
            if cache_key in _cache:
                result, timestamp = _cache[cache_key]
                age = time.time() - timestamp
                if age < ttl_seconds:
                    logging.debug(f"Cache HIT for {func.__name__} (age: {age:.0f}s)")
                    return result

            # Cache miss - call function
            logging.debug(f"Cache MISS for {func.__name__}")
            result = func(*args, **kwargs)

            # Store result with timestamp (even if None)
            _cache[cache_key] = (result, time.time())

            return result
        return wrapper
    return decorator


class ForecastSolarAPI:
    """Client for Forecast.Solar API with automatic TTL caching.

    The API provides solar production forecasts based on location and system
    parameters. Results are cached for 1 hour to stay within rate limits
    (12 requests/hour on free tier).

    Attributes:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        tilt: Panel tilt angle (0-90 degrees, 0=horizontal, 90=vertical)
        azimuth: Panel azimuth (-180 to 180, 0=south, 90=west, -90=east)
        kwp: System peak power in kilowatts
        base_url: Base URL for Forecast.Solar API
    """

    def __init__(self, lat: float, lon: float, tilt: int, azimuth: int, kwp: float):
        """Initialize API client with system parameters.

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            tilt: Panel tilt angle (0-90 degrees)
            azimuth: Panel azimuth (-180 to 180, 0=south)
            kwp: System peak power in kilowatts
        """
        self.lat = lat
        self.lon = lon
        self.tilt = tilt
        self.azimuth = azimuth
        self.kwp = kwp
        self.base_url = "https://api.forecast.solar"

    @ttl_cache(ttl_seconds=3600)
    def get_forecast(self) -> Optional[ForecastData]:
        """Fetch solar production forecast for today and tomorrow.

        Makes HTTP request to Forecast.Solar API and returns forecasted kWh
        values. Results are cached for 1 hour - subsequent calls within the
        TTL period return cached data without hitting the API.

        Returns:
            ForecastData with today_kwh and tomorrow_kwh on success
            None on any failure (network error, rate limit, parse error)
        """
        # Build API URL
        url = (
            f"{self.base_url}/estimate/watthours/day/"
            f"{self.lat}/{self.lon}/{self.tilt}/{self.azimuth}/{self.kwp}"
        )

        try:
            # GET request with 10s timeout
            response = requests.get(url, timeout=10)

            # Check for rate limiting specifically
            if response.status_code == 429:
                logging.warning("Forecast API rate limited (429), using cached data if available")
                return None

            # Raise for other HTTP errors
            response.raise_for_status()

            # Parse response
            data = response.json()
            watt_hours_day = data["result"]

            # Get today and tomorrow date strings
            today = datetime.now()
            tomorrow = today + timedelta(days=1)
            today_str = today.strftime("%Y-%m-%d")
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")

            # Extract values and convert Wh to kWh
            today_wh = watt_hours_day.get(today_str, 0)
            tomorrow_wh = watt_hours_day.get(tomorrow_str, 0)
            today_kwh = today_wh / 1000.0
            tomorrow_kwh = tomorrow_wh / 1000.0

            return ForecastData(
                today_kwh=today_kwh,
                tomorrow_kwh=tomorrow_kwh,
            )

        except requests.exceptions.Timeout:
            logging.error("Forecast API timeout after 10s")
            return None
        except requests.exceptions.HTTPError as e:
            logging.error(f"Forecast API HTTP error {e.response.status_code}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Forecast API request failed: {e}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            logging.error(f"Failed to parse forecast API response: {e}")
            return None
