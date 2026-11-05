# SolarEdge Monitoring API V2: Migration Research

**Milestone:** v2.0 SolarEdge API V2
**Researched:** 2026-11-05
**Overall confidence:** HIGH for endpoints, auth and quota (official docs and the official OpenAPI spec v2.2.0 were read directly). MEDIUM/LOW for a few behaviours the docs don't cover; these are listed under Open questions.

**Primary sources.** The official developer docs are at `api-docs.solaredge.com`, a Stoplight workspace called `se-api`. The pages there are JS-rendered, so they were read as raw markdown and YAML through the Stoplight API:
- Developer Platform articles (Authentication, Tiers and Rate Limits, Homeowner Guide, Migrating V1 to V2, Polling Strategy, FAQ)
- Basic Monitoring OpenAPI spec **v2.2.0**, branch "next 11/2026", updated 2026-11-05. Export: `https://stoplight.io/api/v1/projects/se-api/basic-monitoring-api/nodes/basic-monitoring-api_8.yaml?fromExportButton=true&snapshotType=http_service&deref=optimizedBundle`
- Basic Monitoring Changelog (2.1.0 October 2026, 2.2.0 November 2026)

Confidence tags used below: **[H]** official doc or spec. **[M]** official doc plus community agreement, or an official doc that is ambiguous. **[L]** community or GitHub only.

---

## Summary

- **Base URL** `https://monitoringapi.solaredge.com/v2`. Paths are plural (`/sites/{id}/...`). Auth uses the header `Authorization: Bearer <access_token>`. V1 was shut down on 2026-11-03 and V1 keys do not work on V2. [H]
- **One call covers 4 of the 5 "today" screens.** `GET /sites/{id}/overview` with no params returns today from local midnight until now: `production.total`, `production.toGrid` (Einspeisung), `production.toSelfConsumption`, `consumption.total` (Verbrauch) and `consumption.fromGrid` (Bezug). Units come in `unit` (WH/KWH/MWH/GWH). [H]
- **No live power flow on the Free tier.** `/sites/{id}/power-flow` belongs to the Advanced Monitoring API, which needs Business Pro ($1,000/month) or Enterprise. Lower tiers get `403`. The free substitutes are 15-minute averages from `/sites/{id}/power`, `/meters/telemetry` and `/storage/telemetry`. [H]
- **Free tier:** 2,000 credits/month, 10 calls/minute, 1 app, no overage. Every operation costs 1 credit. Credits and CPM are counted **per developer account**. The month is the **billing-cycle anniversary** (the day the account was created), not the calendar month. [H]
- **OAuth Site Access:** authorize at `https://connect.solaredge.com/authorize`. Token and refresh go to `POST https://monitoringapi.solaredge.com/v2/oauth2/token` with a **JSON body** (not form-encoded) that includes `client_id` and `client_secret`. **No PKCE.** Access token lasts 7200 s (2 h). The refresh token **rotates** (the old one is invalid immediately) and **expires after 14 days unused**. The grant itself lasts up to `access_duration=24` months. [H]
- **Battery:** `GET /sites/{id}/storage/telemetry` (DEVICE_DATA) returns `stateOfEnergy` (%), `remainingEnergy` (Wh), `chargePower`/`dischargePower` (W) and energies, keyed by battery serial. Internal temperature and state code come from a separate call, `GET /sites/{id}/storage/status`. [H]
- **Inventory:** `GET /sites/{id}/devices?types=BATTERY` (repeat `types` for more). Without `types` it returns **inverters only**, which would silently hide the battery. [H]
- **History screens (14 days):** `GET /sites/{id}/meters/telemetry?resolution=DAY&from=...&to=...` returns `productionEnergy` and `consumptionEnergy` (Wh) per day, keyed by meter serial. DAY allows up to 1 month per call. [H]
- **No monthly-quota header for tier keys.** Only `x-ratelimit-limit-minute`/`x-ratelimit-remaining-minute` are sent. A **local credit counter is mandatory**. When the credit limit is hit you get `429` with `detail: "Monthly credit limit reached."` and no `retry-after`. [H] (the monthly headers exist only for "keys with a monthly limit"; see Open questions)
- **Recommended budget:** about 1,250–1,500 credits/month, using the plan in the "Minimal call plan" section. About 26 overview polls/day plus about 13 battery polls/day plus 1 history call/day plus about 7 token refreshes. Refreshes may or may not cost credits; this is undocumented.

---

## 1. Endpoint mapping V1 to V2

Base: `https://monitoringapi.solaredge.com/v2`. Header: `Authorization: Bearer {access_token}`.

### Parameter conventions (apply everywhere)
- `from` and `to` are ISO-8601 date-times **with zone** (`Z` or `+01:00`). A naive local time gets **`400`**. [H] (changelog 2.1.0, spec)
- **Returned timestamps are in site local time with UTC offset**, e.g. `2026-10-01T09:00:00+02:00`. [H]
- If `from`/`to` are omitted, most endpoints default to **local midnight today until now (site time)**. [H] (spec, per operation)
- `resolution` takes `QUARTER_HOUR | HOUR | DAY | WEEK | MONTH | YEAR | TOTAL`. QUARTER_HOUR is the minimum. A value's timestamp marks the **start** of its bucket. [H]
- **Window limits** (energy/telemetry endpoints): QUARTER_HOUR ≤ 12 h, HOUR ≤ 24 h, DAY ≤ 1 month, WEEK ≤ 1 year, MONTH ≤ 3 years, YEAR unlimited, TOTAL gives one value. Exceeding a limit gets `400`. [H]
- From **2026-12-01**, QUARTER_HOUR/HOUR data is only available for the last 1 year. [H] This doesn't matter for this project.
- Time-series `value` can be `null` (no data). `0` means the device reported zero. [H] (changelog 2.1.0)

### Mapping table

| V1 (current code) | V2 replacement | Scope | Key response fields and units | Conf |
|---|---|---|---|---|
| `GET /site/{id}/overview` (lifetime/year/month/day) | `GET /sites/{id}/overview` for today. For lifetime use `GET /sites/{id}/lifetime-energy`, which returns `{energy, unit:"WH", lastUpdateTime}`. For year/month use `GET /sites/{id}/energy?resolution=YEAR|MONTH`. | SITE_DATA | Overview: `{siteId, production:{total, unit, toSelfConsumption, toStorage, toGrid}, consumption:{total, unit, fromPv, fromStorage, fromGrid}}`. `unit` ∈ WH/KWH/MWH/GWH. The `to*`/`from*` fields and `consumption.total` are **nullable**. **No `currentPower`, no `lastUpdateTime`** in the overview. | H |
| `GET /site/{id}/energyDetails` (today, meters Purchased/FeedIn/Production/SelfConsumption/Consumption) | **`GET /sites/{id}/overview`** (no params gives today). Alternative: `GET /sites/{id}/meters/telemetry?resolution=DAY` | SITE_DATA (overview) / DEVICE_DATA (meters) | Overview field mapping: production = `production.total`, self_consumption = `production.toSelfConsumption`, feed_in = `production.toGrid`, consumption = `consumption.total`, purchased = `consumption.fromGrid`. Convert using `unit`. | H (fields), M (equivalence to V1 meter values; see Open questions) |
| `GET /site/{id}/energyDetails?timeUnit=DAY` (14-day history) | `GET /sites/{id}/meters/telemetry?resolution=DAY&from=<local midnight −13 d, with offset>&to=<now, with offset>` | DEVICE_DATA | `{period:{from,to}, resolution, meters:{<SN>:{productionEnergy:{unit:"WH", values:[{timestamp, value}]}, consumptionEnergy:{...}, importEnergy:{...}, exportEnergy:{...}}}}`. DAY returns energy metrics only. Window ≤ 1 month. | H |
| (alt. for production-only history) | `GET /sites/{id}/energy?resolution=DAY&unit=WH` | SITE_DATA | Measurements envelope `{period, unit, resolution, values:[{timestamp, value}]}`. **PV production only, no consumption.** | H |
| `GET /site/{id}/currentPowerFlow` | `GET /sites/{id}/power-flow` (Advanced, **Business Pro/Enterprise only, 403 on Free**). Free substitutes: `GET /sites/{id}/power` (PV W, 15-min avg), `/meters/telemetry` (QUARTER_HOUR: productionPower, consumptionPower, importPower, exportPower in W), `/storage/telemetry` (charge/dischargePower, stateOfEnergy) | n/a / SITE_DATA / DEVICE_DATA | `/power`: Measurements, `unit` W/KW/MW (default W), resolution QUARTER_HOUR or HOUR only. **Off-grid detection (`connections[]`) has no Basic-API equivalent.** | H |
| `GET /site/{id}/inventory` → `Inventory.batteries[]` | `GET /sites/{id}/devices?types=BATTERY` (repeat `types=` for more, e.g. `&types=METER`) | DEVICE_DATA | **JSON array** of `{type, serialNumber, manufacturer, model, partNumber, createdAt, firmwareVersion, connectedTo, connectedToName, parent, active, nameplate, name, form, communicationType, firmware, connectedOptimizers}`. `active:false` = removed/replaced (since 2.2.0). | H |
| `GET /site/{id}/storageData` (internalTemp, fullPackEnergyAvailable, power) | `GET /sites/{id}/storage/telemetry` (+ `GET /sites/{id}/storage/status` for temperature) | DEVICE_DATA | Telemetry: `{period, resolution, storage:{<SN>:{chargePower:{unit:"W",values}, dischargePower, stateOfEnergy:{unit:"PERCENTAGE",values}, chargeEnergy (Wh), dischargeEnergy (Wh), remainingEnergy (Wh)}}}`. QUARTER_HOUR/HOUR give all 6 metrics. DAY and coarser give energies only. `chargePower`/`dischargePower` are always positive. Status: `storage:{<SN>:{batteryState:{values}, internalTemperature:{unit:"CELSIUS", values}}}`, QUARTER_HOUR only, ≤ 12 h, `batteryState` code is opaque (no published mapping). | H |

**V1 to V2 battery field mapping** [H] (Migrating V1 to V2):
- `chargeLevel`/SoC: `stateOfEnergy` (% of **usable** capacity)
- `fullPackEnergyAvailable`: compute `remainingEnergy / (stateOfEnergy/100)`. The current code wrongly shows `fullPackEnergyAvailable` as "available energy". In V2, "available now" is just `remainingEnergy`.
- `power`: `chargePower − dischargePower` (both positive in V2)
- status "Charge/Discharge/Idle": derive it client-side from charge vs discharge power with a threshold. V1's textual status does not exist in V2.
- `internalTemp`: `storage/status` → `internalTemperature` (extra call)

Sources: Migrating V1 to V2 https://api-docs.solaredge.com/docs/developer-platform/mxj41549n0nxk-migrating-from-v1-to-v2 ; Site Overview https://api-docs.solaredge.com/docs/basic-monitoring-api/sl8clhypye68r-site-overview ; Site Meter Telemetry https://api-docs.solaredge.com/docs/basic-monitoring-api/gnpjkjq2e43cg-site-meter-telemetry ; Site Storage Telemetry https://api-docs.solaredge.com/docs/basic-monitoring-api/rnu94oh5tn7kb-site-storage-telemetry ; Site Storage Status https://api-docs.solaredge.com/docs/basic-monitoring-api/ngn4sf6oc7cmi-site-storage-status ; Site Inventory https://api-docs.solaredge.com/docs/basic-monitoring-api/8uqvgujkzr1q5-site-inventory ; Site Power https://api-docs.solaredge.com/docs/basic-monitoring-api/eaixa0sttt93t-site-power ; Changelog https://api-docs.solaredge.com/docs/basic-monitoring-api/5uoeb2xfqt68z-changelog

---

## 2. OAuth2 flow (Site Access)

| Item | Value | Conf / Source |
|---|---|---|
| Authorize URL | `https://connect.solaredge.com/authorize` | H (spec `securitySchemes.OAuth`, Authentication page) |
| Authorize params | `client_id` (required). The Homeowner guide also sends `scope=SITE_DATA%20DEVICE_DATA`, `redirect_uri=...`, `state=...` and `access_duration=24` (months, max 24). `external_id` is optional, for correlation. `response_type` is **not** shown in any official example. | H for client_id/access_duration/external_id. M for scope/redirect_uri/state being honoured (they appear only in the homeowner example). |
| Callback | `?code=...&site_id=...` (+ `external_id` if sent, + `state` per the Homeowner guide). On failure: `?error=...` | H. **Conflict on `state`:** two community integrations (kriskomp, trooperthorn) say SolarEdge does **not** return `state` (as of 2026-10-16) [L]. |
| Token URL | `POST https://monitoringapi.solaredge.com/v2/oauth2/token`, `Content-Type: application/json` | H |
| Code exchange body | `{"grant_type":"authorization_code","code":"...","client_id":"...","client_secret":"..."}`. The Homeowner guide also adds `"redirect_uri"`. | H |
| Refresh body | `{"grant_type":"refresh_token","refresh_token":"...","client_id":"...","client_secret":"..."}` | H |
| Token response | `{"access_token","token_type":"Bearer","expires_in":7200,"refresh_token"}`. No `scope` field shown. | H |
| PKCE | **Not supported** ("Not at launch", FAQ) | H |
| Access token lifetime | 2 h (`expires_in: 7200`) | H |
| Refresh token | **Rotates on every refresh.** The old one "becomes invalid". It **expires after 14 days without use**, and each refresh restarts the 14 days. | H (Authentication + Homeowner guide). Community READMEs say "30 days" [L]. Design for 14. |
| Grant lifetime | `access_duration` up to 24 months, then re-consent (`401 credential_expired`) | H |
| Reusing an old refresh token | Docs say only "becomes invalid". The exact error is **not documented**. Expect HTTP 400 `{"error":"invalid_request"|"invalid_grant", ...}`, since token-endpoint errors are RFC 6749 style at 400 per the docs. | H that it fails, **not found** for the exact error code |
| Revoke | `POST https://monitoringapi.solaredge.com/v2/oauth2/revoke-token`, body `{"token":"..."}`. Revoking a refresh token invalidates all access tokens issued from it. | H |
| Client-secret rotation | The old secret dies instantly. Existing access tokens live until TTL. **Refresh tokens then only work with the new secret.** | H (Applications page) |
| Consent to own site | Sign in at connect.solaredge.com with the **homeowner mySolarEdge credentials**, pick the site if there are several, then Approve. "You consent to yourself" is the official path for homeowners. Fleet API keys are not available to homeowners. A personal-access-token mode is "being considered", not shipped. | H (Homeowner guide, FAQ). A community claim that "any developer account can generate an X-API-Key" [L] contradicts the official homeowner guide; do not rely on it. |
| Where to see grants and revoke | Docs say the "site owner revokes grant", but **not found** where the homeowner does this in the UI | not found |
| Code lifetime | "one-use". Lifetime **not documented** (community: "short") | not found |

**Recommended Mac login script** (based on the above):
1. Start an HTTP listener on `localhost:8765`. Open `https://connect.solaredge.com/authorize?client_id=…&redirect_uri=http://localhost:8765/callback&scope=SITE_DATA%20DEVICE_DATA&state=<random>&access_duration=24`.
2. On callback, check `state` **only if present** (it may be missing, see the conflict above). Read `code` and `site_id`.
3. POST the JSON body to the token URL immediately. Include `redirect_uri`, which is harmless.
4. Write `{access_token, refresh_token, expires_at (absolute UTC epoch), site_id, obtained_at}` to the token file and `scp` it to the Pi (0600).
5. **The Mac must never refresh again.** Whoever refreshes first invalidates the other side's refresh token.

Sources: Authentication https://api-docs.solaredge.com/docs/developer-platform/g09jmvp5t2cok-authentication ; Homeowner and Self-Access Guide https://api-docs.solaredge.com/docs/developer-platform/df8kx5j4z9vi0-homeowner-and-self-access-guide ; Support and FAQ https://api-docs.solaredge.com/docs/developer-platform/uvpdtwvzb3wj4-support-and-faq ; Applications https://api-docs.solaredge.com/docs/developer-platform/z3lbt82nwzxe4-applications

---

## 3. Quota and rate limits

| Item | Value | Conf |
|---|---|---|
| Free tier | $0, **2,000 credits/month**, **10 CPM**, 1 app, auto-provisioned at sign-up, **no overage possible** | H |
| Paid tiers | Business Starter $100 (20k, 25 CPM), Growth $400 (100k, 50 CPM), Pro $1,000 (400k, 100 CPM), Enterprise custom | H |
| Cost per call | 1 credit for every operation (`x-credit-cost: 1` in the spec). May change for heavier endpoints in future. | H |
| Scope of the limit | **Per developer account.** All apps share the CPM bucket and the credit pool. | H |
| Reset | Monthly on the **billing-cycle anniversary** (account creation date for Free), no rollover. **Look up the anniversary day in the console Usage tab.** | H |
| CPM window | Fixed clock-minute window | H |
| Headers | `x-ratelimit-limit-minute`, `x-ratelimit-remaining-minute` (tier keys). `x-ratelimit-limit-month`/`remaining-month`/`limit-second`/`remaining-second` only for "keys with a monthly limit". `retry-after` (seconds) on CPM 429. | H (spec). M on whether a Free OAuth token ever gets the month headers. Community: "There is no monthly counter" [L]. |
| CPM exceeded | `429`, body `{"message":"API rate limit exceeded","request_id":...}`, `x-ratelimit-remaining-minute: 0`, `retry-after` present | H |
| Credits exhausted | `429`, `detail: "Monthly credit limit reached."`, `x-ratelimit-remaining-minute > 0`, **no `retry-after`**, blocked until the next cycle. Route on `x-ratelimit-remaining-minute`. | H |
| Do token refresh calls cost credits? | **Not found.** Docs list credit costs for API operations only. `/oauth2/token` has no `x-credit-cost`. Budget for them anyway (assume 1 each). | not found |
| Do failed calls (4xx/5xx) cost credits? | **Not found.** Assume yes. | not found |
| Usage visibility | Console Usage tab: daily credit consumption plus latest-call timestamp, "near-real-time" | H |

Sources: Tiers and Rate Limits https://api-docs.solaredge.com/docs/developer-platform/pwh8p4k2wtajh-tiers-and-rate-limits ; Authentication (Errors) ; spec `429` response on every operation; Getting Started https://api-docs.solaredge.com/docs/developer-platform/3dvsxljtyueo1-getting-started

---

## 4. Power-flow availability and plan tiers

- **Live power flow is not available on Free.** `GET /sites/{id}/power-flow` and `POST` (start live session) are in the **Advanced Monitoring API**: "require Business Pro or Enterprise. Calls from a lower tier return `403`" (`403 tier_insufficient`). [H] (Tiers, Authentication, Migrating, Homeowner guide: "overkill for a home dashboard")
- Free substitutes, all Basic API and allowed on Free:
  - Latest 15-min average PV power: `GET /sites/{id}/power?from=<now-30min>&to=<now>` (W). Calculated from inverter output adjusted by battery charge/discharge. [H]
  - Latest 15-min import/export/consumption power: `GET /sites/{id}/meters/telemetry` at QUARTER_HOUR. [H]
  - Battery SoC and power: `GET /sites/{id}/storage/telemetry` at QUARTER_HOUR. [H]
- **"Choose Your Plan" step in the portal:** I could not see the portal UI. Per the docs, **Free is auto-provisioned at sign-up** (no card). Paid tiers are bought via the SolarEdge Store from the console's Billing area. The docs say the **portal and store prices are authoritative** if they differ from the docs. **Owner should confirm in the console that the account shows Free / 2,000 credits / 10 CPM and note the cycle anniversary date.** [H for docs, unverified for the actual UI]

---

## 5. Minimal call plan (target ≤ ~65/day; 2,000/31 = 64.5)

Screens and their data sources:

| Screen | Source call | Refresh cadence |
|---|---|---|
| Produktion, Verbrauch, Einspeisung, Bezug (+ self-consumption) | `GET /sites/{id}/overview` (no params gives today, local midnight to now) | every 30 min, 07:00–20:00 |
| Hausakku (SoC, power, status, remaining kWh) | `GET /sites/{id}/storage/telemetry?resolution=QUARTER_HOUR&from=<now-1h, with offset>&to=<now, with offset>`. Take the last non-null value per metric. | every 60 min (or alternate with overview) |
| Hausakku temperature | `GET /sites/{id}/storage/status` (≤ 12 h window) | **drop it, or fetch 1–2×/day** |
| Verlauf Produktion/Verbrauch (14 d) | `GET /sites/{id}/meters/telemetry?resolution=DAY&from=<local midnight −13 d>&to=<now>` | once/day (e.g. first daylight poll). Today's bar can be patched from overview. |
| Battery detection | `GET /sites/{id}/devices?types=BATTERY` | **once, then persist the result to disk.** Do not repeat on each service restart. |
| Token refresh | `POST /v2/oauth2/token` | only when `expires_at − 5 min` has passed and a call is due. That's about 7/day during 13 daylight hours, plus 1 in the morning. |

**Budget (31-day month):**
- Overview: 27 polls/day (07:00, 07:30 … 20:00) = 837
- Storage telemetry hourly: 14/day = 434
- History: 1/day = 31
- Token refresh: about 7–8/day = about 240 (if they cost credits)
- Inventory: about 1 total
- **Total ≈ 1,543** (about 1,300 if refreshes are free). That leaves about 450 credits of headroom for restarts, retries and debugging.
- Night: one optional refresh around midnight is **not** needed. One refresh per day keeps the 14-day window alive. Do **not** refresh while asleep.

**Combined alternative (fewer calls, more parsing):** `GET /sites/{id}/meters/telemetry?resolution=HOUR` from local midnight (≤ 24 h) returns hourly production, consumption, import and export energy **and** power. Summing gives today's totals and the last hour gives approximate current power. This could replace overview, but overview is simpler and is the documented equivalent. Keep this as a fallback.

**Hard safety rules:**
- Persist a local counter keyed by billing cycle: (`cycle_start`, `used`). Increment it **before** each request, including refreshes and retries. Stop non-essential calls at about 1,800.
- Remove the blanket urllib3 retry on 429/5xx. Each retry may cost a credit, and a credit-limit 429 never recovers within the month. At most 1 retry, and only on 5xx/timeouts.
- Debug or dev runs on the Mac use the **same account pool**. Count them, or use canned fixtures.

---

## 6. Pitfalls

1. **Refresh-token rotation and SD card or crash.** The old refresh token dies the moment the server issues a new one. If the Pi crashes or loses power between receiving the response and persisting it, the token chain is lost and you must log in again on the Mac. Mitigation: write the new pair **first** (tmp file, `flush`, `os.fsync`, `os.replace`, then fsync the directory), mode 0600, before using the new access token. Writes are only about 10/day, so SD wear is negligible. [H for rotation, design advice]
2. **Two refreshers race.** If the Mac script, a debug run, or two Pi processes ever refresh the same token, one side ends up with an invalid token. Only the Pi service may refresh. Debug mode on the Mac must use its own throw-away login, and with a 1-app limit that is still the same app and grant. Use a file lock (`fcntl.flock`) around refresh-and-persist. [design, from H facts]
3. **14-day idle expiry.** A Pi that is powered off or offline for more than 14 days needs a new Mac login. The display must show a clear "Login nötig" state. Don't refresh more often than needed, but ensure at least 1/day while running. [H]
4. **24-month grant expiry.** Use `access_duration=24`. Store `granted_at`, and warn on the display or in the log about 30 days before expiry. The error is `401 credential_expired`. [H]
5. **401 vs 403 vs 400 handling:**
   - API `401`: access token expired (`token_expired`) leads to one refresh and one retry. Revoked, or `credential_expired`, needs re-login. [H]
   - API `403`: `site_not_authorized`, `insufficient_scope` (grant lacks DEVICE_DATA) or `tier_insufficient` (e.g. power-flow). These are **not fixable by refreshing**; do not loop. [H]
   - Token endpoint `400` `invalid_request`/`invalid_client` (or a reused or expired refresh token) means re-login is needed; don't retry. [H]
   - Body formats differ: 400/403/404 are RFC 7807 `application/problem+json`. 401/429 are gateway JSON (`message`/`request_id` or `error`/`error_description`). [H]
6. **Timezone.** Always send aware datetimes (e.g. `datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds")`), because naive ones get 400. Responses carry the **site's** offset. Parse with `datetime.fromisoformat` (Python 3.9 can't parse a trailing `Z`; replace it with `+00:00`). Bucket the 14-day history on the **local date part** of `timestamp`. Defaults ("midnight today") are site-local, which is right for this project. DST: since 2.2.0 both repeated-hour readings are returned. [H]
7. **Clock skew and no RTC on the Pi Zero.** On boot before NTP sync, `now()` can be wrong. That gives bad `from`/`to` (400 or wrong windows) and wrong `expires_at` handling. Mitigations: order the systemd unit `After=time-sync.target` + `Wants=time-sync.target` (and enable `systemd-time-wait-sync`). Store `expires_at` as absolute UTC but **also** treat any 401 as "refresh once". Prefer omitting `from`/`to` (server-side "today") where possible. [design]
8. **Overview nulls and units.** `consumption.total`, `fromGrid`, `toGrid` etc. are nullable, so treat null as 0 only for display. `unit` may be KWH/MWH, so always convert using it. The Homeowner guide sample code uses `units` (plural) but the spec says `unit`. Trust the spec. [H]
9. **Inventory default.** `/devices` without `types` returns only inverters, so `has_battery` would always be False. [H]
10. **Data latency.** Backend aggregates refresh about every 15 min. The newest QUARTER_HOUR bucket may be partial or `null`, so take the last **non-null** value. Polling more often than every 15 min wastes credits. [H]
11. **Features lost vs V1:** no live power flow, no off-grid detection, and no textual battery status (derive it). V1 `fullPackEnergyAvailable` is not directly available (compute it). The `PowerFlow` model and `off_grid` must be dropped or derived. [H]
12. **Meter-keyed responses.** Telemetry is a map `{serial: metrics}`. A site can have several meters, plus calculated virtual consumption/import/export when no meter exists (changelog 2.2.0). How to combine several entries (sum vs pick) is **undocumented**. Verify against the real response. [M]
13. **Token endpoint is JSON, not form-encoded.** Standard OAuth libraries (requests-oauthlib) send `application/x-www-form-urlencoded` and client_secret via Basic auth. Use plain `requests.post(json=...)`. Whether form encoding is also accepted: not found. [H for JSON]
14. **Secret rotation.** If the owner regenerates the Client Secret in the console, the Pi's refresh tokens stop working until `.env` gets the new secret. [H]
15. **The app counts against "Max apps = 1".** Deleting the app revokes all site authorizations. [H]

---

## 7. Open questions (verify during implementation)

1. **Does `/v2/oauth2/token` (refresh) consume credits?** Not documented. Check the console Usage tab after a day with known call counts.
2. **Is `state` echoed back on the callback?** The official Homeowner guide says yes. Two community projects say no (2026-10). The Mac script must tolerate both.
3. **Exact error for reusing a rotated refresh token, or one after 14 days idle** (`invalid_request` vs `invalid_grant`). Not documented. Treat any 400 from the token endpoint as "re-login needed".
4. **Refresh-token idle lifetime: 14 days (official) or 30 days (community)?** Design for 14.
5. **Does a Free-tier OAuth token receive `x-ratelimit-*-month` headers?** The spec is ambiguous; the community says no. Log all `x-ratelimit-*` headers on the first live calls.
6. **Does overview `production.toGrid` / `consumption.fromGrid` match the V1 FeedIn/Purchased meter values for this site** (battery plus possibly off-grid setup)? Compare one day against monitoring.solaredge.com.
7. **Meter telemetry shape for this site:** how many meter serials, and whether consumption is a calculated virtual entry. Inspect one real response before writing the parser.
8. **Billing-cycle anniversary date** of the developer account (from the console), needed for the local counter reset.
9. **Authorization code lifetime** is undocumented. Exchange it immediately in the Mac script.
10. **How the homeowner revokes or views the grant** (UI location). Not found in the docs.
11. **Whether failed requests (401/403/429) consume credits.** Not documented.

---

## Sources

Official (HIGH):
- Authentication: https://api-docs.solaredge.com/docs/developer-platform/g09jmvp5t2cok-authentication
- Tiers and Rate Limits: https://api-docs.solaredge.com/docs/developer-platform/pwh8p4k2wtajh-tiers-and-rate-limits
- Homeowner and Self-Access Guide: https://api-docs.solaredge.com/docs/developer-platform/df8kx5j4z9vi0-homeowner-and-self-access-guide
- Migrating from V1 to V2: https://api-docs.solaredge.com/docs/developer-platform/mxj41549n0nxk-migrating-from-v1-to-v2
- Aggregation and Polling Strategy: https://api-docs.solaredge.com/docs/developer-platform/pif9q8f76oz2d-aggregation-and-polling-strategy
- Support and FAQ: https://api-docs.solaredge.com/docs/developer-platform/uvpdtwvzb3wj4-support-and-faq
- Applications: https://api-docs.solaredge.com/docs/developer-platform/z3lbt82nwzxe4-applications
- Migrating from Site API Keys to OAuth: https://api-docs.solaredge.com/docs/developer-platform/6m1ly9bdp9egs-migrating-from-site-api-keys-to-o-auth
- Basic Monitoring Changelog (2.1.0, 2.2.0): https://api-docs.solaredge.com/docs/basic-monitoring-api/5uoeb2xfqt68z-changelog
- Basic Monitoring OpenAPI 2.2.0 (export): https://stoplight.io/api/v1/projects/se-api/basic-monitoring-api/nodes/basic-monitoring-api_8.yaml?fromExportButton=true&snapshotType=http_service&deref=optimizedBundle
- Operation pages: Site Overview https://api-docs.solaredge.com/docs/basic-monitoring-api/sl8clhypye68r-site-overview · Site Power https://api-docs.solaredge.com/docs/basic-monitoring-api/eaixa0sttt93t-site-power · Site Energy https://api-docs.solaredge.com/docs/basic-monitoring-api/jauqhott7zjpo-site-energy · Site Meter Telemetry https://api-docs.solaredge.com/docs/basic-monitoring-api/gnpjkjq2e43cg-site-meter-telemetry · Site Storage Telemetry https://api-docs.solaredge.com/docs/basic-monitoring-api/rnu94oh5tn7kb-site-storage-telemetry · Site Storage Status https://api-docs.solaredge.com/docs/basic-monitoring-api/ngn4sf6oc7cmi-site-storage-status · Site Inventory https://api-docs.solaredge.com/docs/basic-monitoring-api/8uqvgujkzr1q5-site-inventory · Site Lifetime Energy https://api-docs.solaredge.com/docs/basic-monitoring-api/3lvw5qsrhtcbh-site-lifetime-energy
- Advanced Monitoring (power-flow): https://api-docs.solaredge.com/docs/advanced-monitoring/xqw20vdqt3xv8-site-power-flow

Community / secondary (LOW unless corroborated):
- trooperthorn/ha_int_solaredge: https://github.com/trooperthorn/ha_int_solaredge (refresh 30 d claim, 24-month grant, power-flow paid)
- kriskomp/ha-solaredge-v2: https://github.com/kriskomp/ha-solaredge-v2 (`state` not returned, 10 CPM, 429 "Monthly credit limit reached", no monthly counter)
- aarondrabeck/ha-solaredge-api-connector: https://github.com/aarondrabeck/ha-solaredge-api-connector
- domoticz PR #7028: https://github.com/domoticz/domoticz/pull/7028 (rotation, 400/401 on refresh means re-auth, Retry-After)
- EVWorth/solaredge issue #122 and PR #123: https://github.com/EVWorth/solaredge/issues/122 , https://github.com/EVWorth/solaredge/pull/123 (claim that any developer account gets an X-API-Key, which contradicts the official homeowner guide)
