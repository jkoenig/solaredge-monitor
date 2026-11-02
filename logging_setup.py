"""
Structured JSON logging setup for SolarEdge Off-Grid Monitor.

Logs go to stdout (captured by the systemd journal). A log file is written only
when SOLAREDGE_LOG_FILE is set, to keep SD card writes low on the Pi.
All logs use JSON format for structured parsing and analysis.

Usage:
    from logging_setup import setup_logging
    logger = setup_logging(log_level="INFO")
    logger.info("Application started", extra={"version": "1.0"})
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pythonjsonlogger.json import JsonFormatter


def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Configure structured JSON logging.

    Sets up:
    1. StreamHandler to stdout (captured by the systemd journal, which is
       size-capped on the Pi)
    2. Optionally a RotatingFileHandler (1MB rotation, 2 backups) when a log
       file is given or SOLAREDGE_LOG_FILE is set. Off by default: every line
       would otherwise be written twice to the SD card.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (default: SOLAREDGE_LOG_FILE, else none)

    Returns:
        Configured root logger
    """
    # Create JSON formatter
    formatter = JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

    # Console handler (stdout for systemd)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())
    root_logger.addHandler(console_handler)

    # Optional rotating file handler (1MB per file, 2 backups = 3MB max)
    log_file = log_file or os.environ.get("SOLAREDGE_LOG_FILE", "").strip() or None
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1_000_000,  # 1MB
            backupCount=2,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger
