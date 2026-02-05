# Feature Landscape: Solar Energy E-ink Monitor

**Domain:** Solar monitoring on e-ink displays
**Researched:** 2026-02-04
**Confidence:** MEDIUM (based on training knowledge of solar monitoring systems and e-ink display constraints)

## Executive Summary

Solar energy monitors need to balance **information density** with **readability** on constrained displays. For a 250x122 e-ink screen, the challenge is acute: show actionable data while respecting the medium's limitations (slow refresh, 1-bit color, tiny resolution).

**Key insight:** Users check solar monitors for quick status checks, not detailed analysis. The display must answer "Is everything working?" and "How much am I producing/consuming?" at a glance.

## Table Stakes

Features users expect from any solar monitor. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Current power production | Core metric - "How much am I generating right now?" | Low | SolarEdge API: `currentPower.power` |
| Battery state of charge (%) | Critical for off-grid/hybrid systems | Low | SolarEdge API: battery percentage |
| Grid connection status | Need to know if on/off grid | Low | SolarEdge API: grid status |
| Current consumption | "How much am I using?" | Low | SolarEdge API: load power |
| Timestamp/last update | Trust the data is current | Low | Display update time |
| Daily production total | Achievement metric | Low | SolarEdge API: daily energy |
| Self-sufficiency ratio | % of energy from solar vs grid | Medium | Calculated: (solar / total) × 100 |

**E-ink specific constraints:**
- 250x122 = only 31,000 pixels total
- At recommended 16px font, you get ~7-8 lines maximum
- Must prioritize: show 3-4 key metrics clearly vs 10 metrics poorly

## Differentiators

Features that elevate this from basic to excellent for small e-ink displays.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Large, readable fonts** | Glanceable from distance | Low | Min 24px for primary metrics, 16px for labels |
| **Icon-based status** | Universal understanding, language-agnostic | Low | Battery icon, grid/off-grid symbol, solar icon |
| **Trend indicators** | Up/down arrows show direction without history | Low | Compare current to 5-min-ago reading |
| **Smart screen cycling** | Show relevant screen based on context | Medium | E.g., emphasize battery at night, production during day |
| **Adaptive contrast** | Optimize for ambient light conditions | Medium | E-ink excels in sunlight but needs high contrast |
| **Status-at-a-glance** | Single summary screen with all critical info | Low | "Dashboard" screen: production, battery, grid, consumption |
| **Efficiency rating** | Daily performance vs typical day | High | Requires historical data and weather normalization |
| **Power flow diagram** | Visual representation of energy flow | Medium | Arrows showing PV→Battery, PV→Load, Grid→Load, Battery→Load |

**Recommendation for MVP refactor:**
1. Large readable fonts (24px+ for numbers)
2. Icon-based status indicators
3. Single summary screen (replace 4-screen cycling)
4. Trend indicators (simple up/down arrows)

## Anti-Features

Features to explicitly NOT build for small e-ink displays.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Graphs/charts** | 250x122 too small for readable graphs | Use trend arrows (↑↓) or numeric deltas |
| **Historical data** | Can't show meaningful history on tiny screen | Focus on "right now" and "today total" |
| **Multiple colors** | 1-bit display, no color | Use icons, size hierarchy, position for emphasis |
| **Animations** | E-ink refresh is slow (~2s full refresh) | Static displays, partial refresh for numbers only |
| **Small fonts (<14px)** | Unreadable on e-ink at typical viewing distance | Minimum 14px for labels, 24px+ for data |
| **Dense tables** | Matrix of numbers = cognitive overload | One metric per line with clear labeling |
| **Real-time updates** | E-ink degrades with frequent refresh | 5-minute update cycle is appropriate |
| **Grayscale shading** | Dithering looks poor at low resolution | Pure black and white only |
| **Scrolling content** | Requires interaction, e-ink is passive | Fit everything on screen or use screen cycling |
| **Weather forecast** | Scope creep, not core to monitoring | Link to separate weather display if needed |
| **Cost/savings calculations** | Requires electricity rates, currency display | Focus on kWh metrics instead |

## E-ink Display Best Practices (250x122)

### Layout Principles

**1. Vertical hierarchy over horizontal**
- E-ink: 250px wide, 122px tall
- Landscape orientation means limited vertical space
- Use top-to-bottom flow: Header → Primary metric → Secondary metrics

**2. Font sizing for readability**
- **Header/labels:** 14-16px (e.g., "Solar Production")
- **Primary metric:** 32-48px (e.g., "2.4 kW")
- **Secondary metrics:** 20-24px (e.g., "Today: 12.3 kWh")
- **Tertiary info:** 12-14px (timestamp, status text)

Example layout for 250x122:
```
+----------------------------+
| SOLAR PRODUCTION    [icon] | 14px header
|                            |
|        2.4 kW       ↑      | 42px primary + 24px arrow
|                            |
| Today: 12.3 kWh            | 16px secondary
| Battery: 87% [====]        | 16px with icon
| Grid: Off-grid      [icon] | 16px with icon
+----------------------------+
```

**3. Icon usage**
- Solar: ☀ or triangle rays
- Battery: Rectangle with fill level [====    ]
- Grid: Power plug or grid symbol
- Off-grid: Disconnected plug or island icon
- Trend: ↑ ↓ → arrows

**4. Spacing and whitespace**
- Minimum 8px between elements
- E-ink benefits from generous spacing (reduces ghosting)
- Don't be afraid of empty space

**5. Contrast and borders**
- Use solid black lines (1-2px) to separate sections
- Avoid thin fonts (use bold/regular, not light)
- Inverse areas (white text on black) for emphasis

### Screen Organization Strategies

**Option A: Single comprehensive screen**
```
+----------------------------+
| Solar ☀  2.4kW ↑  12.3kWh  | Current + Today
| Load ⚡   1.8kW    9.1kWh   | Current + Today
| Batt [======]  87%  +0.6kW | SoC + charge/discharge
| Grid: Off-grid ⚡ 0.0kW     | Status + flow
| Updated: 14:35             | Timestamp
+----------------------------+
```

**Option B: Rotating focused screens (current approach)**
- Screen 1: Solar production (large numbers)
- Screen 2: Battery status (large SoC display)
- Screen 3: Grid status (on/off-grid, import/export)
- Screen 4: Consumption & self-sufficiency

**Recommendation:** Shift to Option A (single screen). Reasoning:
- 5-minute update cycle means cycling wastes 3.75 minutes showing non-current screen
- User doesn't know which screen they'll see when checking
- Single comprehensive view answers all questions immediately

### Update Strategy

**Partial refresh for numbers:**
- E-ink supports partial refresh (faster, less flicker)
- Update only the numeric values, not entire screen
- Full refresh every 6th update (~30 min) to clear ghosting

**Sleep mode:**
- Midnight-6AM: Display "System sleeping" with last known state
- Or: Keep last full screen visible (e-ink retains image with no power)

## Feature Dependencies

```
Core metrics → Derived metrics → Display layout
    ↓              ↓                  ↓
currentPower   self-sufficiency   screen design
battery SoC    efficiency         icon selection
grid status    trend indicators   font sizing
consumption
```

**Critical dependency:** Display layout must be finalized before implementing derived metrics. No point calculating efficiency if there's no space to show it.

## Data Prioritization for 250x122

Given extreme space constraints, prioritize by actionability:

**Tier 1: Must show (actionable)**
1. Current solar production (kW)
2. Battery SoC (%)
3. Grid status (on/off-grid)
4. Current consumption (kW)

**Tier 2: Should show (context)**
5. Daily production total (kWh)
6. Battery charge/discharge rate (kW)
7. Last update timestamp

**Tier 3: Nice to have (insight)**
8. Self-sufficiency ratio (%)
9. Trend indicators (↑↓)
10. Daily consumption total (kWh)

**Tier 4: Defer (analysis)**
- Historical comparisons
- Efficiency metrics
- Cost savings
- Weather data
- Predictive information

## MVP Refactor Recommendation

For this refactoring milestone, prioritize **readability over features**.

**Add:**
1. ✅ Large readable fonts (32-48px for primary metrics)
2. ✅ Icon-based status indicators
3. ✅ Single comprehensive screen (replace cycling)
4. ✅ Clear visual hierarchy (size + position)
5. ✅ Generous spacing (8px+ between elements)

**Keep:**
1. ✅ Current power production
2. ✅ Battery SoC
3. ✅ Grid status
4. ✅ Consumption
5. ✅ 5-minute update cycle

**Remove:**
1. ❌ VW/BMW/disk integrations (as planned)
2. ❌ 4-screen cycling (consolidate to 1 screen)
3. ❌ Small fonts (<16px for labels, <24px for data)

**Defer to post-MVP:**
1. ⏸ Trend indicators (requires storing previous reading)
2. ⏸ Efficiency metrics (requires historical data)
3. ⏸ Smart screen adaptation (time-of-day logic)
4. ⏸ Power flow diagram (complex for tiny screen)

## Example Layouts

### Option 1: Metric-focused (recommended)

```
250x122 pixels, 1-bit black/white
┌────────────────────────────────────┐
│ SOLAREDGE OFF-GRID  [☀]  14:35   │ 14px
├────────────────────────────────────┤
│                                    │
│  Solar: 2.4kW      Load: 1.8kW   │ 24px
│  Today: 12.3kWh    Used: 9.1kWh  │ 16px
│                                    │
│  Battery: 87% [========  ] +0.6kW │ 20px + bar
│  Grid: Off-grid (Self: 95%)      │ 16px
│                                    │
└────────────────────────────────────┘
```

### Option 2: Icon-heavy

```
┌────────────────────────────────────┐
│  ☀  2.4kW ↑     Today: 12.3kWh    │
│                                    │
│  ⚡  1.8kW        Used:  9.1kWh    │
│                                    │
│  🔋 87% [========  ] Charging     │
│                                    │
│  ⚡ Off-grid   Self-suff: 95%     │
└────────────────────────────────────┘
```

### Option 3: Status-centric

```
┌────────────────────────────────────┐
│         SYSTEM STATUS              │
│                                    │
│    Solar: 2.4kW        [☀ ✓]     │
│   Battery: 87%         [🔋 ✓]     │
│     Grid: Off-grid     [⚡ ✓]     │
│     Load: 1.8kW        [⚡ ✓]     │
│                                    │
│    Self-sufficient: 95%            │
│    Updated: 14:35                  │
└────────────────────────────────────┘
```

## Implementation Notes

**Font selection:**
- Prefer system fonts with good e-ink rendering: DejaVu Sans, Liberation Sans, Arial
- Avoid serif fonts (poor readability on low-res e-ink)
- Use bold weights for better contrast

**Python libraries for e-ink:**
- Pillow (PIL) for image composition
- PIL.ImageDraw for text and shapes
- PIL.ImageFont for font rendering
- Waveshare libraries for display driver

**Code pattern:**
```python
from PIL import Image, ImageDraw, ImageFont

# Create canvas
image = Image.new('1', (250, 122), 255)  # 1-bit, white background
draw = ImageDraw.Draw(image)

# Load fonts
font_header = ImageFont.truetype('/path/to/font.ttf', 14)
font_data = ImageFont.truetype('/path/to/font.ttf', 24)
font_large = ImageFont.truetype('/path/to/font.ttf', 42)

# Draw elements
draw.text((10, 5), "Solar Production", font=font_header, fill=0)
draw.text((10, 30), f"{power:.1f} kW", font=font_large, fill=0)
draw.text((10, 80), f"Today: {daily:.1f} kWh", font=font_data, fill=0)

# Update display
epd.display(epd.getbuffer(image))
```

## Success Criteria

A successful solar e-ink monitor on 250x122:

1. **Readable from 1-2 meters** (typical wall mounting distance)
2. **Answers key questions in <5 seconds:**
   - Is my solar system working?
   - How much am I producing?
   - What's my battery level?
   - Am I on/off grid?
3. **Updates reliably** every 5 minutes
4. **Survives power outages** (e-ink retains last image)
5. **Low maintenance** (no screen burn-in, ghosting managed)

## Sources

**Note:** This research is based on training knowledge (cutoff January 2025) about:
- Solar monitoring systems and typical user needs
- E-ink display characteristics and limitations
- UI design principles for small screens
- SolarEdge API capabilities

**Confidence level:** MEDIUM
- Table stakes features: HIGH confidence (well-established domain)
- E-ink best practices: HIGH confidence (well-documented technology)
- Specific font sizes for 250x122: MEDIUM confidence (extrapolated from general e-ink guidelines)
- Feature prioritization: MEDIUM confidence (based on typical user behavior patterns)

**Recommended validation:**
- Test actual font sizes on physical Waveshare 2.13" V3 display
- Review SolarEdge API documentation for current endpoint availability
- Consider user testing with prototype layouts
- Verify Waveshare library capabilities for partial refresh
