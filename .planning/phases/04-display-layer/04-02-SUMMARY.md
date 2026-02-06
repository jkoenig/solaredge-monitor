---
phase: 04-display-layer
plan: 02
subsystem: ui
tags: [pillow, e-ink, rendering, screen-layouts, german-localization]

# Dependency graph
requires:
  - phase: 04-01
    provides: Rendering utilities (fonts, icons, bars)
  - phase: 03-03
    provides: EnergyDetails model with daily energy data
provides:
  - 4 screen renderer functions (production, consumption, feed-in, purchased)
  - SCREENS registry list for Phase 5 polling loop
  - German-localized labels throughout
  - Complex screens with icon breakdowns (production, consumption)
  - Simple full-screen layouts (feed-in, purchased)
affects: [05-polling-engine, display-driver-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Complex screen layout: top section (label, large value, unit, bar) + bottom section (3-column icon breakdown)"
    - "Simple screen layout: centered label, extra-large value, bar"
    - "Screen function signature: (data: EnergyDetails) -> Image (mode='1', size=(1000,488))"
    - "German labels: Produktion, Verbrauch, Einspeisung, Bezug, Eigenverbrauch, Batterie, Netz, Solar"

key-files:
  created:
    - screens/__init__.py
    - screens/production.py
    - screens/consumption.py
    - screens/feed_in.py
    - screens/purchased.py
  modified: []

key-decisions:
  - "Complex screens show large values (140px) with 3-column breakdowns; simple screens use extra-large values (180px) centered"
  - "Production bar: 20 kWh daily max; Consumption bar: 15 kWh daily max; Feed-in/Purchased bars: 10 kWh daily max"
  - "Battery energy calculated as delta: production - self_consumption - feed_in (production screen) or consumption - self_consumption - purchased (consumption screen)"
  - "All screens use baseline-aligned unit text to the right of values for visual consistency"

patterns-established:
  - "Screen renderer pattern: Accept EnergyDetails, return 1000x488 1-bit PIL Image"
  - "Font sizing: Labels 56-64px, large values 140-180px (larger for simple screens), units 48-56px, breakdown 36-44px"
  - "Icon size: 60px for breakdown sections"
  - "Horizontal centering for simple screens; left-aligned for complex screens"

# Metrics
duration: 2min
completed: 2026-02-06
---

# Phase 4 Plan 2: Screen Renderers Summary

**4 German-localized screen renderers transform EnergyDetails into 1000x488 1-bit images: complex layouts with icon breakdowns (Produktion, Verbrauch) and simple full-screen displays (Einspeisung, Bezug)**

## Performance

- **Duration:** 2 minutes
- **Started:** 2026-02-06T15:25:30Z
- **Completed:** 2026-02-06T15:27:33Z
- **Tasks:** 2
- **Files created:** 5

## Accomplishments
- Produktion screen shows production with 3-way breakdown: Eigenverbrauch (house icon), Batterie (battery icon), Netz (grid icon)
- Verbrauch screen shows consumption with 3-way source breakdown: Solar (sun icon), Batterie, Netz
- Einspeisung and Bezug screens use full display for extra-large single metric
- SCREENS registry list enables Phase 5 polling loop to cycle through all 4 screens
- All screens return 1000x488 1-bit PIL Images ready for e-ink display

## Task Commits

Each task was committed atomically:

1. **Task 1: Create complex screens (Produktion and Verbrauch) with breakdown rows** - `a92d161` (feat)
2. **Task 2: Create simple screens (Einspeisung and Bezug) — full-screen single metrics** - `a14be12` (feat)

## Files Created/Modified

**Created:**
- `screens/__init__.py` - Package init with SCREENS registry list (4 render functions)
- `screens/production.py` - Produktion screen: large kWh value + bar + 3-column breakdown (house/battery/grid icons)
- `screens/consumption.py` - Verbrauch screen: large kWh value + bar + 3-column source breakdown (sun/battery/grid icons)
- `screens/feed_in.py` - Einspeisung screen: centered extra-large value, full-screen layout
- `screens/purchased.py` - Bezug screen: centered extra-large value, full-screen layout

## Decisions Made

**1. Font size differentiation by screen complexity**
- Complex screens (production, consumption): 140px bold value fonts
- Simple screens (feed-in, purchased): 180px bold value fonts
- Rationale: Simple screens have more vertical space without breakdown section

**2. Daily max assumptions for percentage bars**
- Production: 20 kWh (home production capacity)
- Consumption: 15 kWh (typical daily consumption)
- Feed-in and Purchased: 10 kWh (grid interaction)
- Rationale: Based on typical residential solar system, bars show meaningful progress

**3. Battery energy calculation as delta**
- Production screen: battery = production - self_consumption - feed_in
- Consumption screen: battery = consumption - self_consumption - purchased
- Clamped to 0 if negative (edge case handling)
- Rationale: Battery energy not directly in EnergyDetails model, must be derived

**4. Baseline-aligned unit text**
- "kWh" unit text placed to right of value with bottom baseline alignment
- Rationale: Professional typography, values and units read as single unit

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - rendering utilities from 04-01 provided all needed functions.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready:**
- All 4 screen renderers complete and verified
- SCREENS registry ready for polling loop iteration
- German localization complete
- 1000x488 1-bit images render correctly for e-ink display

**Next steps:**
- Phase 4 Plan 3: Status screen (battery SOC, real-time power flow)
- Phase 4 Plan 4: Screen scaling (1000x488 → 250x122 for hardware)
- Phase 5: Polling engine to cycle through screens

---
*Phase: 04-display-layer*
*Completed: 2026-02-06*
