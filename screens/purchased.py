"""
Bezug screen renderer.

Shows total energy purchased from the grid.
Uses unified layout grid matching all other screens.
"""

from PIL import Image, ImageDraw
from models import EnergyDetails
from rendering.fonts import load_font
from rendering.bars import draw_horizontal_bar

# Unified layout constants (shared across all screens)
MARGIN = 5
CANVAS_W, CANVAS_H = 1000, 488


def render_purchased_screen(data: EnergyDetails) -> Image:
    """
    Render the Bezug screen showing grid purchase.

    Args:
        data: EnergyDetails instance with energy data

    Returns:
        1000x488 1-bit PIL Image ready for e-ink display
    """
    img = Image.new('1', (CANVAS_W, CANVAS_H), 1)
    draw = ImageDraw.Draw(img)

    # Fonts (unified across all screens)
    label_font = load_font('Arial.ttf', 60)
    value_font = load_font('ArialBlack.ttf', 120)
    unit_font = load_font('Arial.ttf', 64)
    bar_font = load_font('Arial.ttf', 44)

    # --- HEADLINE: top-left ---
    label_text = "Bezug"
    draw.text((MARGIN, MARGIN), label_text, fill=0, font=label_font)
    label_bbox = draw.textbbox((MARGIN, MARGIN), label_text, font=label_font)
    label_bottom = label_bbox[3]

    # --- VALUE+BAR GROUP: vertically centered between headline and bottom ---
    value_text = f"{data.purchased:.1f}"
    value_measure = draw.textbbox((0, 0), value_text, font=value_font)
    value_h = value_measure[3]

    bar_h = 40
    gap_value_bar = 20
    gap_bar_label = 5
    bar_label_text = "Anteil Verbrauch 100%"
    bar_label_measure = draw.textbbox((0, 0), bar_label_text, font=bar_font)
    bar_label_h = bar_label_measure[3]

    group_h = value_h + gap_value_bar + bar_h + gap_bar_label + bar_label_h
    available_top = label_bottom
    available_bottom = CANVAS_H - MARGIN - 100  # same as breakdown_y_start on other screens
    value_y = available_top + (available_bottom - available_top - group_h) // 2

    draw.text((MARGIN, value_y), value_text, fill=0, font=value_font)
    value_actual = draw.textbbox((MARGIN, value_y), value_text, font=value_font)

    unit_text = "kWh"
    unit_x = value_actual[2] + 20
    unit_actual = draw.textbbox((unit_x, value_y), unit_text, font=unit_font)
    unit_y = value_actual[3] - (unit_actual[3] - unit_actual[1])
    draw.text((unit_x, unit_y), unit_text, fill=0, font=unit_font)

    bar_y = value_y + value_h + gap_value_bar
    bar_bbox = (MARGIN, bar_y, CANVAS_W - MARGIN, bar_y + bar_h)
    percentage = min(100.0, (data.purchased / data.consumption) * 100.0) if data.consumption > 0 else 0.0
    draw_horizontal_bar(draw, bar_bbox, percentage, bar_font, label="Anteil Verbrauch")

    return img
