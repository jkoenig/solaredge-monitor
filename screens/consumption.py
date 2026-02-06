"""
Verbrauch screen renderer.

Shows total consumption with breakdown of where the energy came from:
- Von PV (self-consumption)
- Von Akku (battery discharge)
- Vom Netz (purchased from grid)
"""

from PIL import Image, ImageDraw
from models import EnergyDetails
from rendering.fonts import load_font
from rendering.bars import draw_horizontal_bar

# Unified layout constants (shared across all screens)
MARGIN = 5
CANVAS_W, CANVAS_H = 1000, 488


def render_consumption_screen(data: EnergyDetails) -> Image:
    """
    Render the Verbrauch screen showing consumption breakdown.

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
    breakdown_label_font = load_font('Arial.ttf', 52)
    breakdown_value_font = load_font('Arial.ttf', 60)
    bar_font = load_font('Arial.ttf', 56)

    # --- HEADLINE: top-left ---
    label_text = "Verbrauch"
    draw.text((MARGIN, MARGIN), label_text, fill=0, font=label_font)
    label_bbox = draw.textbbox((MARGIN, MARGIN), label_text, font=label_font)
    label_bottom = label_bbox[3]

    # --- 3-COLUMN BREAKDOWN: sticky to bottom ---
    # label(~52) + gap(8) + value(~60) = ~110px
    breakdown_y_start = CANVAS_H - MARGIN - 110

    # --- VALUE+BAR GROUP: vertically centered between headline and breakdown ---
    value_text = f"{data.consumption:.1f}"
    value_measure = draw.textbbox((0, 0), value_text, font=value_font)
    value_h = value_measure[3]

    bar_h = 40
    gap_value_bar = 20
    gap_bar_label = 5
    bar_label_text = "Solaranteil 100%"
    bar_label_measure = draw.textbbox((0, 0), bar_label_text, font=bar_font)
    bar_label_h = bar_label_measure[3]

    group_h = value_h + gap_value_bar + bar_h + gap_bar_label + bar_label_h
    available_top = label_bottom
    available_bottom = breakdown_y_start
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
    percentage = min(100.0, (data.self_consumption / data.consumption) * 100.0) if data.consumption > 0 else 0.0
    draw_horizontal_bar(draw, bar_bbox, percentage, bar_font, label="Solaranteil")

    content_width = CANVAS_W - 2 * MARGIN
    column_width = content_width // 3

    battery_energy = max(0.0, data.consumption - data.self_consumption - data.purchased)

    # Column 1: "Von PV" + self_consumption value
    col1_x = MARGIN + column_width // 2

    label1 = "Von PV"
    label1_bbox = draw.textbbox((0, 0), label1, font=breakdown_label_font)
    label1_width = label1_bbox[2] - label1_bbox[0]
    label1_x = col1_x - label1_width // 2
    draw.text((label1_x, breakdown_y_start), label1, fill=0, font=breakdown_label_font)

    label1_measured = draw.textbbox((label1_x, breakdown_y_start), label1, font=breakdown_label_font)
    label1_bottom = label1_measured[3]

    value1 = f"{data.self_consumption:.1f} kWh"
    value1_bbox = draw.textbbox((0, 0), value1, font=breakdown_value_font)
    value1_width = value1_bbox[2] - value1_bbox[0]
    value1_x = col1_x - value1_width // 2
    value1_y = label1_bottom + 8
    draw.text((value1_x, value1_y), value1, fill=0, font=breakdown_value_font)

    # Column 2: "Von Akku" + battery energy
    col2_x = MARGIN + column_width + column_width // 2

    label2 = "Von Akku"
    label2_bbox = draw.textbbox((0, 0), label2, font=breakdown_label_font)
    label2_width = label2_bbox[2] - label2_bbox[0]
    label2_x = col2_x - label2_width // 2
    draw.text((label2_x, breakdown_y_start), label2, fill=0, font=breakdown_label_font)

    label2_measured = draw.textbbox((label2_x, breakdown_y_start), label2, font=breakdown_label_font)
    label2_bottom = label2_measured[3]

    value2 = f"{battery_energy:.1f} kWh"
    value2_bbox = draw.textbbox((0, 0), value2, font=breakdown_value_font)
    value2_width = value2_bbox[2] - value2_bbox[0]
    value2_x = col2_x - value2_width // 2
    value2_y = label2_bottom + 8
    draw.text((value2_x, value2_y), value2, fill=0, font=breakdown_value_font)

    # Column 3: "Vom Netz" + purchased value
    col3_x = MARGIN + 2 * column_width + column_width // 2

    label3 = "Vom Netz"
    label3_bbox = draw.textbbox((0, 0), label3, font=breakdown_label_font)
    label3_width = label3_bbox[2] - label3_bbox[0]
    label3_x = col3_x - label3_width // 2
    draw.text((label3_x, breakdown_y_start), label3, fill=0, font=breakdown_label_font)

    label3_measured = draw.textbbox((label3_x, breakdown_y_start), label3, font=breakdown_label_font)
    label3_bottom = label3_measured[3]

    value3 = f"{data.purchased:.1f} kWh"
    value3_bbox = draw.textbbox((0, 0), value3, font=breakdown_value_font)
    value3_width = value3_bbox[2] - value3_bbox[0]
    value3_x = col3_x - value3_width // 2
    value3_y = label3_bottom + 8
    draw.text((value3_x, value3_y), value3, fill=0, font=breakdown_value_font)

    return img
