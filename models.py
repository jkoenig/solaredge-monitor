"""Data models for SolarEdge API responses.

This module defines the data layer foundation for the SolarEdge monitoring system.
Each model represents a specific API response type with typed fields and immutable
instances to ensure data consistency throughout the application.

All models include a fetched_at timestamp to track when the data was retrieved.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class PowerFlow:
    """Current power flow between system elements.

    Represents real-time power measurements at a specific moment. Negative and
    positive values indicate direction of energy flow.

    Fields:
        grid_power: Power from/to grid in kW (negative = purchasing, positive = feeding in)
        load_power: Current consumption in kW
        pv_power: Current PV production in kW
        storage_power: Battery power in kW (negative = charging, positive = discharging)
        storage_status: Battery state ("Charge", "Discharge", "Idle")
        state_of_charge: Battery level as percentage (0-100)
        off_grid: Whether system is disconnected from grid
        fetched_at: Timestamp when data was retrieved
    """
    grid_power: float
    load_power: float
    pv_power: float
    storage_power: float
    storage_status: str
    state_of_charge: int
    off_grid: bool
    fetched_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class EnergyDetails:
    """Today's cumulative energy data.

    Represents aggregated energy measurements for the current day. All values
    reset at midnight and accumulate throughout the day.

    Fields:
        production: Total PV production today in kWh
        self_consumption: Energy consumed from own production in kWh
        feed_in: Energy exported to grid in kWh
        consumption: Total consumption today in kWh
        purchased: Energy purchased from grid in kWh
        fetched_at: Timestamp when data was retrieved
    """
    production: float
    self_consumption: float
    feed_in: float
    consumption: float
    purchased: float
    fetched_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class SiteOverview:
    """Site overview with historical data.

    Represents aggregate energy production statistics over various time periods,
    from a single day to the lifetime of the installation.

    Fields:
        last_update_time: API timestamp of last update
        lifetime_energy: Total production since installation in MWh
        last_year_energy: Production in last 12 months in kWh
        last_month_energy: Production in last 30 days in kWh
        last_day_energy: Production yesterday in kWh
        fetched_at: Timestamp when data was retrieved
    """
    last_update_time: str
    lifetime_energy: float
    last_year_energy: float
    last_month_energy: float
    last_day_energy: float
    fetched_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class EnergyHistory:
    """14-day daily energy history for histogram screens.

    Fields:
        dates: List of date strings ["2026-01-23", ...], length 14
        production: Daily production in kWh, length 14 (0.0 for null days)
        consumption: Daily consumption in kWh, length 14 (0.0 for null days)
        fetched_at: Timestamp when data was retrieved
    """
    dates: list
    production: list
    consumption: list
    fetched_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class BatteryData:
    """Current battery state for Akku screen.

    Fields:
        state_of_charge: Battery level 0-100% (from PowerFlow)
        status: "Charge"/"Discharge"/"Idle" (from PowerFlow)
        internal_temp: Battery temperature in °C (from storageData)
        available_energy: Available energy in kWh (from storageData)
        power: Battery power in kW (from storageData)
        fetched_at: Timestamp when data was retrieved
    """
    state_of_charge: int
    status: str
    internal_temp: float
    available_energy: float
    power: float
    fetched_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class ForecastData:
    """Solar production forecast for today and tomorrow.

    Data from Forecast.Solar API, cached for 1 hour.

    Fields:
        today_kwh: Forecasted production for today in kWh
        tomorrow_kwh: Forecasted production for tomorrow in kWh
        fetched_at: Timestamp when data was retrieved
    """
    today_kwh: float
    tomorrow_kwh: float
    fetched_at: datetime = field(default_factory=datetime.now)
