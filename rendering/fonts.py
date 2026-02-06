"""
Font loading with caching and fallback chain.

Fonts are loaded once and cached for the lifetime of the process. Multiple calls
with the same font_name and size will return the identical cached font object.

Search order:
1. Project-local fonts/ directory (Arial.ttf, ArialBlack.ttf)
2. Raspberry Pi system fonts (/usr/share/fonts/truetype/dejavu)
3. Alternative system fonts (/usr/share/fonts/truetype/liberation)
4. PIL default font (no size support)
"""

from pathlib import Path
from PIL import ImageFont
import logging

logger = logging.getLogger(__name__)

# Module-level cache: (font_name, size) -> ImageFont.FreeTypeFont
_FONT_CACHE = {}


def load_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    """
    Load a TrueType font with caching and fallback.

    Args:
        font_name: Font filename (e.g., "Arial.ttf")
        size: Font size in points

    Returns:
        PIL ImageFont.FreeTypeFont object (or default font if not found)
    """
    cache_key = (font_name, size)

    # Return cached font if available
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]

    # Search for font file in fallback chain
    search_paths = [
        Path("fonts") / font_name,  # Project-local
        Path("/usr/share/fonts/truetype/dejavu") / font_name,  # Raspberry Pi
        Path("/usr/share/fonts/truetype/liberation") / font_name,  # Alternative
    ]

    for font_path in search_paths:
        if font_path.exists():
            font = ImageFont.truetype(str(font_path), size)
            _FONT_CACHE[cache_key] = font
            logger.debug(f"Loaded font {font_name} size {size} from {font_path}")
            return font

    # No font file found, fall back to PIL default
    logger.warning(
        f"Font {font_name} not found in any search path, using PIL default font. "
        f"Searched: {', '.join(str(p) for p in search_paths)}"
    )
    default_font = ImageFont.load_default()
    _FONT_CACHE[cache_key] = default_font
    return default_font
