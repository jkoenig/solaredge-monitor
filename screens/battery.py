"""
Hausakku screen renderer.

Shows battery state of charge with status and details:
- SOC percentage as big value with bar
- Power legend (Laden/Entladen mit x kW)
- 2-column breakdown: Temperatur + Verfügbar
"""

from PIL import Image, ImageDraw
from models import BatteryData
from rendering.fonts import load_font

# Unified layout constants (shared across all screens)
MARGIN = 5
CANVAS_W, CANVAS_H = 1000, 488

# Status translation map
STATUS_MAP = {
    "Charge": "Lädt",
    "Discharge": "Entlädt",
    "Idle": "Leerlauf",
}


def render_battery_screen(data: BatteryData) -> Image:
    """
    Render the Hausakku screen showing battery state.

    Args:
        data: BatteryData instance with battery state

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
    label_text = "Hausakku"
    draw.text((MARGIN, MARGIN), label_text, fill=0, font=label_font)
    label_bbox = draw.textbbox((MARGIN, MARGIN), label_text, font=label_font)
    label_bottom = label_bbox[3]

    # --- 2-COLUMN BREAKDOWN: sticky to bottom ---
    # Labels with descenders (Temperatur/Verfügbar) are 10px taller than
    # production labels, so reserve 125px instead of 110px
    breakdown_y_start = CANVAS_H - MARGIN - 125

    # --- VALUE+BAR GROUP: vertically centered between headline and breakdown ---
    value_text = f"{data.state_of_charge}"
    value_measure = draw.textbbox((0, 0), value_text, font=value_font)
    value_h = value_measure[3]

    bar_h = 40
    gap_value_bar = 20
    gap_bar_label = 5
    status_german = STATUS_MAP.get(data.status, data.status)
    power_kw = abs(data.power)
    if data.status == "Idle":
        bar_label_text = ""
    else:
        bar_label_text = f"{status_german} mit {power_kw:.1f} kW"
    bar_label_measure = draw.textbbox((0, 0), bar_label_text, font=bar_font)
    bar_label_h = bar_label_measure[3]

    group_h = value_h + gap_value_bar + bar_h + gap_bar_label + bar_label_h
    available_top = label_bottom
    available_bottom = breakdown_y_start
    value_y = available_top + (available_bottom - available_top - group_h) // 2

    draw.text((MARGIN, value_y), value_text, fill=0, font=value_font)
    value_actual = draw.textbbox((MARGIN, value_y), value_text, font=value_font)

    # Unit: "%" baseline-aligned to value
    unit_text = "%"
    unit_x = value_actual[2] + 20
    unit_actual = draw.textbbox((unit_x, value_y), unit_text, font=unit_font)
    unit_y = value_actual[3] - (unit_actual[3] - unit_actual[1])
    draw.text((unit_x, unit_y), unit_text, fill=0, font=unit_font)

    # Bar: SOC fill (drawn manually to use custom legend instead of percentage)
    bar_y = value_y + value_h + gap_value_bar
    soc = max(0.0, min(100.0, float(data.state_of_charge)))
    bar_x0, bar_x1 = MARGIN, CANVAS_W - MARGIN
    draw.rectangle((bar_x0, bar_y, bar_x1, bar_y + bar_h), outline=0, width=4)
    fill_width = int((soc / 100.0) * (bar_x1 - bar_x0))
    if fill_width > 0:
        draw.rectangle((bar_x0, bar_y, bar_x0 + fill_width, bar_y + bar_h), fill=0)

    # Bar legend: power info
    legend_y = bar_y + bar_h + gap_bar_label
    draw.text((MARGIN, legend_y), bar_label_text, fill=0, font=bar_font)

    # --- 2-COLUMN BREAKDOWN: Temperatur + Verfügbar ---
    content_width = CANVAS_W - 2 * MARGIN
    column_width = content_width // 2

    # Column 1: Temperatur
    col1_x = MARGIN + column_width // 2

    label1 = "Temperatur"
    label1_bbox = draw.textbbox((0, 0), label1, font=breakdown_label_font)
    label1_width = label1_bbox[2] - label1_bbox[0]
    label1_x = col1_x - label1_width // 2
    draw.text((label1_x, breakdown_y_start), label1, fill=0, font=breakdown_label_font)

    label1_measured = draw.textbbox((label1_x, breakdown_y_start), label1, font=breakdown_label_font)
    label1_bottom = label1_measured[3]

    value1 = f"{data.internal_temp:.0f}\u00b0C"
    value1_bbox = draw.textbbox((0, 0), value1, font=breakdown_value_font)
    value1_width = value1_bbox[2] - value1_bbox[0]
    value1_x = col1_x - value1_width // 2
    value1_y = label1_bottom + 8
    draw.text((value1_x, value1_y), value1, fill=0, font=breakdown_value_font)

    # Column 2: Verfügbar
    col2_x = MARGIN + column_width + column_width // 2

    label2 = "Verfügbar"
    label2_bbox = draw.textbbox((0, 0), label2, font=breakdown_label_font)
    label2_width = label2_bbox[2] - label2_bbox[0]
    label2_x = col2_x - label2_width // 2
    draw.text((label2_x, breakdown_y_start), label2, fill=0, font=breakdown_label_font)

    label2_measured = draw.textbbox((label2_x, breakdown_y_start), label2, font=breakdown_label_font)
    label2_bottom = label2_measured[3]

    value2 = f"{data.available_energy:.1f} kWh"
    value2_bbox = draw.textbbox((0, 0), value2, font=breakdown_value_font)
    value2_width = value2_bbox[2] - value2_bbox[0]
    value2_x = col2_x - value2_width // 2
    value2_y = label2_bottom + 8
    draw.text((value2_x, value2_y), value2, fill=0, font=breakdown_value_font)

    return img
