"""Display hardware abstraction layer.

Provides a unified Display class that automatically detects and uses the
appropriate backend:
- E-ink hardware (waveshare_epd) when available
- PNG file output (to ./debug/) as fallback for development

This is a STUB for Phase 4. Full rendering logic will be implemented later.
"""

import logging
import os
from datetime import datetime
from PIL import Image

# Try to import e-ink driver (error stored for deferred logging)
_EINK_IMPORT_ERROR = None
try:
    from waveshare_epd import epd2in13_V3
    EINK_AVAILABLE = True
except Exception as e:
    EINK_AVAILABLE = False
    _EINK_IMPORT_ERROR = f"{type(e).__name__}: {e}"


class Display:
    """Hardware-abstracted display renderer.

    Auto-detects available backend:
    - E-ink hardware if waveshare_epd available
    - PNG files if not (development mode)
    """

    def __init__(self, debug_mode: bool = False):
        """Initialize display backend.

        Args:
            debug_mode: Force PNG backend even if e-ink available
        """
        self.width = 250
        self.height = 122
        self.scale_factor = 4  # 4x supersampling (render at 1000x488)

        if not debug_mode and EINK_AVAILABLE:
            self.epd = epd2in13_V3.EPD()
            self.epd.init()
            self.epd.Clear(0xFF)
            self.backend = "eink"
            logging.info("Display: E-ink hardware initialized")
        else:
            self.epd = None
            self.backend = "png"
            os.makedirs("debug", exist_ok=True)
            reason = "debug mode" if debug_mode else "driver not found"
            logging.info(f"Display: PNG backend ({reason})")
            if _EINK_IMPORT_ERROR and not debug_mode:
                logging.warning(f"E-ink driver import failed: {_EINK_IMPORT_ERROR}")

    def render(self, image, name: str = "screen"):
        """Render image to display or save as PNG.

        Uses LANCZOS resampling for high-quality downsampling to e-ink resolution.

        Args:
            image: PIL Image to render (1000x488 high-res)
            name: Base filename for PNG output
        """
        if self.backend == "eink":
            # High-quality downsampling: 1-bit -> grayscale -> resize -> 1-bit
            gray = image.convert('L')
            scaled = gray.resize((self.width, self.height), Image.LANCZOS)
            final = scaled.convert('1')
            self.epd.display(self.epd.getbuffer(final))
            logging.info(f"Rendered '{name}' to e-ink display")
        else:
            # Save high-res PNG to debug folder (for visual inspection)
            filename = f"debug/{name}_{datetime.now():%Y%m%d_%H%M%S}.png"
            image.save(filename)
            logging.info(f"Rendered '{name}' ({image.width}x{image.height}) to {filename}")

    def clear(self):
        """Clear the display."""
        if self.backend == "eink" and self.epd:
            self.epd.Clear(0xFF)
            logging.info("Display cleared")

    def sleep(self):
        """Put e-ink display to sleep mode."""
        if self.backend == "eink" and self.epd:
            self.epd.sleep()
            logging.info("Display sleeping")

    def __del__(self):
        """Clean up e-ink driver on shutdown."""
        if hasattr(self, 'backend') and self.backend == "eink" and self.epd:
            try:
                self.epd.sleep()
            except Exception:
                pass
