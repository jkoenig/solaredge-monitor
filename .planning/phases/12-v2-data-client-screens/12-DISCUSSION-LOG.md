# Phase 12: V2 Data Client & Screens - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md. This log keeps the alternatives that were considered.

**Date:** 2026-11-05
**Phase:** 12-v2-data-client-screens
**Areas discussed:** Akku-Anzeige, Verlauf heutiger Balken, Rollout before Phase 13, Live probe calls

Discussion held in German.

---

## Akku-Anzeige

| Option | Description | Selected |
|--------|-------------|----------|
| Temperatur 2× täglich | Keep column, fetch storage/status twice a day | ✓ |
| Ersetzen: Kapazität | Show pack size instead, no extra call | |
| Temperatur weglassen | Only "Verfügbar" column | |

| Option | Description | Selected |
|--------|-------------|----------|
| Noch gespeichert | remainingEnergy | ✓ |
| Gesamtgrösse wie bisher | pack size | |

## Verlauf: heutiger Balken

| Option | Description | Selected |
|--------|-------------|----------|
| Laufend nachführen | Patch today's bar from overview | ✓ |
| Stand vom Morgen | Keep value from daily fetch | |
| Nur 14 abgeschlossene Tage | No today bar | |

## Bis Phase 13 aufs Gerät?

| Option | Description | Selected |
|--------|-------------|----------|
| Sofort drauf, langsamer Takt | Deploy now, ~30 min daytime cadence | ✓ |
| Erst nach Phase 13 drauf | Keep "Fehler" until quota guard exists | |

## Echte Probe-Abrufe

| Option | Description | Selected |
|--------|-------------|----------|
| Ja, mach | ~5–10 credits, structure only | ✓ |
| Nein, nur nach Doku | | |

Probe results (8 calls, structure only): overview all float in WH; 2 battery devices (1 inactive); meters/telemetry DAY returns only a virtual CONSUMPTION meter → production history needs /energy?resolution=DAY; no monthly rate-limit headers.

## Claude's Discretion

V2 client module layout, model changes, idle threshold, battery cache details, interim cadence mechanism, 5xx retry details.

## Deferred Ideas

None.
