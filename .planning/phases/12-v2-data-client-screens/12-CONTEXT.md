# Phase 12: V2 Data Client & Screens - Context

**Gathered:** 2026-11-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Every existing screen (Produktion, Verbrauch, Einspeisung, Bezug, Hausakku, Verlauf Produktion, Verlauf Verbrauch; Prognose stays on Forecast.Solar) is filled from the SolarEdge Monitoring API V2 through the Phase 11 token store (`TokenStore.authorized_request`). All V1 code is removed: V1 endpoints, `api_key` auth, `PowerFlow` model and fetch, `SiteOverview`, inventory call, and the blanket urllib3 Retry on 429/5xx (at most one retry on 5xx/timeout). `SOLAREDGE_API_KEY` is removed from config (deferred from Phase 11 D-15).

Not in this phase: the persistent call counter with hard stop at 1,800 and the final 07:00–20:00 fetch schedule (Phase 13), README/.env.example docs and systemd time-sync (Phase 14). Phase 12 does ship an interim slower cadence so it can run on se-monitor right away (D-07).

</domain>

<decisions>
## Implementation Decisions

### Carried forward
- **D-01:** All V2 calls go through `TokenStore.authorized_request` (Bearer header, refresh once + retry once on 401, `LoginRequired` → "Login nötig" state from Phase 11). Site ID comes from the token file (`TokenStore.site_id`).
- **D-02:** Free tier: 2,000 credits/month, 10 calls/min, every call costs a credit. No monthly quota header is sent (confirmed live, D-12), so budget discipline is on us.

### Hausakku screen
- **D-03:** "Temperatur" column stays. Temperature comes from `GET /sites/{id}/storage/status` (`internalTemperature`, last non-null value), fetched **twice a day** only (e.g. first daytime poll and around midday); the screen shows the last fetched value in between.
- **D-04:** "Verfügbar" shows the energy **currently stored**: `remainingEnergy` (Wh → kWh) from `/storage/telemetry`, last non-null value. Not the pack size (the V1 code showed `fullPackEnergyAvailable`, which was wrong).
- **D-05:** SoC = `stateOfEnergy` (%), power = `chargePower − dischargePower` (W, both positive in V2), from `/storage/telemetry?resolution=QUARTER_HOUR` over the last ~1 h, last non-null value per metric. Status Laden/Entladen/Ruhe derived from charge vs discharge power with a small threshold (Claude's discretion); existing legend style kept ("Lädt mit X kW" / "Entlädt mit X kW" / empty when idle).

### Verlauf (14-day history)
- **D-06:** Today's bar is kept **up to date during the day** from the overview values that are fetched anyway (`production.total`, `consumption.total`), so it grows through the day without extra calls. The 13 past days come from the once-a-day history fetch.

### Rollout before Phase 13
- **D-07:** Phase 12 is deployed to se-monitor **immediately** with an interim slower cadence so the display shows real values again: overview about every 30 min during daytime only, storage telemetry about hourly, history once a day, temperature twice a day. Target ≤ ~60 calls/day including token refreshes (≈ 1,800/month worst case, normally less). Default poll interval and daytime window are adjusted so the Pi's current `.env` (no POLL/SLEEP overrides set, i.e. code defaults 5 min / sleep 0–6) does not burn credits. Exact mechanism is Claude's discretion; Phase 13 replaces it with the final schedule and the hard counter.

### Live API shape (probed on se-monitor 2026-11-05, owner approved ~8 calls)
- **D-08:** `GET /overview` (no params): all fields present and float, `unit: "WH"` for both production and consumption, `siteId` int. Still convert via `unit` and treat null as 0 (spec says nullable).
- **D-09:** `GET /devices?types=BATTERY` returns **2 entries: one `active: false` (replaced), one `active: true`**. Battery presence = at least one `active: true` battery. `/storage/telemetry` only returns the active one's serial. Cache the result on disk (API-03); no inventory call on restart.
- **D-10:** `GET /meters/telemetry?resolution=DAY` returns **only a virtual `"CONSUMPTION"` meter with `consumptionEnergy`** (no `productionEnergy`) for this site. Production history must come from **`GET /sites/{id}/energy?resolution=DAY&unit=WH`** (14 values, no nulls). So the daily history fetch is **2 calls**. Parser must not assume meter keys are serials; sum all meters that carry the metric.
- **D-11:** Timestamps carry the site offset (`+01:00` / `+02:00` across DST); DAY buckets start at local midnight → bucket by the local date part. `/storage/telemetry` QUARTER_HOUR values were all non-null over the last hour; `acGridChargingEnergy` came back with an empty values list (ignore it).
- **D-12:** Response headers: only `x-ratelimit-limit-minute` (10) and `x-ratelimit-remaining-minute`. No `x-ratelimit-*-month`, no `x-credit-cost`. Research open question 5 answered: no.

### Claude's Discretion
- Module layout of the V2 client (rewrite `solaredge_api.py` vs new module) and model changes (`BatteryData` fields, drop `PowerFlow`/`SiteOverview`).
- Charge/discharge idle threshold.
- Battery cache file location/format and when it is invalidated (e.g. delete file to re-detect).
- How the interim cadence is implemented (D-07), as long as it stays within budget and is easy for Phase 13 to replace.
- Single retry on 5xx/timeout details; 403/400 handling (no loop, log and keep cached values).

</decisions>

<specifics>
## Specific Ideas

- The owner wants real numbers back on the display as soon as Phase 12 is done, without waiting for Phase 13.
- Serial numbers and site ID must not appear in logs or planning docs (same masking rule as before).

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### V2 API
- `.planning/research/V2-API.md` §1 "Endpoint mapping V1 to V2": endpoints, fields, units, window limits, V1→V2 battery mapping
- `.planning/research/V2-API.md` §5 "Minimal call plan": cadence and budget (note D-10: history is 2 calls/day for this site)
- `.planning/research/V2-API.md` §6 "Pitfalls" items 5, 6, 8, 9, 10, 11, 12: error handling, timezone, nulls/units, inventory default, latency, lost V1 features, meter-keyed responses
- `.planning/research/V2-API.md` §7 "Open questions" 5–7 (answered by D-08..D-12)

### Requirements
- `.planning/REQUIREMENTS.md`: API-01..API-05
- `.planning/ROADMAP.md` Phase 12: success criteria 1–5

### Prior phase
- `.planning/phases/11-oauth-login-token-store/11-CONTEXT.md`: token store decisions, login state, D-15 (API key removal deferred to here)
- `token_store.py`: `TokenStore.authorized_request`, `site_id`, `LoginRequired`, `TransientAuthError`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `token_store.TokenStore.authorized_request(method, url, **kwargs)`: Bearer auth, 401 → refresh once + retry once, plain session without retry adapter.
- `screens/battery.py`: layout stays (bar + "Lädt/Entlädt mit X kW" legend, 2-column grid Temperatur / Verfügbar); only data source changes.
- `screens/history.py`: 14-bar layout stays; `EnergyHistory(dates, production, consumption)` model fits both new sources.
- `screens/production.py` / `screens/consumption.py`: breakdowns currently derive "In Akku"/"Von Akku" as remainders; overview now has `toStorage` / `fromStorage` / `fromPv` directly.
- `screens/forecast.py` uses `actual_production` from EnergyDetails; keep feeding it from overview `production.total`.

### Established Patterns
- API methods return `None` on failure; main loop falls back to cached data (`last_successful_*`).
- Frozen dataclasses in `models.py`; German display labels, English code/logs; site id masked in logs.
- `main.py` lazy `init_site_clients()` after login; `has_battery` decides whether the Hausakku screen is in the rotation.

### Integration Points
- `solaredge_api.SolarEdgeAPI(api_key, site_id)` with urllib3 Retry → replace with a V2 client built on `TokenStore`.
- `main.fetch_data()` currently calls `get_current_power_flow()` + `get_storage_data()`; rewrite around overview / storage telemetry / storage status / history with their own cadences.
- `config.py`: drop `SOLAREDGE_API_KEY` requirement; poll interval / sleep defaults per D-07.
- Tests: `tests/` stdlib unittest; V2 responses should be canned fixtures shaped like D-08..D-11 (no live calls in tests).

</code_context>

<deferred>
## Deferred Ideas

None. The discussion stayed within the phase scope.

</deferred>

---

*Phase: 12-v2-data-client-screens*
*Context gathered: 2026-11-05*
