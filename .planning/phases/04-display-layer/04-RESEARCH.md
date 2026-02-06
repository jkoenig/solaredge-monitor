# Phase 4: Display Layer - Research

**Researched:** 2026-02-06
**Domain:** PIL/Pillow image rendering, e-ink display optimization, screen cycling patterns
**Confidence:** HIGH

## Summary

This phase implements visual rendering for a 250x122 monochrome e-ink display with 4x supersampling (render at 1000x488). The research focused on PIL/Pillow best practices for drawing text and shapes, font selection for e-ink readability, screen cycling patterns, and common pitfalls when working with e-ink displays.

The standard approach is to use Pillow (PIL Fork) with ImageDraw for compositing text, shapes, and geometric icons. For e-ink readability at distance, Verdana and Arial are the most legible fonts, with DejaVu Sans as a widely-available alternative on Raspberry Pi. Render at high resolution with 4x supersampling and downsample with filtering for crisp output. Use simple cycling patterns with itertools.cycle() or index-based rotation for screen management.

Key findings align with Phase 3 decisions: Display class already implements debug_mode PNG output and 4x supersampling. PIL/Pillow is the standard stack for e-ink rendering. Simple geometric shapes drawn with ImageDraw primitives (rectangle, ellipse, line, polygon) are preferred over font-based icons for clarity.

**Primary recommendation:** Use Pillow 10.x+ (Python 3.9 compatible), DejaVu Sans or Liberation Sans fonts from Raspberry Pi system fonts, render at 1000x488 with Image.LANCZOS resampling for downscaling, implement simple list-based screen cycling with modulo indexing, and minimize partial refreshes to prevent e-ink ghosting.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pillow | 10.x-12.x | Image creation and manipulation | The friendly PIL fork, mature (6.0 status), de facto standard for Python image processing |
| PIL.ImageDraw | (via Pillow) | Drawing primitives (text, shapes) | Built into Pillow, provides rectangle(), ellipse(), text(), line() for compositing |
| PIL.ImageFont | (via Pillow) | TrueType font loading | Built into Pillow, loads .ttf files with size specification |
| itertools | stdlib | Cycling utilities | stdlib cycle() function for infinite iteration patterns |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PIL.Image | (via Pillow) | Image creation and resizing | Always - entry point for creating images and downsampling |
| datetime | stdlib | Timestamp formatting | Already in use from Phase 3 models |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pillow | cairo/pycairo | cairo is more powerful but much heavier dependency, overkill for simple shapes and text |
| System fonts | Custom fonts | System fonts (DejaVu/Liberation) are pre-installed, eliminate distribution complexity |
| itertools.cycle | State machine library | Full state machines (python-statemachine) are overkill for simple 4-screen rotation |

**Installation:**
```bash
# Pillow 10.x for Python 3.9 compatibility (Pillow 12.x requires Python 3.10+)
pip install Pillow>=10.0.0,<11.0.0
```

**Python 3.9 Compatibility Note:**
- Pillow 12.1.0 (latest as of Jan 2026) requires Python >=3.10
- Pillow 10.x is the last major version supporting Python 3.9
- All core features (ImageDraw, ImageFont, resampling) are identical

## Architecture Patterns

### Recommended Project Structure
```
solaredge-offgrid-monitor/
├── display.py              # Display class (Phase 3 - hardware abstraction)
├── screens/                # NEW: Screen rendering functions
│   ├── __init__.py
│   ├── production.py       # render_production_screen(data) -> Image
│   ├── consumption.py      # render_consumption_screen(data) -> Image
│   ├── feed_in.py          # render_feed_in_screen(data) -> Image
│   └── purchased.py        # render_purchased_screen(data) -> Image
├── rendering/              # NEW: Shared rendering utilities
│   ├── __init__.py
│   ├── fonts.py            # Load and cache font objects
│   ├── icons.py            # Draw geometric icons (battery, house, grid, sun)
│   └── bars.py             # Draw horizontal bar charts with percentages
└── main.py                 # Phase 5: Add screen cycling loop
```

**Dependency flow** (extends Phase 3):
```
models.py -> screens/*.py -> display.py -> main.py
              ↓
         rendering/*.py (fonts, icons, bars)
```

Key principles:
- **Pure functions for screens**: Each screen renderer is a pure function `(data: EnergyDetails) -> PIL.Image`
- **Shared utilities**: Common rendering (fonts, icons, bars) extracted to rendering/ module
- **Separation from display hardware**: Screen renderers return PIL Images, Display class handles output
- **Type-driven**: Screens receive frozen dataclass models, not raw dicts

### Pattern 1: Screen Renderer Functions
**What:** Pure functions that accept typed data models and return PIL Images
**When to use:** Each distinct screen layout (Produktion, Verbrauch, Einspeisung, Bezug)
**Example:**
```python
# Source: Phase 4 requirements + Pillow best practices
from PIL import Image, ImageDraw
from models import EnergyDetails
from rendering.fonts import load_font
from rendering.bars import draw_horizontal_bar

def render_production_screen(data: EnergyDetails) -> Image:
    """Render Produktion screen with total production and breakdown.

    Layout:
    - Top: "Produktion" label + total kWh (large) + horizontal bar
    - Bottom: 3-column breakdown (Eigenverbrauch, Batterie, Netz)

    Args:
        data: EnergyDetails with production, self_consumption, feed_in

    Returns:
        1000x488 PIL Image (high-res for 4x supersampling)
    """
    # Create high-res canvas (4x supersampling)
    img = Image.new('1', (1000, 488), 1)  # '1' mode = 1-bit pixels (black/white)
    draw = ImageDraw.Draw(img)

    # Load fonts (cached)
    font_label = load_font("DejaVuSans.ttf", 56)    # ~14px at 250px width
    font_value = load_font("DejaVuSans-Bold.ttf", 96)  # ~24px at 250px width
    font_unit = load_font("DejaVuSans.ttf", 48)    # Smaller for "kWh"

    # Draw label "Produktion"
    draw.text((50, 40), "Produktion", font=font_label, fill=0)

    # Draw value (large) with unit
    value_text = f"{data.production:.1f}"
    draw.text((50, 120), value_text, font=font_value, fill=0)
    bbox = draw.textbbox((50, 120), value_text, font=font_value)
    draw.text((bbox[2] + 20, 150), "kWh", font=font_unit, fill=0)

    # Draw horizontal bar (percentage based on typical daily max)
    percentage = min(100, (data.production / 20.0) * 100)  # Assume 20kWh daily max
    draw_horizontal_bar(draw, (50, 240, 950, 280), percentage, fill=0)

    # Draw breakdown row (3 icons + values)
    # ... (icon rendering details)

    return img
```

### Pattern 2: Shared Font Loading with Caching
**What:** Load and cache TrueType font objects to avoid repeated file I/O
**When to use:** Every screen renderer that needs to draw text
**Example:**
```python
# Source: https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
from PIL import ImageFont
from pathlib import Path

_FONT_CACHE = {}

def load_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load TrueType font with caching.

    Searches font locations in order:
    1. ./fonts/ (project-local fonts)
    2. /usr/share/fonts/truetype/ (system fonts on Raspberry Pi)
    3. PIL default font as fallback

    Args:
        font_name: Font filename (e.g., "DejaVuSans.ttf")
        size: Font size in pixels (at high-res, divide by 4 for actual display size)

    Returns:
        Loaded font object (cached for reuse)
    """
    cache_key = (font_name, size)
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]

    # Search paths
    search_paths = [
        Path("fonts") / font_name,
        Path("/usr/share/fonts/truetype/dejavu") / font_name,
        Path("/usr/share/fonts/truetype/liberation") / font_name,
    ]

    for path in search_paths:
        if path.exists():
            font = ImageFont.truetype(str(path), size)
            _FONT_CACHE[cache_key] = font
            return font

    # Fallback to default font
    return ImageFont.load_default()
```

### Pattern 3: Geometric Icon Drawing
**What:** Draw simple geometric shapes to represent system elements (battery, house, grid, PV)
**When to use:** Breakdown sections where icons visually distinguish energy sources/destinations
**Example:**
```python
# Source: https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html
from PIL import ImageDraw

def draw_battery_icon(draw: ImageDraw.Draw, x: int, y: int, size: int):
    """Draw battery icon as simple rectangle with terminal.

    Args:
        draw: ImageDraw instance
        x, y: Top-left corner of icon
        size: Icon dimension (square bounding box)
    """
    # Main battery body (rectangle)
    draw.rectangle(
        [(x, y + size//6), (x + size, y + size)],
        outline=0, width=8
    )
    # Positive terminal (small rectangle on top)
    terminal_width = size // 3
    terminal_x = x + (size - terminal_width) // 2
    draw.rectangle(
        [(terminal_x, y), (terminal_x + terminal_width, y + size//6)],
        fill=0
    )

def draw_house_icon(draw: ImageDraw.Draw, x: int, y: int, size: int):
    """Draw house icon as triangle roof + rectangle body."""
    # Roof (triangle using polygon)
    roof_points = [
        (x + size//2, y),              # Top point
        (x, y + size//3),              # Bottom-left
        (x + size, y + size//3)        # Bottom-right
    ]
    draw.polygon(roof_points, outline=0, width=8)

    # Body (rectangle)
    draw.rectangle(
        [(x + size//6, y + size//3), (x + 5*size//6, y + size)],
        outline=0, width=8
    )

def draw_grid_icon(draw: ImageDraw.Draw, x: int, y: int, size: int):
    """Draw grid icon as simple line pattern."""
    # Vertical lines
    for i in range(4):
        line_x = x + (i * size // 3)
        draw.line([(line_x, y), (line_x, y + size)], fill=0, width=6)
    # Horizontal lines
    for i in range(4):
        line_y = y + (i * size // 3)
        draw.line([(x, line_y), (x + size, line_y)], fill=0, width=6)

def draw_sun_icon(draw: ImageDraw.Draw, x: int, y: int, size: int):
    """Draw sun icon as circle with rays."""
    center_x = x + size // 2
    center_y = y + size // 2
    radius = size // 3

    # Center circle
    draw.ellipse(
        [(center_x - radius, center_y - radius),
         (center_x + radius, center_y + radius)],
        fill=0
    )

    # 8 rays (lines from center outward)
    ray_length = size // 2 - radius - 10
    for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
        import math
        rad = math.radians(angle)
        start_x = center_x + int(radius * math.cos(rad))
        start_y = center_y + int(radius * math.sin(rad))
        end_x = center_x + int((radius + ray_length) * math.cos(rad))
        end_y = center_y + int((radius + ray_length) * math.sin(rad))
        draw.line([(start_x, start_y), (end_x, end_y)], fill=0, width=8)
```

### Pattern 4: Horizontal Bar Charts
**What:** Draw filled rectangle bars with percentage text
**When to use:** Visualizing energy production/consumption relative to typical daily maximum
**Example:**
```python
# Source: https://note.nkmk.me/en/python-pillow-imagedraw/
from PIL import ImageDraw

def draw_horizontal_bar(draw: ImageDraw.Draw, bbox: tuple, percentage: float, fill: int):
    """Draw horizontal bar chart with percentage.

    Args:
        draw: ImageDraw instance
        bbox: Bounding box as (x0, y0, x1, y1)
        percentage: Fill percentage (0-100)
        fill: Fill color (0=black, 1=white for monochrome)
    """
    x0, y0, x1, y1 = bbox
    bar_width = x1 - x0
    bar_height = y1 - y0

    # Draw outline
    draw.rectangle(bbox, outline=0, width=6)

    # Draw filled portion
    fill_width = int((percentage / 100.0) * bar_width)
    if fill_width > 0:
        draw.rectangle(
            [(x0, y0), (x0 + fill_width, y1)],
            fill=0
        )

    # Draw percentage text (centered, white text on black bar for contrast)
    from rendering.fonts import load_font
    font = load_font("DejaVuSans.ttf", 48)
    text = f"{percentage:.0f}%"
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = x0 + (bar_width - text_width) // 2
    text_y = y0 + (bar_height - text_height) // 2

    # White text if over black bar, black text otherwise
    text_fill = 1 if percentage > 50 else 0
    draw.text((text_x, text_y), text, font=font, fill=text_fill)
```

### Pattern 5: Simple Screen Cycling
**What:** Rotate through screen list using modulo indexing
**When to use:** Displaying multiple screens in sequence (Phase 5 polling loop)
**Example:**
```python
# Source: https://docs.python.org/3/library/itertools.html
from screens import (
    render_production_screen,
    render_consumption_screen,
    render_feed_in_screen,
    render_purchased_screen
)

# Screen registry (list of render functions)
SCREENS = [
    render_production_screen,
    render_consumption_screen,
    render_feed_in_screen,
    render_purchased_screen,
]

# Simple modulo cycling
current_screen_index = 0

def get_next_screen(data):
    """Get next screen in rotation."""
    global current_screen_index

    renderer = SCREENS[current_screen_index]
    image = renderer(data)

    # Advance to next screen (wrap around)
    current_screen_index = (current_screen_index + 1) % len(SCREENS)

    return image

# Alternative: itertools.cycle for infinite iteration
from itertools import cycle
screen_cycle = cycle(SCREENS)

def get_next_screen_itertools(data):
    """Get next screen using itertools.cycle."""
    renderer = next(screen_cycle)
    return renderer(data)
```

### Anti-Patterns to Avoid

- **Rendering at native resolution then upscaling**: Always render at high-res (1000x488) and downsample. Upscaling looks pixelated on e-ink.
- **Using FontAwesome or icon fonts**: Font icons render poorly at small sizes on monochrome displays. Simple geometric shapes are clearer.
- **Loading fonts repeatedly**: Cache font objects. FreeType keeps files open, and repeated loading hits file handle limits (512 on Windows).
- **Partial refresh without full refresh**: E-ink displays accumulate ghosting. Full refresh periodically is essential.
- **Forgetting text bounding boxes**: Use textbbox() to measure text before drawing for proper alignment and layout.
- **Antialiasing for monochrome**: Image mode '1' (1-bit) doesn't support antialiasing. Use '1' mode directly, not 'L' (grayscale) converted to '1'.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Text wrapping/line breaking | Manual string splitting by width | PIL.ImageDraw.multiline_text() with textbbox() for measurement | Handles unicode, kerning, and complex scripts correctly |
| Image resampling algorithms | Custom pixel averaging | PIL.Image.resize() with LANCZOS filter | Optimized C implementation, proper antialiasing, prevents moiré patterns |
| Font file discovery | Hardcoded paths | Fallback chain (local → system → default) | Cross-platform, handles missing fonts gracefully |
| State machine for cycling | Custom class with states/transitions | Simple list + modulo or itertools.cycle() | 4 screens don't need state machine complexity |
| Icon assets | PNG/SVG files to load | PIL.ImageDraw geometric primitives | No asset management, resolution-independent, smaller codebase |

**Key insight:** E-ink displays have unique constraints (monochrome, slow refresh, ghosting) that make simple solutions better than complex libraries. Direct PIL primitives outperform asset-based approaches for this use case.

## Common Pitfalls

### Pitfall 1: Text Cutoff at Image Edges
**What goes wrong:** Text renders with top/bottom cut off, or positioned incorrectly
**Why it happens:** PIL text rendering uses bounding boxes that include ascenders/descenders, and anchor point defaults to top-left corner
**How to avoid:** Always use textbbox() to measure text dimensions before positioning. Consider using anchor parameter for alignment (e.g., anchor="mm" for middle-middle).
**Warning signs:** Text appears truncated, uneven spacing between elements, text overlapping other elements

### Pitfall 2: E-Ink Ghosting from Partial Refreshes
**What goes wrong:** Faint residual images from previous screens persist, causing visual clutter
**Why it happens:** E-ink microcapsules don't fully reset with partial refresh. Particles move slower in cold temperatures.
**How to avoid:** Perform full refresh every N partial refreshes (recommended: every 180 seconds or ~5 screen cycles). Use display.Clear() method periodically.
**Warning signs:** Shadows of previous numbers/text visible, overlapping bar charts, contrast degradation

### Pitfall 3: Font File Not Found
**What goes wrong:** Program crashes with "cannot open resource" error
**Why it happens:** Font paths differ across systems, fonts not installed, or wrong font name
**How to avoid:** Implement fallback chain (project fonts → system fonts → PIL default). Use Path.exists() to check before loading.
**Warning signs:** Works on dev machine but fails on Raspberry Pi, ImportError or IOError on font loading

### Pitfall 4: Downsampling Artifacts (Moiré Patterns)
**What goes wrong:** Text or thin lines appear jagged, or show wavy patterns after downscaling
**Why it happens:** Nearest-neighbor or low-quality resampling creates aliasing when reducing 4x
**How to avoid:** Always use Image.LANCZOS (or Image.BICUBIC) for downsampling. Render at exact multiple (4x) of target resolution.
**Warning signs:** Jagged text edges, wavy line patterns in icons, pixelated appearance

### Pitfall 5: Percentage Bars Don't Fit Data Range
**What goes wrong:** Bar charts show tiny slivers or are always full
**Why it happens:** Percentage calculation uses wrong maximum (e.g., peak power vs. daily energy)
**How to avoid:** Base percentage on typical daily maximum for energy (kWh), not instantaneous max. Use historical data to set realistic scale (e.g., 20 kWh daily production max).
**Warning signs:** All bars near 0%, all bars at 100%, bar doesn't match intuitive sense of "good day" vs. "poor day"

### Pitfall 6: Image Mode Confusion ('1' vs 'L' vs 'RGB')
**What goes wrong:** Images render with wrong colors, or display driver rejects format
**Why it happens:** E-ink displays expect '1' (1-bit) or 'L' (8-bit grayscale), but code creates 'RGB'
**How to avoid:** Create images in mode '1' directly for pure black/white. If using grayscale, convert to '1' with dithering: `img.convert('1', dither=Image.FLOYDSTEINBERG)`
**Warning signs:** Display shows garbage, images save correctly as PNG but fail on e-ink, unexpected colors

## Code Examples

Verified patterns from official sources:

### Creating 1-Bit Monochrome Image
```python
# Source: https://pillow.readthedocs.io/en/stable/handbook/concepts.html
from PIL import Image

# Mode '1' = 1-bit pixels (black and white, stored as 8 pixels per byte)
# 1 = white, 0 = black
img = Image.new('1', (1000, 488), 1)  # 1000x488 white canvas

# For e-ink displays, this is ideal: true monochrome, no grayscale conversion needed
```

### Text Rendering with Bounding Box Measurement
```python
# Source: https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
from PIL import Image, ImageDraw, ImageFont

img = Image.new('1', (1000, 488), 1)
draw = ImageDraw.Draw(img)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 96)

text = "12.5"
# Get bounding box BEFORE drawing to calculate layout
bbox = draw.textbbox((0, 0), text, font=font)
text_width = bbox[2] - bbox[0]
text_height = bbox[3] - bbox[1]

# Now position text precisely
x = (1000 - text_width) // 2  # Center horizontally
y = 100
draw.text((x, y), text, font=font, fill=0)
```

### High-Res Rendering with LANCZOS Downsampling
```python
# Source: https://pillow.readthedocs.io/en/stable/handbook/concepts.html#filters
from PIL import Image

# Render at 4x resolution (1000x488)
high_res = Image.new('1', (1000, 488), 1)
# ... draw content ...

# Downsample to display resolution (250x122) with LANCZOS filter
# LANCZOS provides best quality for downsampling (high-quality filter)
display_img = high_res.resize((250, 122), Image.LANCZOS)

# Note: For 1-bit images, may need to convert to 'L' first, resize, then back to '1'
temp_gray = high_res.convert('L')
resized_gray = temp_gray.resize((250, 122), Image.LANCZOS)
display_img = resized_gray.convert('1')
```

### Drawing Shapes with Line Width
```python
# Source: https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html
from PIL import Image, ImageDraw

img = Image.new('1', (1000, 488), 1)
draw = ImageDraw.Draw(img)

# Rectangle with outline only
draw.rectangle([(100, 100), (900, 300)], outline=0, width=8)

# Rectangle filled
draw.rectangle([(100, 350), (900, 400)], fill=0)

# Circle (added in Pillow 10.4.0)
draw.circle((500, 244), 50, outline=0, width=8)

# Ellipse (older method for circles)
draw.ellipse([(200, 200), (300, 300)], outline=0, width=8)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pygame for rendering | Pillow/PIL | Established by 2020 | Pillow is lighter, no SDL dependency, better for headless systems |
| Manual pixel arrays | ImageDraw primitives | Pillow 2.x+ | Cleaner API, hardware-accelerated, cross-platform |
| Nearest-neighbor downsampling | LANCZOS/BICUBIC resampling | Pillow 3.0+ (2015) | Dramatically improved text/icon clarity on low-res displays |
| Icon font files (FontAwesome) | Geometric primitives | E-ink trend 2022+ | Better monochrome rendering, no font file distribution, resolution-independent |
| Complex state machines | itertools.cycle() or simple modulo | Always available | Simpler codebases for straightforward cycling (state machines overkill for <10 states) |

**Deprecated/outdated:**
- **PIL (original project)**: Abandoned in 2011, use Pillow instead (friendly fork, actively maintained)
- **Image.ANTIALIAS constant**: Deprecated in Pillow 10.0.0, use Image.LANCZOS instead (same algorithm, clearer name)
- **Loading fonts without paths**: PIL default font is extremely limited (bitmap, single size). Always use TrueType fonts for quality.

## Open Questions

Things that couldn't be fully resolved:

1. **Optimal cycling interval for 4 screens**
   - What we know: Common e-ink refresh recommendations are 180+ seconds to minimize ghosting
   - What's unclear: Balance between information freshness and display wear/ghosting for this specific 4-screen rotation
   - Recommendation: Start with 30 seconds per screen (2 minutes total cycle), tune based on user preference and ghosting observation. Phase 5 should make interval configurable.

2. **Typical daily energy maximum for percentage scaling**
   - What we know: Bar charts need a maximum value to calculate percentage fill
   - What's unclear: User's typical daily production/consumption range (varies by season, weather, system size)
   - Recommendation: Use conservative defaults (20 kWh production, 15 kWh consumption) initially. Phase 6+ could implement adaptive scaling based on historical data.

3. **Cold temperature e-ink performance**
   - What we know: E-ink particles move slower in cold, causing weaker refreshes and more ghosting
   - What's unclear: User's installation environment temperature range
   - Recommendation: Assume room temperature (15-25°C) for now. Document in user guide that extreme temperatures (below 0°C, above 40°C) may degrade display quality.

## Sources

### Primary (HIGH confidence)
- Pillow 12.1.0 official documentation - ImageDraw module: https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html
- Pillow 12.1.0 official documentation - ImageFont module: https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
- Pillow 12.1.0 PyPI page (version/requirements): https://pypi.org/project/pillow/
- Python stdlib itertools documentation: https://docs.python.org/3/library/itertools.html

### Secondary (MEDIUM confidence)
- E-ink font readability research (Verdana/Arial most legible): MobileRead Forums - https://www.mobileread.com/forums/showthread.php?t=366520
- Raspberry Pi font locations (DejaVu/Liberation in /usr/share/fonts): Raspberry Connect - https://raspberryconnect.com/raspbian-packages/35-raspbian-fonts
- Waveshare e-ink ghosting documentation (180s refresh interval): Waveshare Wiki EINK-DISP-97 - https://www.waveshare.com/wiki/EINK-DISP-97
- Supersampling and downsampling fundamentals: Cloudinary Glossary - https://cloudinary.com/glossary/supersampling
- PIL ImageDraw shape examples: note.nkmk.me guide - https://note.nkmk.me/en/python-pillow-imagedraw/

### Tertiary (LOW confidence - flagged for validation)
- Progress bar best practices (general UX): Domo Learn - https://www.domo.com/learn/charts/progress-bars
- E-ink display project examples (various platforms): Multiple sources from WebSearch

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Pillow is universally standard for Python image processing, official docs verified all capabilities
- Architecture: HIGH - Screen renderer pattern is straightforward, confirmed via existing Phase 3 structure and PIL documentation
- Pitfalls: MEDIUM-HIGH - E-ink pitfalls verified with Waveshare docs and community sources; PIL pitfalls from official GitHub issues

**Research date:** 2026-02-06
**Valid until:** 2026-03-06 (30 days) - Pillow is mature/stable, major changes unlikely

**Context constraints applied:**
- Locked decisions: 4 screens (Produktion, Verbrauch, Einspeisung, Bezug), German labels, PIL-drawn geometric icons (not FontAwesome), 250x122 display, 4x supersampling
- Claude's discretion: Font choice (researched DejaVu Sans/Liberation Sans), font sizes (researched readable scales), bar styling (researched horizontal bar patterns), cycling interval (researched 30s-180s range)
- Deferred ideas: Additional screens, screen priority/weighting (ignored in research)
