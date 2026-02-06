from screens.production import render_production_screen
from screens.consumption import render_consumption_screen
from screens.feed_in import render_feed_in_screen
from screens.purchased import render_purchased_screen
from screens.battery import render_battery_screen
from screens.history import render_history_production_screen, render_history_consumption_screen
from screens.forecast import render_forecast_screen

# Legacy screen list (energy screens only)
SCREENS = [
    render_production_screen,
    render_consumption_screen,
    render_feed_in_screen,
    render_purchased_screen,
]


def get_screens(has_battery=False, has_forecast_config=False):
    """Build dynamic screen list based on system capabilities.

    Returns list of (render_fn, data_key, name) tuples where data_key
    indicates which data object the render function expects:
    - "energy": EnergyDetails
    - "battery": BatteryData
    - "history": EnergyHistory
    - "forecast": ForecastData

    Args:
        has_battery: Whether the site has a battery installed
        has_forecast_config: Whether all 5 FORECAST_* env vars are set
    """
    screens = [
        (render_production_screen, "energy", "Produktion"),
        (render_consumption_screen, "energy", "Verbrauch"),
        (render_feed_in_screen, "energy", "Einspeisung"),
        (render_purchased_screen, "energy", "Bezug"),
    ]
    if has_battery:
        screens.append((render_battery_screen, "battery", "Hausakku"))
    if has_forecast_config:
        screens.append((render_forecast_screen, "forecast", "Prognose"))
    screens.append((render_history_production_screen, "history", "Verlauf Produktion"))
    screens.append((render_history_consumption_screen, "history", "Verlauf Verbrauch"))
    return screens
