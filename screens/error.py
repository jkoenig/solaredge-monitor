"""
Error screen renderer for SolarEdge Off-Grid Monitor.

Displays a simple error message when API is unavailable or other failures occur.
Used by the main polling loop after consecutive API failures.
"""

from PIL import Image, ImageDraw
from rendering.fonts import load_font

# Canvas and layout constants (matching other screens)
CANVAS_W = 1000
CANVAS_H = 488
MARGIN = 15


def render_error_screen(message: str = "API nicht erreichbar") -> Image.Image:
    """Render an error screen with headline and centered message.

    Args:
        message: Error message to display (default: "API nicht erreichbar")

    Returns:
        PIL Image in mode '1' (1-bit monochrome), size 1000x488
    """
    # Create white background (1 = white in mode '1')
    img = Image.new('1', (CANVAS_W, CANVAS_H), 1)
    draw = ImageDraw.Draw(img)

    # Draw headline "Fehler" at top-left
    headline_font = load_font("Arial.ttf", 48)
    headline_text = "Fehler"
    draw.text((MARGIN, MARGIN), headline_text, font=headline_font, fill=0)

    # Calculate headline bottom boundary for message centering
    headline_bbox = draw.textbbox((MARGIN, MARGIN), headline_text, font=headline_font)
    headline_bottom = headline_bbox[3]

    # Center the error message in the remaining area
    message_font = load_font("Arial.ttf", 36)
    message_bbox = draw.textbbox((0, 0), message, font=message_font)
    message_width = message_bbox[2] - message_bbox[0]
    message_height = message_bbox[3] - message_bbox[1]

    # Calculate available vertical space below headline
    available_top = headline_bottom
    available_bottom = CANVAS_H - MARGIN
    available_height = available_bottom - available_top

    # Center message horizontally and vertically
    message_x = (CANVAS_W - message_width) // 2
    message_y = available_top + (available_height - message_height) // 2

    draw.text((message_x, message_y), message, font=message_font, fill=0)

    return img
