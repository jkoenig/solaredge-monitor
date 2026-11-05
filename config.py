"""
Configuration management for SolarEdge Off-Grid Monitor.

Loads all configuration from environment variables (with SOLAREDGE_ prefix).
Validates required fields and type-converts all values at startup.

Usage:
    from dotenv import load_dotenv
    load_dotenv(interpolate=False)  # Load .env file first; no ${VAR} expansion so secrets with "$" stay intact
    from config import Config
    config = Config()  # Loads from environment, validates, raises ValueError on errors
    config.log_startup()  # Logs with secrets masked
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os
import logging


@dataclass
class Config:
    """Application configuration loaded from environment variables.

    All environment variables use SOLAREDGE_ prefix.

    Required fields (must be provided):
        - api_key: SolarEdge API key (D-15; removed in Phase 12)

    Optional fields (with defaults):
        - site_id: informational only; the app reads the site id from the
          token file (D-14)
        - client_id / client_secret: OAuth credentials written to .env by the
          Mac login script (D-13). Missing values do not stop startup; the
          service shows "Login nötig" instead.
        - token_file: OAuth token file (default: <app dir>/.tokens.json,
          override with SOLAREDGE_TOKEN_FILE) (D-11)
        - poll_interval: Minutes between API polls (default: 5, minimum: 1)
        - sleep_start_hour: Hour to pause polling, 0-23 (default: 0 = midnight)
        - sleep_end_hour: Hour to resume polling, 0-23 (default: 6 = 6 AM)
        - debug: Enable debug mode (default: False)
        - log_level: Logging level (default: INFO)
    """

    # Required credentials
    api_key: str = ""
    site_id: str = ""  # optional, informational (D-14)

    # OAuth (Phase 11)
    client_id: str = ""
    client_secret: str = ""
    token_file: str = ""
    env_file: str = ""

    # Optional operational settings with defaults
    poll_interval: int = 5
    sleep_start_hour: int = 0
    sleep_end_hour: int = 6
    debug: bool = False
    log_level: str = "INFO"

    # Optional forecast configuration (all 5 must be present to enable forecast screen)
    forecast_lat: Optional[float] = None
    forecast_lon: Optional[float] = None
    forecast_tilt: Optional[int] = None
    forecast_azimuth: Optional[int] = None
    forecast_kwp: Optional[float] = None

    def __post_init__(self):
        """Load values from environment variables and validate.

        Accumulates all validation errors before raising to allow
        operator to fix everything in one pass.

        Raises:
            ValueError: If any required fields are missing or validation fails.
                       Error message includes all validation failures.
        """
        errors = []

        # Load and validate required credentials
        self.api_key = os.environ.get("SOLAREDGE_API_KEY", "")
        if not self.api_key:
            errors.append("  - SOLAREDGE_API_KEY: SolarEdge API key (required)")

        # Site id is optional: read from the token file at runtime (D-14)
        self.site_id = os.environ.get("SOLAREDGE_SITE_ID", "").strip()

        # OAuth client credentials: no validation error when empty (D-13)
        self.client_id = os.environ.get("SOLAREDGE_CLIENT_ID", "").strip()
        self.client_secret = os.environ.get("SOLAREDGE_CLIENT_SECRET", "").strip()

        app_dir = Path(__file__).resolve().parent
        self.token_file = (
            os.environ.get("SOLAREDGE_TOKEN_FILE", "").strip()
            or str(app_dir / ".tokens.json")
        )
        self.env_file = str(app_dir / ".env")

        # Load and validate poll interval
        poll_str = os.environ.get("SOLAREDGE_POLL_INTERVAL", "5")
        try:
            self.poll_interval = int(poll_str)
            if self.poll_interval < 1:
                errors.append("  - SOLAREDGE_POLL_INTERVAL: Must be >= 1 minute")
        except ValueError:
            errors.append(f"  - SOLAREDGE_POLL_INTERVAL: Must be an integer (got '{poll_str}')")

        # Load and validate sleep start hour
        start_str = os.environ.get("SOLAREDGE_SLEEP_START", "0")
        try:
            self.sleep_start_hour = int(start_str)
            if not (0 <= self.sleep_start_hour <= 23):
                errors.append("  - SOLAREDGE_SLEEP_START: Must be 0-23")
        except ValueError:
            errors.append(f"  - SOLAREDGE_SLEEP_START: Must be an integer (got '{start_str}')")

        # Load and validate sleep end hour
        end_str = os.environ.get("SOLAREDGE_SLEEP_END", "6")
        try:
            self.sleep_end_hour = int(end_str)
            if not (0 <= self.sleep_end_hour <= 23):
                errors.append("  - SOLAREDGE_SLEEP_END: Must be 0-23")
        except ValueError:
            errors.append(f"  - SOLAREDGE_SLEEP_END: Must be an integer (got '{end_str}')")

        # Parse boolean (CRITICAL: avoid bool() trap where "false" is truthy)
        debug_str = os.environ.get("SOLAREDGE_DEBUG", "false").lower()
        self.debug = debug_str in ("true", "1", "yes", "on")

        # Load and validate log level
        log_level_str = os.environ.get("SOLAREDGE_LOG_LEVEL", "INFO").upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if log_level_str in valid_levels:
            self.log_level = log_level_str
        else:
            errors.append(f"  - SOLAREDGE_LOG_LEVEL: Must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL (got '{log_level_str}')")

        # Report all errors at once
        if errors:
            error_msg = "ERROR: Configuration validation failed:\n" + "\n".join(errors)
            raise ValueError(error_msg)

        # Optional forecast configuration (all 5 must be present to enable forecast screen)
        self.forecast_lat = self._load_optional_float("FORECAST_LAT")
        self.forecast_lon = self._load_optional_float("FORECAST_LON")
        self.forecast_tilt = self._load_optional_int("FORECAST_TILT", min_val=0, max_val=90)
        self.forecast_azimuth = self._load_optional_int("FORECAST_AZIMUTH", min_val=-180, max_val=180)
        self.forecast_kwp = self._load_optional_float("FORECAST_KWP")

    def log_startup(self):
        """Log configuration at startup with secrets masked.

        API key is masked to show only last 4 characters.
        All other values are shown in full.
        """
        # Mask API key (show last 4 chars, or **** if shorter)
        masked_key = f"****{self.api_key[-4:]}" if len(self.api_key) >= 4 else "****"

        logging.info("Configuration loaded:")
        logging.info(f"  SOLAREDGE_API_KEY: {masked_key}")
        if self.site_id:
            masked_site = f"****{self.site_id[-4:]}" if len(self.site_id) >= 4 else "****"
        else:
            masked_site = "(from token file)"
        logging.info(f"  SOLAREDGE_SITE_ID: {masked_site}")
        if self.client_id:
            masked_cid = f"****{self.client_id[-4:]}" if len(self.client_id) >= 4 else "****"
        else:
            masked_cid = "missing"
        logging.info(f"  SOLAREDGE_CLIENT_ID: {masked_cid}")
        # Never log any part of the secret (D-16)
        logging.info(f"  SOLAREDGE_CLIENT_SECRET: {'set' if self.client_secret else 'missing'}")
        logging.info(f"  SOLAREDGE_TOKEN_FILE: {self.token_file}")
        logging.info(f"  SOLAREDGE_POLL_INTERVAL: {self.poll_interval} min")
        logging.info(f"  SOLAREDGE_SLEEP_START: {self.sleep_start_hour}:00")
        logging.info(f"  SOLAREDGE_SLEEP_END: {self.sleep_end_hour}:00")
        logging.info(f"  SOLAREDGE_DEBUG: {self.debug}")
        logging.info(f"  SOLAREDGE_LOG_LEVEL: {self.log_level}")

        # Log forecast configuration status
        if self.has_forecast_config():
            logging.info(f"  Forecast: enabled (lat={self.forecast_lat}, lon={self.forecast_lon}, tilt={self.forecast_tilt}, azimuth={self.forecast_azimuth}, kwp={self.forecast_kwp})")
        else:
            logging.info("  Forecast: disabled (incomplete configuration)")

    @staticmethod
    def _load_optional_float(key: str) -> Optional[float]:
        """Load optional float from environment, return None if missing or invalid."""
        value = os.environ.get(key)
        if value is None or value.strip() == "":
            return None
        try:
            return float(value)
        except ValueError:
            logging.warning(f"{key}: Invalid float value '{value}', ignoring")
            return None

    @staticmethod
    def _load_optional_int(key: str, min_val: int = None, max_val: int = None) -> Optional[int]:
        """Load optional int from environment with range validation."""
        value = os.environ.get(key)
        if value is None or value.strip() == "":
            return None
        try:
            val = int(value)
            if min_val is not None and val < min_val:
                logging.warning(f"{key}: Value {val} below minimum {min_val}, ignoring")
                return None
            if max_val is not None and val > max_val:
                logging.warning(f"{key}: Value {val} above maximum {max_val}, ignoring")
                return None
            return val
        except ValueError:
            logging.warning(f"{key}: Invalid integer value '{value}', ignoring")
            return None

    def has_forecast_config(self) -> bool:
        """Return True if all 5 forecast parameters are configured."""
        return all([
            self.forecast_lat is not None,
            self.forecast_lon is not None,
            self.forecast_tilt is not None,
            self.forecast_azimuth is not None,
            self.forecast_kwp is not None,
        ])
