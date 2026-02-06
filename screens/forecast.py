"""
Prognose screen renderer.

Shows today's solar production forecast with progress bar comparing
actual production vs forecast, and tomorrow's forecast with delta.
"""

from datetime import datetime
from PIL import Image, ImageDraw
from models import ForecastData
from rendering.fonts import load_font

# Unified layout constants (shared across all screens)
MARGIN = 5
CANVAS_W, CANVAS_H = 1000, 488


def render_forecast_screen(data: ForecastData) -> Image:
    """
    Render the Prognose screen showing forecast vs actual production.

    Args:
        data: ForecastData instance with forecast and actual production

    Returns:
        1000x488 1-bit PIL Image ready for e-ink display
    """
    img = Image.new('1', (CANVAS_W, CANVAS_H), 1)
    draw = ImageDraw.Draw(img)

    # Fonts (unified across all screens)
    label_font = load_font('Arial.ttf', 60)
    value_font = load_font('ArialBlack.ttf', 120)
    unit_font = load_font('Arial.ttf', 64)
    breakdown_value_font = load_font('Arial.ttf', 60)
    bar_font = load_font('Arial.ttf', 56)
    stale_font = load_font('Arial.ttf', 36)

    # --- HEADLINE: top-left ---
    label_text = "Prognose, heute"
    draw.text((MARGIN, MARGIN), label_text, fill=0, font=label_font)
    label_bbox = draw.textbbox((MARGIN, MARGIN), label_text, font=label_font)
    label_bottom = label_bbox[3]

    # --- BREAKDOWN: sticky to bottom ---
    breakdown_y_start = CANVAS_H - MARGIN - 110

    # --- VALUE+BAR GROUP: vertically centered between headline and breakdown ---
    value_text = f"{data.today_kwh:.1f}"
    value_measure = draw.textbbox((0, 0), value_text, font=value_font)
    value_h = value_measure[3]  # distance from draw position to visual bottom

    bar_h = 40
    gap_value_bar = 20
    gap_bar_label = 5

    # Calculate percentage for sizing (will be recalculated for legend)
    percentage = (data.actual_production / data.today_kwh * 100.0) if data.today_kwh > 0 else 0.0

    # Bar label sizing
    if data.today_kwh > 0:
        bar_label_text = f"{int(percentage)}% der Prognose erreicht"
    else:
        bar_label_text = "Keine Prognose verfügbar"
    bar_label_measure = draw.textbbox((0, 0), bar_label_text, font=bar_font)
    bar_label_h = bar_label_measure[3]

    group_h = value_h + gap_value_bar + bar_h + gap_bar_label + bar_label_h
    available_top = label_bottom
    available_bottom = breakdown_y_start
    value_y = available_top + (available_bottom - available_top - group_h) // 2

    draw.text((MARGIN, value_y), value_text, fill=0, font=value_font)
    value_actual = draw.textbbox((MARGIN, value_y), value_text, font=value_font)

    # Unit: "kWh erwartet" baseline-aligned to value
    unit_text = "kWh erwartet"
    unit_x = value_actual[2] + 20
    unit_actual = draw.textbbox((unit_x, value_y), unit_text, font=unit_font)
    unit_y = value_actual[3] - (unit_actual[3] - unit_actual[1])
    draw.text((unit_x, unit_y), unit_text, fill=0, font=unit_font)

    # --- PROGRESS BAR: manual drawing for custom legend ---
    bar_y = value_y + value_h + gap_value_bar
    bar_x0, bar_x1 = MARGIN, CANVAS_W - MARGIN

    # Draw outline
    draw.rectangle((bar_x0, bar_y, bar_x1, bar_y + bar_h), outline=0, width=4)

    # Calculate fill
    if data.today_kwh > 0:
        percentage = (data.actual_production / data.today_kwh * 100.0)
        clamped = min(100.0, percentage)
        fill_width = int((clamped / 100.0) * (bar_x1 - bar_x0))
        if fill_width > 0:
            draw.rectangle((bar_x0, bar_y, bar_x0 + fill_width, bar_y + bar_h), fill=0)

        # Overflow indicator (>100%)
        if percentage > 100.0:
            # Draw white rectangle at right end to create inverted "notch"
            notch_x0 = bar_x1 - 40
            notch_x1 = bar_x1 - 2
            notch_y0 = bar_y + 2
            notch_y1 = bar_y + bar_h - 2
            draw.rectangle((notch_x0, notch_y0, notch_x1, notch_y1), fill=1, outline=0, width=2)

    # Bar legend below bar
    legend_y = bar_y + bar_h + gap_bar_label
    if data.today_kwh > 0:
        legend_text = f"{int(percentage)}% der Prognose erreicht"
    else:
        legend_text = "Keine Prognose verfügbar"
    draw.text((MARGIN, legend_y), legend_text, fill=0, font=bar_font)

    # --- BOTTOM BREAKDOWN: Tomorrow's forecast with delta ---
    if data.today_kwh > 0 or data.tomorrow_kwh > 0:
        if data.tomorrow_kwh > 0:
            delta = data.tomorrow_kwh - data.today_kwh
            delta_text = f"(+{delta:.1f})" if delta >= 0 else f"({delta:.1f})"
            tomorrow_text = f"Morgen: {data.tomorrow_kwh:.1f} kWh {delta_text}"
        elif data.today_kwh > 0:
            tomorrow_text = "Morgen: keine Daten"
        else:
            tomorrow_text = ""

        if tomorrow_text:
            tomorrow_bbox = draw.textbbox((0, 0), tomorrow_text, font=breakdown_value_font)
            tomorrow_width = tomorrow_bbox[2] - tomorrow_bbox[0]
            tomorrow_height = tomorrow_bbox[3] - tomorrow_bbox[1]
            tomorrow_x = (CANVAS_W - tomorrow_width) // 2
            tomorrow_y = breakdown_y_start + (110 - tomorrow_height) // 2
            draw.text((tomorrow_x, tomorrow_y), tomorrow_text, fill=0, font=breakdown_value_font)

    # --- STALENESS INDICATOR: top-right if data > 2 hours old ---
    age_seconds = (datetime.now() - data.fetched_at).total_seconds()
    if age_seconds > 7200:  # 2 hours
        stale_text = f"Stand: {data.fetched_at.strftime('%H:%M')}"
        stale_bbox = draw.textbbox((0, 0), stale_text, font=stale_font)
        stale_width = stale_bbox[2] - stale_bbox[0]
        stale_x = CANVAS_W - MARGIN - stale_width
        draw.text((stale_x, MARGIN), stale_text, fill=0, font=stale_font)

    return img
