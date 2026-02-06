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
