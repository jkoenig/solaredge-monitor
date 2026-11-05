"""Data models for SolarEdge API responses.

This module defines the data layer foundation for the SolarEdge monitoring system.
Each model represents a specific API response type with typed fields and immutable
instances to ensure data consistency throughout the application.

All models include a fetched_at timestamp to track when the data was retrieved.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class EnergyDetails:
    """Today's cumulative energy data.

    Represents aggregated energy measurements for the current day. All values
    reset at midnight and accumulate throughout the day.

    Source is the V2 site overview. All values are kWh, converted from the
    response unit; null is 0.

    Fields:
        production: production.total
        self_consumption: production.toSelfConsumption
        feed_in: production.toGrid
        consumption: consumption.total
        purchased: consumption.fromGrid
        to_storage: production.toStorage (energy charged into the battery)
        from_pv: consumption.fromPv (consumption covered directly by PV)
        from_storage: consumption.fromStorage (consumption covered by the battery)
        fetched_at: Timestamp when data was retrieved
    """
    production: float
    self_consumption: float
    feed_in: float
    consumption: float
    purchased: float
    to_storage: float = 0.0
    from_pv: float = 0.0
    from_storage: float = 0.0
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
        state_of_charge: stateOfEnergy (int %) from /storage/telemetry
        status: "Charge"/"Discharge"/"Idle", derived from chargePower - dischargePower
            with an idle threshold
        internal_temp: Battery temperature in °C from /storage/status internalTemperature
        available_energy: remainingEnergy in kWh, the energy currently stored,
            NOT the pack size
        power: Net battery power in kW, positive = charging
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
        actual_production: Actual PV production today in kWh (from overview production.total, for progress bar)
        fetched_at: Timestamp when data was retrieved
    """
    today_kwh: float
    tomorrow_kwh: float
    actual_production: float = 0.0
    fetched_at: datetime = field(default_factory=datetime.now)
