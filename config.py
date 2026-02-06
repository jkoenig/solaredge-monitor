"""
Configuration management for SolarEdge Off-Grid Monitor.

Loads all configuration from environment variables (with SOLAREDGE_ prefix).
Validates required fields and type-converts all values at startup.

Usage:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file first
    from config import Config
    config = Config()  # Loads from environment, validates, raises ValueError on errors
    config.log_startup()  # Logs with secrets masked
"""

from dataclasses import dataclass
import os
import logging


@dataclass
class Config:
    """Application configuration loaded from environment variables.

    All environment variables use SOLAREDGE_ prefix.

    Required fields (must be provided):
        - api_key: SolarEdge API key
        - site_id: SolarEdge site identifier

    Optional fields (with defaults):
        - poll_interval: Minutes between API polls (default: 5, minimum: 1)
        - sleep_start_hour: Hour to pause polling, 0-23 (default: 0 = midnight)
        - sleep_end_hour: Hour to resume polling, 0-23 (default: 6 = 6 AM)
        - debug: Enable debug mode (default: False)
    """

    # Required credentials
    api_key: str = ""
    site_id: str = ""

    # Optional operational settings with defaults
    poll_interval: int = 5
    sleep_start_hour: int = 0
    sleep_end_hour: int = 6
    debug: bool = False

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

        self.site_id = os.environ.get("SOLAREDGE_SITE_ID", "")
        if not self.site_id:
            errors.append("  - SOLAREDGE_SITE_ID: Site identifier (required)")

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

        # Report all errors at once
        if errors:
            error_msg = "ERROR: Configuration validation failed:\n" + "\n".join(errors)
            raise ValueError(error_msg)

    def log_startup(self):
        """Log configuration at startup with secrets masked.

        API key is masked to show only last 4 characters.
        All other values are shown in full.
        """
        # Mask API key (show last 4 chars, or **** if shorter)
        masked_key = f"****{self.api_key[-4:]}" if len(self.api_key) >= 4 else "****"

        logging.info("Configuration loaded:")
        logging.info(f"  SOLAREDGE_API_KEY: {masked_key}")
        logging.info(f"  SOLAREDGE_SITE_ID: {self.site_id}")
        logging.info(f"  SOLAREDGE_POLL_INTERVAL: {self.poll_interval} min")
        logging.info(f"  SOLAREDGE_SLEEP_START: {self.sleep_start_hour}:00")
        logging.info(f"  SOLAREDGE_SLEEP_END: {self.sleep_end_hour}:00")
        logging.info(f"  SOLAREDGE_DEBUG: {self.debug}")
