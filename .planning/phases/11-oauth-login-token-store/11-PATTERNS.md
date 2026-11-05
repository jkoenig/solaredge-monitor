# Phase 11: OAuth Login & Token Store - Pattern Map

**Mapped:** 2026-11-05
**Files analyzed:** 9 (4 new, 5 modified)
**Analogs found:** 7 / 9 (login script and tests have none)

Flat layout: all modules sit at repo root (`config.py`, `main.py`, `solaredge_api.py`, `forecast_api.py`, `models.py`, `logging_setup.py`), plus `screens/`, `rendering/`. No `scripts/` dir and no `tests/` dir exist.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `token_store.py` (NEW; file + lock + atomic persist + refresh) | service/store | file-I/O + request-response | `solaredge_api.py` (requests, log-and-return-None) and `forecast_api.py` (module style) | role-match |
| `oauth.py` (NEW, optional; token endpoint POST, bearer provider) | service | request-response | `solaredge_api.py` `_request()` | role-match |
| `models.py` (MOD: optional frozen `TokenData`) | model | transform | `models.py` `EnergyHistory`/`BatteryData` | exact |
| `screens/error.py` (MOD: add `render_login_required_screen()`) | component | transform (render) | `screens/error.py` `render_error_screen` | exact |
| `main.py` (MOD: login-needed state, startup w/o crash) | controller/loop | event-driven polling | `main.py` itself (sleep-window state `in_sleep`, `display.clear()`) | exact |
| `config.py` (MOD: client id/secret, token path, site_id optional) | config | request-response | `config.py` itself | exact |
| `.gitignore` (MOD) | config | n/a | existing `.env` block | exact |
| `.env.example` (MOD, small; full docs are Phase 14) | config | n/a | existing file | exact |
| `scripts/solaredge_login.py` (NEW; stdlib-only Mac script) | script/CLI | request-response + file-I/O (subprocess op/ssh/scp) | none | none |
| tests (optional) | test | n/a | none | none |

## Test infrastructure

No `tests/` dir, no pytest/unittest config, no test deps in `requirements.txt` (python-dotenv, python-json-logger, requests==2.31.0, Pillow==10.2.0). `.planning/codebase/TESTING.md` says: no framework, ad-hoc manual scripts only (`epd_2in13_V3_test.py` at root, hardware test). Validation of this phase is therefore manual (debug mode on Mac via `SOLAREDGE_DEBUG`, `Display(debug_mode=True)` writes PNGs to `debug/`). If the planner wants automated tests for the token store (atomic persist, corrupt file, 400 handling), it must add `tests/` and pytest as a new dev-only dependency (not in requirements.txt used on the Pi); no convention exists to copy.

## Pattern Assignments

### `screens/error.py` (component, render)

**Analog:** same file, `render_error_screen` (lines 1-52). Copy it verbatim into a sibling function with fixed headline "Login nötig" and hint "Mac: login-Skript starten" (UI-SPEC: single line, Arial 60 headline at (MARGIN, MARGIN), Arial 48 hint centered in area headline_bottom..CANVAS_H-MARGIN). Simplest: refactor to a private `_render_headline_message(headline, message)` and have both public functions call it, so "Fehler" output stays byte-identical.

Imports + constants (lines 8-14):
```python
from PIL import Image, ImageDraw
from rendering.fonts import load_font

CANVAS_W = 1000
CANVAS_H = 488
MARGIN = 5
```
Core (lines 28-51):
```python
img = Image.new('1', (CANVAS_W, CANVAS_H), 1)
draw = ImageDraw.Draw(img)
headline_font = load_font("Arial.ttf", 60)
headline_text = "Fehler"          # -> "Login nötig"
draw.text((MARGIN, MARGIN), headline_text, font=headline_font, fill=0)
headline_bbox = draw.textbbox((MARGIN, MARGIN), headline_text, font=headline_font)
headline_bottom = headline_bbox[3]
message_font = load_font("Arial.ttf", 48)
message_bbox = draw.textbbox((0, 0), message, font=message_font)
message_width = message_bbox[2] - message_bbox[0]
message_height = message_bbox[3] - message_bbox[1]
available_top = headline_bottom
available_bottom = CANVAS_H - MARGIN
available_height = available_bottom - available_top
message_x = (CANVAS_W - message_width) // 2
message_y = available_top + (available_height - message_height) // 2
draw.text((message_x, message_y), message, font=message_font, fill=0)
return img
```
Not added to `get_screens()` (UI-SPEC); main.py calls it directly like `render_error_screen()` and `display.render(image, "login")`.

### `main.py` (loop, event-driven)

**Analog:** itself. Relevant excerpts:

Imports (lines 36-43) add `from token_store import ...` after `from config import Config`. `load_dotenv()` stays before Config import.

Startup that must not crash without a token (lines 197-204): `api = SolarEdgeAPI(config.api_key, config.site_id)` and `battery_detected = api.has_battery()`. `config.site_id` is no longer required (D-14), so site_id must come from the token file; with no usable token, skip `has_battery()` and defer battery detection/`get_screens(...)` until a token becomes valid (lines 202-224 need to move into a "(re)initialize after login" helper, or run lazily).

State-flag-in-loop pattern to copy for login-needed (lines 239-252, sleep window):
```python
if is_sleep_time(config):
    if not in_sleep:
        logging.info("Entering sleep mode (display off until wake time)")
        display.clear()
        in_sleep = True
    interruptible_sleep(60)
    continue
else:
    if in_sleep:
        logging.info("Waking from sleep mode")
        in_sleep = False
        next_poll = time.monotonic()  # Force immediate poll after wake
```
Mirror this: `login_needed` bool; on entry render once (`display.render(render_login_required_screen(), "login")`, redraw only on entry, per UI-SPEC), then `interruptible_sleep(...)`/`continue` each tick with a cheap mtime/content check of the token file; on change, clear flag and set `next_poll = time.monotonic()`. Place the check after the sleep-window check (no refresh while asleep) and before the poll-due check. Existing 1 s ticks (`interruptible_sleep(1)`, line 257) are fine; D-12 says about every minute, so throttle the stat check.

Failure path to short-circuit (lines 295-323): `consecutive_failures >= MAX_FAILURES` -> `render_error_screen()`. A rejected-token result must NOT go through this counter (D-07); the data-fetch layer needs a distinguishable signal (exception such as `LoginRequired`, or a flag on the token provider) since API methods return `None` on every failure (`solaredge_api.py` lines 60-90).

Shutdown/finally (lines 335-340) unchanged: `display.clear(); display.sleep()`.

### `config.py` (config)

**Analog:** itself. Env loading idiom (lines 62-68):
```python
self.api_key = os.environ.get("SOLAREDGE_API_KEY", "")
if not self.api_key:
    errors.append("  - SOLAREDGE_API_KEY: SolarEdge API key (required)")
```
Changes: keep `api_key` required (D-15); drop the `site_id` required check (lines 66-68) and make it optional/informational; add `client_id`, `client_secret` (via `os.environ.get("SOLAREDGE_CLIENT_ID", "")`), and `token_file` default `/home/pi/solaredge-monitor/.tokens.json` (consider `SOLAREDGE_TOKEN_FILE`, default derived from `Path(__file__).parent / ".tokens.json"` which equals the Pi path and is Mac-friendly). Decide whether missing client id/secret is a validation error or leads to "Login nötig"; the errors-list idiom is the pattern if required. Dataclass field declarations at lines 41-42 and docstring lines 26-28 must be updated.

Masking (lines 136-141), extend for client id/secret (never print secret in full, D-16):
```python
masked_key = f"****{self.api_key[-4:]}" if len(self.api_key) >= 4 else "****"
logging.info(f"  SOLAREDGE_API_KEY: {masked_key}")
masked_site = f"****{self.site_id[-4:]}" if len(self.site_id) >= 4 else "****"
```
For the secret prefer logging only "set"/"missing" rather than last 4 chars.

### `token_store.py` (NEW; store + refresh, file-I/O + request-response)

**Analog (style only):** `solaredge_api.py` and `forecast_api.py`: module docstring, `import logging`, `import requests`, `Optional` returns, log-and-return-None, 10 s timeout. No existing file-locking or atomic-write code in the repo, so the atomic persist/flock logic comes from V2-API.md section 6 pitfalls 1 and 2 (tmp file, flush, `os.fsync`, `os.replace`, fsync dir, mode 0600, `fcntl.flock` on a separate lock file, persist before using new access token).

Error/logging idiom to copy (`solaredge_api.py` lines 78-90):
```python
try:
    response = self.session.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()
except requests.exceptions.Timeout:
    logging.error(f"API timeout after 10s: {endpoint}")
    return None
except requests.exceptions.HTTPError as e:
    logging.error(f"API HTTP error {e.response.status_code}: {endpoint}")
    return None
except requests.exceptions.RequestException as e:
    logging.error(f"API request failed: {endpoint} - {e}")
    return None
```
Adapt: token endpoint `requests.post(url, json={...}, timeout=10)` (no Retry adapter, no retry loop on 400/401, D-05). Distinguish three outcomes: success, rejected (400/401 -> login needed), transient (timeout/5xx/network -> keep token, try later, NOT login needed). Never log the body, tokens, or secret.

Frozen dataclass model idiom (`models.py` lines 14, 87-101): `@dataclass(frozen=True)` with docstring "Fields:" list and `fetched_at: datetime = field(default_factory=datetime.now)`. Optional `TokenData` (access_token, refresh_token, expires_at, site_id, obtained_at, granted_at) can follow this. Note `expires_at`/`granted_at` are absolute UTC epoch floats, unlike `fetched_at` naive local datetime.

Session building block for Phase 12: `SolarEdgeAPI.__init__` (lines 35-58) builds `requests.Session` with blanket `Retry`; Phase 11 should expose something like `get_access_token()` (refresh if `expires_at - 300 < now`, under flock) and `force_refresh()` for the 401 refresh-once-retry-once rule; do not edit `SolarEdgeAPI` V1 calls this phase (Phase 12 replaces them).

Grant-expiry warning (D-20): once-a-day `logging.warning` when `now > granted_at + 24 months - 30 days`; track last-warned date in memory.

Time source note: use `time.time()` (UTC epoch) for `expires_at`; the repo only uses `ZoneInfo("Europe/Berlin")` for sleep windows (`main.py` lines 67-68).

### `scripts/solaredge_login.py` (NEW; no analog)

No existing CLI script, no `scripts/` dir. Only constraints apply: stdlib only, system `python3` (D-18), `op`/`ssh`/`scp` via `subprocess` (host alias `se-monitor`), shebang `#!/usr/bin/env python3` (as in `main.py` line 1), argparse flag `--secrets-only`. Use research steps in V2-API.md section 2 "Recommended Mac login script" (listener on 8765, `state` check only if present, JSON POST incl. `redirect_uri`, token file with `granted_at`, scp to temp name then `mv` on Pi then chmod 600, delete local copy). `.env` update on Pi: idempotent replace of `SOLAREDGE_CLIENT_ID`/`SOLAREDGE_CLIENT_SECRET` lines, keep the rest; pass secret via stdin, not argv (argv shows in `ps`). Do not put secrets in logged commands.

Deployment facts from `deploy.sh`: runs as user `pi` from the script dir, `git pull` + service restart; unchanged. Service: `User=pi`, `WorkingDirectory=/home/pi/solaredge-monitor`.

### `.gitignore` (config)

Existing secrets block (lines 1-4):
```
# Environment and secrets
.env
.env.*
!.env.example
```
Add `.tokens.json`, `.tokens.json.*` (tmp files) and the lock file name (e.g. `.tokens.lock`) here. Note `.planning/` is gitignored.

### `.env.example` (config)

Existing style: banner section comments, `KEY=placeholder` for required. Add `SOLAREDGE_CLIENT_ID` / `SOLAREDGE_CLIENT_SECRET` placeholder lines (noting they are written by the login script) and demote `SOLAREDGE_SITE_ID` to optional/comment. Full docs are Phase 14.

## Shared Patterns

### Return-None-and-log error handling
**Source:** `solaredge_api.py` lines 60-90; `forecast_api.py` (same). **Apply to:** `token_store.py`/`oauth.py`. English log messages, German display text only.

### Secret masking
**Source:** `config.py` lines 136-141. **Apply to:** `Config.log_startup()` additions and any log line in token code (D-16). Never log tokens/secret/response bodies.

### Logging
**Source:** `logging_setup.py` (JSON via `pythonjsonlogger`, stdout to journal). **Apply to:** all Pi-side modules: use bare `logging.info/warning/error(...)` (root logger), as `main.py` and `solaredge_api.py` do. The Mac login script is not part of this (use `print`).

### Shutdown-aware waiting
**Source:** `main.py` `interruptible_sleep` lines 87-100 and `shutdown_flag`. **Apply to:** login-needed idle in main loop; never use bare `time.sleep` for long waits.

### Display rendering
**Source:** `main.py` line 308-309: `display.render(error_image, "error")`; `display.clear()` at 243. **Apply to:** login screen (render once on entry).

## Conventions

Derivation tool returned `skipped: no-readable-files` (it expects the plugin's own CJS/ESM layout), so this is a manual read of the Python repo.

| Axis | Dominant | Share | Entropy | Status |
|---|---|---|---|---|
| File-name casing | snake_case (`solaredge_api.py`, `logging_setup.py`) | ~100% | low | named contract |
| Identifier casing | snake_case functions/vars, PascalCase classes, UPPER_CASE constants | ~100% | low | named contract |
| Export style | module-level defs, no `__all__`; frozen dataclasses for models | ~100% | low | named contract |
| Import style | absolute flat imports (`from models import ...`), stdlib then third-party then local, `from x import y` | ~95% | low | named contract |

Contested hotspots (author's choice): none found in this Python repo (the CJS<->SDK dual resolver does not apply here). Match the local style: module docstring at top, Google-style docstrings with Args/Returns, type hints with `Optional[...]`, English code and logs, German display strings.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `scripts/solaredge_login.py` | CLI script | browser OAuth + subprocess | no scripts or CLI in repo; use V2-API.md section 2 |
| atomic write + `fcntl.flock` logic in `token_store.py` | store | file-I/O | no file persistence exists; use V2-API.md section 6 items 1-2 |
| tests | test | n/a | no test infra |

## Metadata

**Analog search scope:** repo root `*.py`, `screens/`, `rendering/`, `.gitignore`, `.env.example`, `.planning/codebase/TESTING.md`, `.planning/research/V2-API.md` sections 2 and 6
**Files scanned:** about 14
**Pattern extraction date:** 2026-11-05
