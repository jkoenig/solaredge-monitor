---
phase: 11
slug: oauth-login-token-store
status: approved
reviewed_at: 2026-11-05
shadcn_initialized: false
preset: none
created: 2026-11-05
---

# Phase 11 — UI Design Contract

> One screen only: "Login nötig" on a 250x122 1-bit e-ink display (rendered 1000x488, 4x supersampled, LANCZOS downsample). Not a web UI. Sources: 11-CONTEXT.md D-06..D-09 (locked), screens/error.py, MEMORY layout grid.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (PIL rendering, no CSS/components) |
| Preset | not applicable |
| Component library | none; reuse the headline + centered-message pattern of `screens/error.py` (D-06) |
| Icon library | none (icons removed project-wide) |
| Font | Arial.ttf via `rendering.fonts.load_font` |

Implementation: add `render_login_required_screen()` (or a parametrized headline in `render_error_screen`) in `screens/error.py`. Returns a mode `'1'` image, 1000x488, white background (1), black text (0).

---

## Spacing Scale

N/A for web tokens (no 8-point CSS scale on a pixel canvas). E-ink equivalent: the project grid.

| Token | Value | Usage |
|-------|-------|-------|
| MARGIN | 5px | All edges; headline at (5, 5) |
| Canvas | 1000x488 | Supersampled; physical 250x122 |
| Content width | 990px | CANVAS_W - 2*MARGIN; hint wrap limit |

Exceptions: none. Hint is centered horizontally and vertically in the area from headline bottom to CANVAS_H - MARGIN (identical to error screen).

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Headline "Login nötig" | Arial 60 | regular (Arial.ttf) | single line, drawn at (MARGIN, MARGIN) |
| Hint | Arial 48 | regular | 1.2 (only if wrapped to 2 lines) |

Only 2 sizes, 1 weight. Hint at 48 measures 519px wide (PIL getbbox, fonts/Arial.ttf), so it fits on one line; render it single-line. Focal point: the headline is the primary anchor, the hint is secondary. Safeguard only: if a future copy change exceeds 990px, wrap at the word boundary after "Mac:" into "Mac:" / "login-Skript starten". Center each line horizontally and center the block vertically. Do not shrink the font. Umlaut "ö" in the headline needs no extra reserve (headline is top-anchored).

---

## Color

N/A (1-bit display, no palette). Equivalent contract:

| Role | Value | Usage |
|------|-------|-------|
| Background | white (1) | Entire canvas |
| Foreground | black (0) | Headline and hint text |
| Accent / Destructive | none | No grey, no inversion, no dithering |

No bars, icons, borders, or inverted blocks. Text only, so the screen is unmistakably different from data screens.

---

## Copywriting Contract

Display copy is German (user requirement).

| Element | Copy |
|---------|------|
| Headline | `Login nötig` |
| Hint (centered) | `Mac: login-Skript starten` (wrap allowed per Typography) |
| Primary CTA | none (no interaction; the hint is the instruction) |
| Empty state | not applicable (screen is shown only when the token is unusable) |
| Error state | this screen is the error state for: token file missing, corrupt/unreadable, or refresh rejected (D-07) |
| Destructive confirmation | none |

Behavior contract (locked):
- Shown immediately when the token is known unusable, with no 3-failure threshold (D-07).
- Exclusive: no data-screen rotation and no cached values while shown (D-08).
- Static: service stays up, makes no token/API calls, and re-renders only when a new token file appears (D-09). Redraw the e-ink panel once on entering the state, not on every poll.
- Screen is not part of `get_screens()` rotation; main.py renders it directly.

Out of scope for this spec: console/CLI output of the login script. Its language (German or English) is Claude's discretion.

---

## Registry Safety

N/A: no shadcn, no third-party registries, no web components.

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| none | none | not applicable |

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS
- [x] Dimension 2 Visuals: PASS (FLAG resolved: focal point stated)
- [x] Dimension 3 Color: PASS (N/A, 1-bit)
- [x] Dimension 4 Typography: PASS
- [x] Dimension 5 Spacing: PASS (MARGIN grid)
- [x] Dimension 6 Registry Safety: PASS (N/A)

**Approval:** approved 2026-11-05
