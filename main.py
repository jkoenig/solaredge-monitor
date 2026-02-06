#!/usr/bin/env python3
"""
SolarEdge Off-Grid Monitor - Main Entry Point

Run with: python3 main.py

Requires .env file with:
  SOLAREDGE_API_KEY=your_api_key
  SOLAREDGE_SITE_ID=your_site_id
"""

import logging
import sys

from dotenv import load_dotenv

# Load .env before importing Config (Config reads from environment)
load_dotenv()

from config import Config
from models import PowerFlow, EnergyDetails, SiteOverview
from solaredge_api import SolarEdgeAPI
from display import Display


def main():
    """Main entry point - verify modules work together."""
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    logging.info("SolarEdge Off-Grid Monitor starting...")

    # Load and validate configuration
    try:
        config = Config()
        config.log_startup()
    except ValueError as e:
        logging.error(str(e))
        sys.exit(1)

    # Create API client
    api = SolarEdgeAPI(config.api_key, config.site_id)
    logging.info("API client initialized")

    # Create display (debug mode from config)
    display = Display(debug_mode=config.debug)
    logging.info(f"Display initialized (backend: {display.backend})")

    # Test API call (will fail without valid credentials, but proves wiring works)
    logging.info("Testing API connection...")
    power_flow = api.get_current_power_flow()
    if power_flow:
        logging.info(f"Power flow: {power_flow}")
    else:
        logging.warning("Could not fetch power flow (check API credentials)")

    logging.info("Module integration verified. Full polling loop will be implemented in Phase 5.")


if __name__ == "__main__":
    main()
