"""
Structured JSON logging setup for SolarEdge Off-Grid Monitor.

Provides unified logging configuration for both console (systemd) and file output.
All logs use JSON format for structured parsing and analysis.

Usage:
    from logging_setup import setup_logging
    logger = setup_logging(log_level="INFO", log_file="solaredge_monitor.log")
    logger.info("Application started", extra={"version": "1.0"})
"""

import logging
from logging.handlers import RotatingFileHandler
from pythonjsonlogger.json import JsonFormatter


def setup_logging(log_level: str = "INFO", log_file: str = "solaredge_monitor.log") -> logging.Logger:
    """Configure structured JSON logging with console and file output.

    Sets up two handlers:
    1. StreamHandler to stdout (captured by systemd)
    2. RotatingFileHandler with 10MB rotation, 5 backups (60MB max)

    Both handlers use JSON formatting for structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (default: solaredge_monitor.log)

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

    # Rotating file handler (10MB per file, 5 backups = 60MB max)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10_000_000,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return root_logger
