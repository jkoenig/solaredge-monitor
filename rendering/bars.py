"""
Horizontal bar chart drawing with percentage display.

Bars render with a filled portion proportional to the percentage value,
with percentage text displayed to the right of the bar.
"""

from PIL import ImageDraw


def draw_horizontal_bar(draw: ImageDraw.Draw, bbox: tuple, percentage: float, font, label: str = "", legend: str = "") -> None:
    """
    Draw a horizontal bar chart with percentage fill and text label.

    Args:
        draw: PIL ImageDraw instance
        bbox: Tuple of (x0, y0, x1, y1) defining bar bounds
        percentage: Fill percentage (0-100)
        font: PIL font object for percentage text
        label: Optional label to prefix before percentage (e.g., "Eigenverbrauch" → "Eigenverbrauch 75%")
        legend: Optional pre-formatted legend text (overrides label if provided)
    """
    x0, y0, x1, y1 = bbox

    # Draw outline rectangle
    draw.rectangle(bbox, outline=0, width=4)

    # Clamp percentage to valid range
    percentage = max(0.0, min(100.0, percentage))

    # Calculate filled width
    bar_width = x1 - x0
    fill_width = int((percentage / 100.0) * bar_width)

    # Draw filled portion if width > 0
    if fill_width > 0:
        fill_bbox = [x0, y0, x0 + fill_width, y1]
        draw.rectangle(fill_bbox, fill=0)

    # Draw legend text BELOW the bar (left-aligned at bar x0)
    if legend:
        percentage_text = legend
    elif label:
        percentage_text = f"{label} {int(percentage)}%"
    else:
        percentage_text = f"{int(percentage)}%"

    text_y = y1 + 5  # 5px gap below bar
    draw.text((x0, text_y), percentage_text, fill=0, font=font)
