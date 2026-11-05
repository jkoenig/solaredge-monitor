# Phase 11: OAuth Login & Token Store - Context

**Gathered:** 2026-11-05
**Status:** Ready for planning

<domain>
## Phase Boundary

The owner logs in once from the Mac (browser consent, callback on http://localhost:8765/callback); the login script puts the token pair on se-monitor. From then on only the Pi refreshes tokens, persisting each rotated refresh token atomically under a file lock. When the token is missing, corrupt or rejected, the display shows "Login nötig", the service stays up, and it resumes on its own once a fresh token file appears.

Not in this phase: replacing V1 data calls with V2 endpoints and removing V1 code (Phase 12), fetch schedule and quota counter (Phase 13), README/.env.example docs and systemd time-sync (Phase 14). Phase 11 provides the token store and an authenticated-request building block that Phase 12 uses.

</domain>

<decisions>
## Implementation Decisions

### Carried forward (already locked before this discussion)
- **D-01:** Only the Pi refreshes tokens. The Mac script does the initial login only and must not keep a refreshing copy (STATE.md, research pitfall 2).
- **D-02:** Callback at `http://localhost:8765/callback`; validate `state` only if it is present (SolarEdge may not echo it).
- **D-03:** Client ID/secret read on the Mac from 1Password via `op`, item `7rboxat3in2tlx2ywilmsna5cy`.
- **D-04:** Token file mode 0600; rotated pair persisted with tmp file + flush + fsync + `os.replace` (+ directory fsync) under `fcntl.flock`, *before* the new access token is used.
- **D-05:** Any 400/401 from the token endpoint means re-login needed; no retry loop on it. Token endpoint uses JSON body (`requests.post(json=...)`), no PKCE, no requests-oauthlib.

### "Login nötig" display state
- **D-06:** Screen layout: headline "Login nötig" top-left (same headline position/font as other screens, Arial 60), below it a centered hint "Mac: login-Skript starten" (may wrap to two lines). Extend/reuse `screens/error.py` pattern (headline + centered message) rather than inventing a new layout.
- **D-07:** Shown **immediately** once the token state is known to be unusable (file missing, unreadable/corrupt, or token endpoint rejects refresh). No 3-failure threshold like the generic API error screen.
- **D-08:** While login is needed, the display shows **only** the "Login nötig" screen. Cached data screens do NOT keep rotating (no stale numbers that look current).
- **D-09:** Service does not exit; it stays in the login-needed state and makes no further token/API calls until a new token file appears.

### Getting tokens onto the Pi
- **D-10:** The login script copies the token file to se-monitor itself via `scp` (SSH host alias `se-monitor`, user `pi`), then sets mode 0600 on the Pi. It deletes any local token copy on the Mac afterwards; the Mac keeps nothing that can refresh.
- **D-11:** Token file path on the Pi: `/home/pi/solaredge-monitor/.tokens.json` (app directory, next to `.env`). Add `.tokens.json` to `.gitignore`. Path should be a config value with this default so debug runs on the Mac can point elsewhere.
- **D-12:** Pick-up is automatic: while in "Login nötig", the Pi checks on each loop iteration (about every minute) whether a new/changed token file exists (e.g. mtime/content change) and resumes fetching without a restart. Write the file on the Pi atomically (upload to temp name, then `mv`) so the service never reads a half-copied file.

### Client secret & site ID on the Pi
- **D-13:** Client ID and secret live in the Pi's `.env` as `SOLAREDGE_CLIENT_ID` and `SOLAREDGE_CLIENT_SECRET`. They are not typed by hand: a Mac-side step reads them from 1Password via `op` and writes/updates those two lines in `/home/pi/solaredge-monitor/.env` over SSH (idempotent: replace existing lines, keep everything else). `deploy.sh` on the Pi stays as is.
- **D-14:** The site ID comes from the login callback (`site_id`) and is stored in the token file. `SOLAREDGE_SITE_ID` is no longer required in `.env`; the app reads the site ID from the token file.
- **D-15:** `SOLAREDGE_API_KEY` stays (still required) during Phase 11; it is removed together with the V1 code in Phase 12.
- **D-16:** Secrets (client secret, tokens) must never be logged; mask like the existing api_key/site_id masking in `config.log_startup()`.

### Login script
- **D-17:** One command does everything: `python3 scripts/solaredge_login.py` runs browser login → token exchange → token file to the Pi → client ID/secret into the Pi's `.env`. A flag (e.g. `--secrets-only`) updates only the `.env` secrets without a new login (for client-secret rotation).
- **D-18:** Python standard library only (http.server, urllib, json, webbrowser, secrets, subprocess). Runs on the Mac with system `python3`, no venv or pip install. Uses `op`, `ssh` and `scp` as subprocess calls.
- **D-19:** Authorize URL as in research: `https://connect.solaredge.com/authorize?client_id=…&redirect_uri=…&scope=SITE_DATA%20DEVICE_DATA&state=<random>&access_duration=24`. Token file stores at least `access_token`, `refresh_token`, `expires_at` (absolute UTC epoch), `site_id`, `obtained_at`, and `granted_at` (for the 24-month expiry).
- **D-20:** 24-month grant expiry: from 30 days before `granted_at + 24 months`, the Pi logs a warning once a day. No display change. After expiry the normal "Login nötig" path applies.

### Claude's Discretion
- Exact refresh threshold (research suggests refresh when `expires_at − 5 min` has passed and a call is due); treat any API 401 as "refresh once, retry once".
- Module layout (e.g. `token_store.py` / `oauth.py`) and how the authenticated session is exposed for Phase 12.
- How `main.py` represents the login-needed state in the loop.
- Script output/verbosity and error messages (German or English console text is fine; display text is German).
- Lock file details and mtime-vs-hash detection for the new token file.
- Whether to hold off on any refresh while in the sleep window (research: don't refresh while asleep; once a day is enough for the 14-day window).

</decisions>

<specifics>
## Specific Ideas

- Display mock agreed in discussion:
  ```
  ┌──────────────────────────┐
  │ Login nötig              │
  │                          │
  │   Mac: login-Skript      │
  │        starten           │
  └──────────────────────────┘
  ```
- The user wants the whole setup driven from the Mac with secrets coming from 1Password, never typed into the Pi by hand.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### OAuth / V2 API
- `.planning/research/V2-API.md` §2 "OAuth2 flow (Site Access)": authorize/token URLs, JSON body, rotation, 14-day idle expiry, 24-month grant, error codes
- `.planning/research/V2-API.md` §6 "Pitfalls" items 1–4, 7, 13, 14: atomic persist, two-refresher race, idle expiry, grant expiry, clock skew, JSON token endpoint, secret rotation
- `.planning/research/V2-API.md` §7 "Open questions" 1–4: refresh credit cost, `state` echo, exact rejected-refresh error, 14 vs 30 days
- `.planning/research/PITFALLS.md`, `.planning/research/ARCHITECTURE.md`: milestone-level research

### Requirements
- `.planning/REQUIREMENTS.md`: AUTH-01..AUTH-04
- `.planning/ROADMAP.md` Phase 11: success criteria 1–4

### Existing code
- `screens/error.py`: headline + centered message layout to reuse for "Login nötig"
- `main.py`: polling loop, failure handling, screen cycle
- `config.py`: env loading, validation, secret masking in `log_startup()`
- `solaredge-monitor.service`: User=pi, WorkingDirectory=/home/pi/solaredge-monitor
- `deploy.sh`: Pi-side git pull + restart (unchanged by this phase)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `screens/error.py` `render_error_screen(message)`: already does headline (Arial 60) + centered message (Arial 48) on the 1000x488 canvas; generalize with a headline parameter or add a sibling `render_login_needed_screen()`.
- `config.Config`: env parsing with collected validation errors and masked startup logging; add CLIENT_ID/SECRET and token file path here.
- `logging_setup.py`: JSON structured logging, journal-only by default (spare the SD card).

### Established Patterns
- Frozen dataclasses for models (`models.py`).
- API methods return `None` on failure and the loop falls back to cached data; the login-needed state must short-circuit this (no 3-failure threshold, no stale rotation).
- `interruptible_sleep` + `shutdown_flag` for SIGTERM handling; the token-file check fits into the existing 1–60 s loop ticks.
- German display labels, English code/logs.

### Integration Points
- `solaredge_api.SolarEdgeAPI.__init__(api_key, site_id)` + `_request()` use a requests Session with a blanket urllib3 Retry; Phase 11 adds a bearer-token provider that Phase 12's V2 client will use (Phase 12 removes the Retry).
- `main.py` startup currently calls `api.has_battery()` immediately; with no valid token it must go into "Login nötig" instead of crashing.
- `.gitignore` needs `.tokens.json` (and any lock file).

</code_context>

<deferred>
## Deferred Ideas

None. The discussion stayed within the phase scope.

</deferred>

---

*Phase: 11-oauth-login-token-store*
*Context gathered: 2026-11-05*
