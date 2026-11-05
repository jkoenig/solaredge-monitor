"""
Error screen renderer for SolarEdge Off-Grid Monitor.

Displays a simple error message when API is unavailable or other failures occur.
Used by the main polling loop after consecutive API failures.

Also provides the "Login noetig" screen (D-06): shown when no usable OAuth token
exists. It is rendered directly by main.py and is not part of get_screens().
"""

from PIL import Image, ImageDraw
from rendering.fonts import load_font

# Canvas and layout constants (matching other screens)
CANVAS_W = 1000
CANVAS_H = 488
MARGIN = 5

LOGIN_HEADLINE = "Login nötig"
LOGIN_HINT = "Mac: login-Skript starten"


def render_error_screen(message: str = "API nicht erreichbar") -> Image.Image:
    """Render an error screen with headline and centered message.

    Args:
        message: Error message to display (default: "API nicht erreichbar")

    Returns:
        PIL Image in mode '1' (1-bit monochrome), size 1000x488
    """
    return _render_headline_message("Fehler", message)


def render_login_required_screen() -> Image.Image:
    """Render the "Login nötig" screen (D-06).

    Shown immediately (D-07) and exclusively (D-08) when the OAuth token is
    unusable; main.py renders it once on entering that state and stays static
    until a new token file appears (D-09). Not part of get_screens().

    Returns:
        PIL Image in mode '1', size 1000x488
    """
    return _render_headline_message(LOGIN_HEADLINE, LOGIN_HINT)


def _render_headline_message(headline: str, message: str) -> Image.Image:
    """Render headline top-left and a message centered below it."""
    # Create white background (1 = white in mode '1')
    img = Image.new('1', (CANVAS_W, CANVAS_H), 1)
    draw = ImageDraw.Draw(img)

    headline_font = load_font("Arial.ttf", 60)
    draw.text((MARGIN, MARGIN), headline, font=headline_font, fill=0)

    # Calculate headline bottom boundary for message centering
    headline_bbox = draw.textbbox((MARGIN, MARGIN), headline, font=headline_font)
    headline_bottom = headline_bbox[3]

    # Center the message in the remaining area
    message_font = load_font("Arial.ttf", 48)
    message_bbox = draw.textbbox((0, 0), message, font=message_font)
    message_width = message_bbox[2] - message_bbox[0]
    message_height = message_bbox[3] - message_bbox[1]

    # Calculate available vertical space below headline
    available_top = headline_bottom
    available_bottom = CANVAS_H - MARGIN
    available_height = available_bottom - available_top

    if message_width > CANVAS_W - 2 * MARGIN and "Mac: " in message:
        # Wrap safeguard: split after "Mac:", center both lines, never shrink font
        lines = ["Mac:", message.split("Mac: ", 1)[1]]
        spacing = round(48 * 1.2)
        block_height = spacing * (len(lines) - 1) + message_height
        y = available_top + (available_height - block_height) // 2
        for line in lines:
            lb = draw.textbbox((0, 0), line, font=message_font)
            x = (CANVAS_W - (lb[2] - lb[0])) // 2
            draw.text((x, y), line, font=message_font, fill=0)
            y += spacing
        return img

    # Center message horizontally and vertically
    message_x = (CANVAS_W - message_width) // 2
    message_y = available_top + (available_height - message_height) // 2

    draw.text((message_x, message_y), message, font=message_font, fill=0)

    return img
