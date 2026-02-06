"""
Rendering utilities for e-ink display output.

This package provides shared building blocks for screen renderers:
- Font loading with caching and fallback
- Geometric icon drawing (battery, house, grid, sun)
- Horizontal bar chart drawing with percentage display
"""

from rendering.fonts import load_font
from rendering.icons import draw_battery_icon, draw_house_icon, draw_grid_icon, draw_sun_icon
from rendering.bars import draw_horizontal_bar

__all__ = [
    'load_font',
    'draw_battery_icon',
    'draw_house_icon',
    'draw_grid_icon',
    'draw_sun_icon',
    'draw_horizontal_bar',
]
