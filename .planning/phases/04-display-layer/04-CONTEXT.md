# Phase 4: Display Layer - Context

**Gathered:** 2026-02-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Render solar energy data onto a 250x122 e-ink display (4x supersampling at 1000x488) with readable fonts and screen cycling. Display functions receive typed data models (PowerFlow, EnergyDetails) and produce images. Debug mode outputs PNG files. Polling loop and operational behavior are Phase 5.

</domain>

<decisions>
## Implementation Decisions

### Screen content (4 screens, all German labels)

**Screen 1 — Produktion:**
- Large "Produktion" label + total kWh value + horizontal bar with percentage
- Breakdown row with 3 sub-items showing where production went:
  - House icon (Eigenverbrauch / self-consumption) + kWh
  - Battery icon (Batterie / charged into battery) + kWh
  - Grid icon (Netz / feed-in to grid) + kWh

**Screen 2 — Verbrauch:**
- Large "Verbrauch" label + total kWh value + horizontal bar with percentage
- Breakdown row with 3 sub-items showing where consumption came from:
  - PV icon (solar / from PV production) + kWh
  - Battery icon (Batterie / from battery) + kWh
  - Grid icon (Netz / from grid) + kWh

**Screen 3 — Einspeisung:**
- Feed-in to grid: kWh value + horizontal bar
- Full screen for this single metric

**Screen 4 — Bezug:**
- Grid purchase: kWh value + horizontal bar
- Full screen for this single metric

### Visual hierarchy & fonts
- kWh numbers as large as possible — maximize readability from 2-3 meters
- "kWh" unit shown in smaller text next to value (like the SolarEdge app screenshots)
- No screen titles/headers — labels (Produktion, Verbrauch, etc.) are self-explanatory
- Simple PIL-drawn geometric shapes for icons (battery rectangle, house outline, grid lines, sun circle) — no FontAwesome font icons
- Horizontal bars show percentage inside or next to them

### Screen cycling
- 4 screens in equal rotation (each gets same display time)
- Cycling interval: Claude's discretion
- Start screen: Claude's discretion

### Claude's Discretion
- Font choice (Arial available, can pick what renders best on e-ink)
- Font sizes within constraint: values as large as possible, labels smaller
- Bar chart style (filled, outlined, etc.)
- Layout of breakdown items relative to main value and bar
- Cycling interval between screens
- Starting screen on boot
- Icon drawing details (exact shapes, sizes)
- How to handle the percentage display on bars

</decisions>

<specifics>
## Specific Ideas

- User referenced the SolarEdge monitoring app (screenshots provided) as the visual model — two-row layout with label, kWh value, horizontal bar, and source breakdown
- Readability from 2-3 meter distance is a key requirement — this drove the decision to split Produktion and Verbrauch into separate screens rather than cramming both onto one
- Each of the 4 screens gets the full 250x122 display to itself for maximum readability
- Data source: EnergyDetails model provides production, self_consumption, feed_in, consumption, purchased; PowerFlow provides additional real-time breakdown data

</specifics>

<deferred>
## Deferred Ideas

- Additional screens (battery SOC, grid on/off status) — user wants to add more screens later
- Screen priority/weighting — all equal for now, could change when more screens are added

</deferred>

---

*Phase: 04-display-layer*
*Context gathered: 2026-02-06*
