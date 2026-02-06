"""SolarEdge API client with automatic retry logic.

This module provides a client for the SolarEdge Monitoring API that handles
authentication, retry logic, and response parsing. All API errors are logged
and handled gracefully by returning None, allowing the application to continue
with stale data rather than crashing.

The client uses exponential backoff (2s, 4s, 8s) for transient failures and
includes a 10-second timeout per request.
"""

import logging
from datetime import datetime
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from models import PowerFlow, EnergyDetails, SiteOverview


class SolarEdgeAPI:
    """Client for SolarEdge Monitoring API with automatic retry.

    Handles all communication with the SolarEdge API, including authentication,
    retry logic for transient failures, and parsing responses into typed data models.

    Attributes:
        api_key: SolarEdge API key for authentication
        site_id: Site identifier for API requests
        base_url: Base URL for the SolarEdge Monitoring API
        session: Requests session configured with retry logic
    """

    def __init__(self, api_key: str, site_id: str):
        """Initialize API client with retry configuration.

        Args:
            api_key: SolarEdge API key
            site_id: Site identifier
        """
        self.api_key = api_key
        self.site_id = site_id
        self.base_url = "https://monitoringapi.solaredge.com"

        # Configure retry: 3 attempts, exponential backoff (2s, 4s, 8s)
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )

        # Create session with retry adapter
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """Execute API request with retry and error handling.

        Logs errors internally and returns None on failure, allowing the caller
        to continue with stale data or handle the failure gracefully.

        Args:
            endpoint: API endpoint path (e.g., "/site/123/overview")
            params: Additional query parameters (api_key added automatically)

        Returns:
            dict: JSON response on success
            None: On complete failure after retries
        """
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        params["api_key"] = self.api_key

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logging.error(f"API timeout after 10s: {endpoint}")
            return None
        except requests.exceptions.HTTPError as e:
            logging.error(f"API HTTP error {e.response.status_code}: {endpoint}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"API request failed: {endpoint} - {e}")
            return None

    def get_current_power_flow(self) -> Optional[PowerFlow]:
        """Fetch current power flow between system elements.

        Retrieves real-time power measurements showing energy flow between
        the grid, PV panels, battery, and load.

        Returns:
            PowerFlow: Current system state with power values in kW
            None: If API request fails after retries
        """
        endpoint = f"/site/{self.site_id}/currentPowerFlow"
        data = self._request(endpoint)

        if data is None:
            logging.warning("Failed to fetch power flow")
            return None

        try:
            flow = data["siteCurrentPowerFlow"]

            # Detect off-grid state from connections array
            # If first connection is not from grid, system is off-grid
            off_grid = False
            connections = flow.get("connections", [])
            if connections and connections[0].get("from", "").lower() != "grid":
                off_grid = True

            return PowerFlow(
                grid_power=float(flow["GRID"]["currentPower"]),
                load_power=float(flow["LOAD"]["currentPower"]),
                pv_power=float(flow["PV"]["currentPower"]),
                storage_power=float(flow["STORAGE"]["currentPower"]),
                storage_status=flow["STORAGE"]["status"],
                state_of_charge=int(flow["STORAGE"]["chargeLevel"]),
                off_grid=off_grid
            )
        except (KeyError, ValueError, TypeError) as e:
            logging.error(f"Failed to parse power flow response: {e}")
            return None

    def get_energy_details(self) -> Optional[EnergyDetails]:
        """Fetch today's cumulative energy data.

        Retrieves aggregated energy measurements for the current day, including
        production, consumption, and grid interactions.

        Returns:
            EnergyDetails: Today's energy totals in kWh
            None: If API request fails after retries
        """
        endpoint = f"/site/{self.site_id}/energyDetails"

        # Query today's data with all relevant meters
        today = datetime.now().strftime("%Y-%m-%d")
        params = {
            "meters": "Purchased,FeedIn,Production,SelfConsumption,Consumption",
            "startTime": f"{today} 00:00:00",
            "endTime": f"{today} 23:59:59"
        }

        data = self._request(endpoint, params)

        if data is None:
            logging.warning("Failed to fetch energy details")
            return None

        try:
            meters = data["energyDetails"]["meters"]

            # Extract values by meter type and convert Wh to kWh
            production = 0.0
            self_consumption = 0.0
            feed_in = 0.0
            consumption = 0.0
            purchased = 0.0

            for meter in meters:
                meter_type = meter.get("type", "")
                values = meter.get("values", [])
                # Sum all values for the day and convert Wh to kWh
                total_wh = sum(v.get("value", 0) for v in values if v.get("value") is not None)
                total_kwh = total_wh / 1000.0

                if meter_type == "Production":
                    production = total_kwh
                elif meter_type == "SelfConsumption":
                    self_consumption = total_kwh
                elif meter_type == "FeedIn":
                    feed_in = total_kwh
                elif meter_type == "Consumption":
                    consumption = total_kwh
                elif meter_type == "Purchased":
                    purchased = total_kwh

            return EnergyDetails(
                production=production,
                self_consumption=self_consumption,
                feed_in=feed_in,
                consumption=consumption,
                purchased=purchased
            )
        except (KeyError, ValueError, TypeError) as e:
            logging.error(f"Failed to parse energy details response: {e}")
            return None

    def get_site_overview(self) -> Optional[SiteOverview]:
        """Fetch site overview with historical data.

        Retrieves aggregate energy production statistics over various time periods,
        from a single day to the lifetime of the installation.

        Returns:
            SiteOverview: Historical energy production data
            None: If API request fails after retries
        """
        endpoint = f"/site/{self.site_id}/overview"
        data = self._request(endpoint)

        if data is None:
            logging.warning("Failed to fetch site overview")
            return None

        try:
            overview = data["overview"]

            return SiteOverview(
                last_update_time=overview.get("lastUpdateTime", ""),
                lifetime_energy=float(overview.get("lifeTimeData", {}).get("energy", 0.0)) / 1_000_000.0,  # Wh to MWh
                last_year_energy=float(overview.get("lastYearData", {}).get("energy", 0.0)) / 1000.0,  # Wh to kWh
                last_month_energy=float(overview.get("lastMonthData", {}).get("energy", 0.0)) / 1000.0,  # Wh to kWh
                last_day_energy=float(overview.get("lastDayData", {}).get("energy", 0.0)) / 1000.0  # Wh to kWh
            )
        except (KeyError, ValueError, TypeError) as e:
            logging.error(f"Failed to parse site overview response: {e}")
            return None
