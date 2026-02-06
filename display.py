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

# Try to import e-ink driver
try:
    from waveshare_epd import epd2in13_V3
    EINK_AVAILABLE = True
except ImportError:
    EINK_AVAILABLE = False


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

    def render(self, image, name: str = "screen"):
        """Render image to display or save as PNG.

        STUB: Full rendering logic will be implemented in Phase 4.

        Args:
            image: PIL Image to render (1000x488 high-res)
            name: Base filename for PNG output
        """
        if self.backend == "eink":
            # Scale down and display
            scaled = image.resize((self.width, self.height))
            self.epd.display(self.epd.getbuffer(scaled))
            logging.info(f"Rendered to e-ink display")
        else:
            # Save to debug folder
            filename = f"debug/{name}_{datetime.now():%Y%m%d_%H%M%S}.png"
            image.save(filename)
            logging.info(f"Rendered {self.width}x{self.height} to {filename}")

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
