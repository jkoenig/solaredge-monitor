"""
Einspeisung screen renderer.

Full-screen display showing total energy fed into the grid.
Uses all available space for maximum readability.
"""

from PIL import Image, ImageDraw
from models import EnergyDetails
from rendering.fonts import load_font
from rendering.bars import draw_horizontal_bar


def render_feed_in_screen(data: EnergyDetails) -> Image:
    """
    Render the Einspeisung screen showing grid feed-in.

    Args:
        data: EnergyDetails instance with energy data

    Returns:
        1000x488 1-bit PIL Image ready for e-ink display
    """
    # Create image: mode '1' for 1-bit monochrome, white background (1)
    img = Image.new('1', (1000, 488), 1)
    draw = ImageDraw.Draw(img)

    # Load fonts (larger than complex screens since we have more space)
    label_font = load_font('Arial.ttf', 64)
    value_font = load_font('ArialBlack.ttf', 180)
    unit_font = load_font('Arial.ttf', 56)
    bar_font = load_font('Arial.ttf', 36)

    # Calculate vertical centering
    # Total height needed: label + value + unit + bar
    total_content_height = 320  # Approximate
    start_y = (488 - total_content_height) // 2

    # "Einspeisung" label
    label_text = "Einspeisung"
    label_bbox = draw.textbbox((0, 0), label_text, font=label_font)
    label_width = label_bbox[2] - label_bbox[0]
    label_x = (1000 - label_width) // 2  # Center horizontally
    label_y = start_y
    draw.text((label_x, label_y), label_text, fill=0, font=label_font)

    # Main kWh value (extra large)
    value_text = f"{data.feed_in:.1f}"
    value_bbox = draw.textbbox((0, 0), value_text, font=value_font)
    value_width = value_bbox[2] - value_bbox[0]
    value_height = value_bbox[3] - value_bbox[1]
    value_y = label_y + 90

    # "kWh" unit text to the right, baseline-aligned
    unit_text = "kWh"
    unit_bbox = draw.textbbox((0, 0), unit_text, font=unit_font)
    unit_width = unit_bbox[2] - unit_bbox[0]
    unit_height = unit_bbox[3] - unit_bbox[1]

    # Center the value+unit combo
    total_width = value_width + 20 + unit_width
    value_x = (1000 - total_width) // 2
    unit_x = value_x + value_width + 20
    unit_y = value_y + value_height - unit_height

    draw.text((value_x, value_y), value_text, fill=0, font=value_font)
    draw.text((unit_x, unit_y), unit_text, fill=0, font=unit_font)

    # Horizontal bar showing feed_in as percentage of production
    bar_y = value_y + value_height + 60
    bar_bbox = (100, bar_y, 850, bar_y + 50)
    percentage = min(100.0, (data.feed_in / data.production) * 100.0) if data.production > 0 else 0.0
    draw_horizontal_bar(draw, bar_bbox, percentage, bar_font, label="Anteil Produktion")

    return img
