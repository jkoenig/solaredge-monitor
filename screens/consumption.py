"""
Verbrauch screen renderer.

Shows total consumption with breakdown of where the energy came from:
- Solar (self-consumption)
- Batterie (battery discharge)
- Netz (purchased from grid)
"""

from PIL import Image, ImageDraw
from models import EnergyDetails
from rendering.fonts import load_font
from rendering.icons import draw_sun_icon, draw_battery_icon, draw_grid_icon
from rendering.bars import draw_horizontal_bar


def render_consumption_screen(data: EnergyDetails) -> Image:
    """
    Render the Verbrauch screen showing consumption breakdown.

    Args:
        data: EnergyDetails instance with energy data

    Returns:
        1000x488 1-bit PIL Image ready for e-ink display
    """
    # Create image: mode '1' for 1-bit monochrome, white background (1)
    img = Image.new('1', (1000, 488), 1)
    draw = ImageDraw.Draw(img)

    # Load fonts (same sizes as production for consistency)
    label_font = load_font('Arial.ttf', 56)
    value_font = load_font('ArialBlack.ttf', 140)
    unit_font = load_font('Arial.ttf', 48)
    breakdown_label_font = load_font('Arial.ttf', 36)
    breakdown_value_font = load_font('Arial.ttf', 44)
    bar_font = load_font('Arial.ttf', 32)

    # TOP SECTION: Label, value, bar
    # "Verbrauch" label at top-left
    label_text = "Verbrauch"
    draw.text((30, 20), label_text, fill=0, font=label_font)

    # Main kWh value (large and bold)
    value_text = f"{data.consumption:.1f}"
    value_bbox = draw.textbbox((0, 0), value_text, font=value_font)
    value_width = value_bbox[2] - value_bbox[0]
    value_height = value_bbox[3] - value_bbox[1]
    value_x = 30
    value_y = 90
    draw.text((value_x, value_y), value_text, fill=0, font=value_font)

    # "kWh" unit text to the right, baseline-aligned
    unit_text = "kWh"
    unit_x = value_x + value_width + 20
    unit_bbox = draw.textbbox((0, 0), unit_text, font=unit_font)
    unit_height = unit_bbox[3] - unit_bbox[1]
    unit_y = value_y + value_height - unit_height
    draw.text((unit_x, unit_y), unit_text, fill=0, font=unit_font)

    # Horizontal bar showing percentage (consumption / 15.0 * 100, capped at 100%)
    bar_y = value_y + value_height + 30
    bar_bbox = (30, bar_y, 850, bar_y + 40)
    percentage = min(100.0, (data.consumption / 15.0) * 100.0)
    draw_horizontal_bar(draw, bar_bbox, percentage, bar_font)

    # BOTTOM SECTION: 3-column breakdown showing sources of consumption
    breakdown_y_start = bar_y + 80
    icon_size = 60
    column_width = 1000 // 3

    # Calculate battery energy: consumption - self_consumption - purchased
    battery_energy = max(0.0, data.consumption - data.self_consumption - data.purchased)

    # Column 1: Sun icon + "Solar" + self_consumption value
    col1_x = column_width // 2
    icon_x1 = col1_x - icon_size // 2
    draw_sun_icon(draw, icon_x1, breakdown_y_start, icon_size)

    label1 = "Solar"
    label1_bbox = draw.textbbox((0, 0), label1, font=breakdown_label_font)
    label1_width = label1_bbox[2] - label1_bbox[0]
    label1_x = col1_x - label1_width // 2
    label1_y = breakdown_y_start + icon_size + 10
    draw.text((label1_x, label1_y), label1, fill=0, font=breakdown_label_font)

    value1 = f"{data.self_consumption:.1f} kWh"
    value1_bbox = draw.textbbox((0, 0), value1, font=breakdown_value_font)
    value1_width = value1_bbox[2] - value1_bbox[0]
    value1_x = col1_x - value1_width // 2
    value1_y = label1_y + 45
    draw.text((value1_x, value1_y), value1, fill=0, font=breakdown_value_font)

    # Column 2: Battery icon + "Batterie" + battery energy
    col2_x = column_width + column_width // 2
    icon_x2 = col2_x - icon_size // 2
    draw_battery_icon(draw, icon_x2, breakdown_y_start, icon_size)

    label2 = "Batterie"
    label2_bbox = draw.textbbox((0, 0), label2, font=breakdown_label_font)
    label2_width = label2_bbox[2] - label2_bbox[0]
    label2_x = col2_x - label2_width // 2
    label2_y = breakdown_y_start + icon_size + 10
    draw.text((label2_x, label2_y), label2, fill=0, font=breakdown_label_font)

    value2 = f"{battery_energy:.1f} kWh"
    value2_bbox = draw.textbbox((0, 0), value2, font=breakdown_value_font)
    value2_width = value2_bbox[2] - value2_bbox[0]
    value2_x = col2_x - value2_width // 2
    value2_y = label2_y + 45
    draw.text((value2_x, value2_y), value2, fill=0, font=breakdown_value_font)

    # Column 3: Grid icon + "Netz" + purchased value
    col3_x = 2 * column_width + column_width // 2
    icon_x3 = col3_x - icon_size // 2
    draw_grid_icon(draw, icon_x3, breakdown_y_start, icon_size)

    label3 = "Netz"
    label3_bbox = draw.textbbox((0, 0), label3, font=breakdown_label_font)
    label3_width = label3_bbox[2] - label3_bbox[0]
    label3_x = col3_x - label3_width // 2
    label3_y = breakdown_y_start + icon_size + 10
    draw.text((label3_x, label3_y), label3, fill=0, font=breakdown_label_font)

    value3 = f"{data.purchased:.1f} kWh"
    value3_bbox = draw.textbbox((0, 0), value3, font=breakdown_value_font)
    value3_width = value3_bbox[2] - value3_bbox[0]
    value3_x = col3_x - value3_width // 2
    value3_y = label3_y + 45
    draw.text((value3_x, value3_y), value3, fill=0, font=breakdown_value_font)

    return img
