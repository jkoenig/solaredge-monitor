---
phase: 12
slug: v2-data-client-screens
status: approved
shadcn_initialized: false
preset: none
created: 2026-11-05
---

# Phase 12 — UI Design Contract

> Data-source phase on a 250x122 1-bit e-ink display (rendered 1000x488, 4x supersampled, LANCZOS downsample). Not a web UI. Layouts, fonts, and positions in `screens/*.py` and `rendering/*.py` are unchanged. This contract locks only the labels, value formats, and data-to-field mapping. Sources: 12-CONTEXT.md D-03..D-06, D-08, D-10, D-11; MEMORY layout grid.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (PIL rendering) |
| Preset | not applicable |
| Component library | none; existing renderers and `rendering/` helpers |
| Icon library | none (icons removed project-wide) |
| Font | Arial.ttf / ArialBlack via `rendering.fonts.load_font` |

**No new on-screen elements.** No new screens, rows, columns, icons, staleness markers, or error text on data screens. All sizes, margins, and the reserved breakdown area (110px; 125px on Hausakku) stay as in the current code.

---

## Spacing Scale

Unchanged project grid. Phase 12 adds no tokens.

| Token | Value | Usage |
|-------|-------|-------|
| MARGIN | 5px | All edges |
| Canvas | 1000x488 | Supersampled |
| Breakdown reserve | 110px (Hausakku: 125px) | Unchanged |

Exceptions: none.

---

## Typography

Unchanged. No new roles.

| Role | Size | Weight |
|------|------|--------|
| Headline | Arial 60 | regular |
| Value | ArialBlack 120 | black |
| Unit (kWh / %) | Arial 64 | regular |
| Bar legend | Arial 56 | regular |
| Breakdown label / value | Arial 52 / Arial 60 | regular |
| History sub-label / dates | Arial 44 / Arial 36 | regular |

---

## Color

1-bit: white background (1), black foreground (0). No grey, no dithering, no inversion. Accent and destructive: none.

---

## Screen Contracts

Display copy is German. Number format: one decimal with `.` as in the current code (`f"{x:.1f}"`), except SoC and temperature (integer).

### General rules

- **Null rule (D-08):** any null or missing V2 numeric field is treated as 0 and rendered as a normal number (`0.0 kWh`). No "–", "n/a", or blank for a null in a successful response.
- **Unit rule (D-08):** convert by the response `unit` (Wh to kWh). Never assume Wh.
- **Fetch failure:** keep showing the last successful values (`last_successful_*`). No new on-screen indicator. The existing error screen and the Phase 11 "Login nötig" screen are unchanged.
- No serial numbers or site IDs on screen or in logs.

### Produktion (breakdown from overview)

| Element | Label | Value source |
|---------|-------|--------------|
| Headline value | existing | `production.total`, kWh, `.1f` |
| Column 1 | `Verbraucht` | `production.toSelfConsumption` (kWh; `consumption.fromPv` is not used on this screen) |
| Column 2 | `In Akku` | `production.toStorage` (kWh) |
| Column 3 | `Ins Netz` | `production.toGrid` (feed-in, kWh) |

The remainder derivation for "In Akku" is replaced by the direct value. Labels unchanged. The bar legend stays as it is today (percentage text from `draw_horizontal_bar`).

### Verbrauch (breakdown from overview)

| Element | Label | Value source |
|---------|-------|--------------|
| Headline value | existing | `consumption.total`, kWh, `.1f` |
| Column 1 | `Von PV` | `consumption.fromPv` (kWh) |
| Column 2 | `Von Akku` | `consumption.fromStorage` (kWh) |
| Column 3 | `Vom Netz` | `consumption.fromGrid` (purchased, kWh) |

The remainder derivation for "Von Akku" is replaced by the direct value. Labels unchanged.

### Einspeisung / Bezug

Layout and labels unchanged. Einspeisung = `production.toGrid`, Bezug = `consumption.fromGrid`, in kWh, `.1f`.

### Prognose

Unchanged. `actual_production` comes from overview `production.total`.

### Hausakku

| Element | Contract |
|---------|----------|
| Headline | unchanged |
| Value | SoC = `stateOfEnergy`, integer, with `%` as today (last non-null, last ~1 h QUARTER_HOUR) |
| Bar | drawn manually, fill = SoC (unchanged; no auto percentage text) |
| Bar legend | `Lädt mit X.X kW` when charging, `Entlädt mit X.X kW` when discharging, empty string when idle. X = abs(`chargePower − dischargePower`) / 1000, `.1f` |
| Idle | abs net power below an idle threshold (recommended 50 W, planner may adjust) gives an empty legend. The English `Idle` / "Leerlauf" label must never appear on screen |
| Column 1 | `Temperatur`, value `{internalTemperature:.0f}°C` from `/storage/status`, last non-null |
| Column 2 | `Verfügbar`, value `{remainingEnergy / 1000:.1f} kWh` from `/storage/telemetry`, last non-null. This is the energy currently stored, not the pack size |

Behavior:
- Temperature is refreshed only twice a day (first daytime poll and around midday). Between refreshes the screen shows the last fetched value. Not a staleness case: no marker.
- Temperature rule: a successful `/storage/status` fetch that returns null renders `0°C`. If no fetch has happened yet or it failed, no temperature value is invented; the existing battery fallback behavior is reused (planner picks the concrete fallback).
- The Hausakku screen is in the rotation only if at least one `active: true` battery exists (D-09). Rotation order is unchanged.
- The 2-column grid stays at CANVAS_H - MARGIN - 125.

### Verlauf Produktion / Verlauf Verbrauch

| Element | Contract |
|---------|----------|
| Bars | exactly 14 (13 past days + today), 6px gap, ~65px wide, solid black, bottom-aligned, height proportional to the max of the 14 values |
| Past 13 days | production from `/sites/{id}/energy?resolution=DAY&unit=WH`, consumption from `/meters/telemetry?resolution=DAY` (`consumptionEnergy`, summed over all meters carrying the metric) |
| Today's bar | patched from overview `production.total` / `consumption.total`, so it grows during the day. Shape and styling identical to the other bars (no hatching, no outline) |
| Date labels | local date part of the timestamp (site offset ignored, no UTC conversion), same Arial 36 format as today |
| Sub-label | `max: X.X kWh` right-aligned, label left, unchanged; max includes today's patched value |
| Null | a null bucket is 0 (no bar, label still drawn) |

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA | none (no interaction) |
| Empty state | none; null renders as `0.0 kWh` / empty legend per the rules above |
| Error state | no new copy. Existing error screen and Phase 11 "Login nötig" unchanged |
| Destructive confirmation | none |

New German strings introduced by this phase: none. All labels above already exist in the code.

---

## Registry Safety

N/A: no shadcn, no third-party registries.

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| none | none | not applicable |

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS
- [x] Dimension 2 Visuals: PASS
- [x] Dimension 3 Color: PASS
- [x] Dimension 4 Typography: PASS
- [x] Dimension 5 Spacing: PASS
- [x] Dimension 6 Registry Safety: PASS

**Approval:** pending
