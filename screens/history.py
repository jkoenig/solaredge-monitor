"""
History histogram screen renderer.

Shows 14-day daily bar charts for production or consumption.
Two public entry points share a single private renderer.
"""

from PIL import Image, ImageDraw
from models import EnergyHistory
from rendering.fonts import load_font

MARGIN = 5
CANVAS_W, CANVAS_H = 1000, 488


def render_history_production_screen(data: EnergyHistory) -> Image:
    return _render_history(data, data.production, "Produktion")


def render_history_consumption_screen(data: EnergyHistory) -> Image:
    return _render_history(data, data.consumption, "Verbrauch")


def _render_history(data: EnergyHistory, values: list, label: str) -> Image:
    """Render a 14-day histogram screen.

    Layout:
        Headline "Letzte 2 Wochen" (Arial 60) at top
        Sub-label with label left + "max: X.X kWh" right (Arial 44)
        14 vertical bars proportional to max value
        Date labels (DD) below bars (Arial 36)
    """
    img = Image.new('1', (CANVAS_W, CANVAS_H), 1)
    draw = ImageDraw.Draw(img)

    headline_font = load_font('Arial.ttf', 60)
    sub_font = load_font('Arial.ttf', 44)
    date_font = load_font('Arial.ttf', 36)

    # --- HEADLINE ---
    headline = "Letzte 2 Wochen"
    draw.text((MARGIN, MARGIN), headline, fill=0, font=headline_font)
    headline_bbox = draw.textbbox((MARGIN, MARGIN), headline, font=headline_font)
    headline_bottom = headline_bbox[3]

    # --- SUB-LABEL ---
    sub_y = headline_bottom + 8
    max_val = max(values) if values else 0.0
    max_text = f"max: {max_val:.1f} kWh"

    draw.text((MARGIN, sub_y), label, fill=0, font=sub_font)

    max_bbox = draw.textbbox((0, 0), max_text, font=sub_font)
    max_text_w = max_bbox[2] - max_bbox[0]
    draw.text((CANVAS_W - MARGIN - max_text_w, sub_y), max_text, fill=0, font=sub_font)

    sub_bbox = draw.textbbox((MARGIN, sub_y), label, font=sub_font)
    sub_bottom = sub_bbox[3]

    # --- DATE LABELS (bottom) ---
    # Measure date label height
    sample_date_bbox = draw.textbbox((0, 0), "31", font=date_font)
    date_label_h = sample_date_bbox[3]
    date_label_y = CANVAS_H - MARGIN - date_label_h

    # --- BAR AREA ---
    bar_top = sub_bottom + 15
    bar_bottom = date_label_y - 8  # gap between bars and date labels
    bar_area_h = bar_bottom - bar_top

    # Bar geometry: 14 bars with 6px gaps
    content_width = CANVAS_W - 2 * MARGIN
    num_bars = len(values)
    gap = 6
    bar_width = (content_width - (num_bars - 1) * gap) // num_bars

    for i, val in enumerate(values):
        bar_x = MARGIN + i * (bar_width + gap)

        # Draw bar (height proportional to max)
        if val > 0 and max_val > 0:
            bar_h = int((val / max_val) * bar_area_h)
            bar_h = max(bar_h, 2)  # minimum visible height
            draw.rectangle(
                [bar_x, bar_bottom - bar_h, bar_x + bar_width, bar_bottom],
                fill=0,
            )

        # Draw date label centered below bar
        date_str = data.dates[i][-2:]  # DD from YYYY-MM-DD
        date_bbox = draw.textbbox((0, 0), date_str, font=date_font)
        date_w = date_bbox[2] - date_bbox[0]
        date_x = bar_x + (bar_width - date_w) // 2
        draw.text((date_x, date_label_y), date_str, fill=0, font=date_font)

    return img
