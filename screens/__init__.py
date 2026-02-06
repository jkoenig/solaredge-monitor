from screens.production import render_production_screen
from screens.consumption import render_consumption_screen
from screens.feed_in import render_feed_in_screen
from screens.purchased import render_purchased_screen

# Screen registry for cycling (Phase 5 polling loop uses this)
SCREENS = [
    render_production_screen,
    render_consumption_screen,
    render_feed_in_screen,
    render_purchased_screen,
]
