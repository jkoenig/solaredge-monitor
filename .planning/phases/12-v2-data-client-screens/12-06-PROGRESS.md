# 12-06 progress (deploy checkpoint, in progress)

- 2026-11-05 19:59: owner chose "deploy now" (Task 1). Local suite 173 + 29 green, V1 gate clean.
- 20:00:27 pushed + ./deploy.sh. Service active, NRestarts=0, no Traceback.
- First round (20:00:52, before the .env fix): devices 1, overview, storage/status, storage/telemetry, energy, meters/telemetry = 6 calls, all 200. "Battery detection: 1 active of 2", history 14 days, "Poll successful".
- .battery.json: 600 pi, keys [has_battery, site_hash, version], has_battery True. Site-id occurrences in journal: 0.
- Finding: Pi .env had overrides (POLL_INTERVAL < 30, SLEEP 01-06) -> 19 h awake, ~75 calls/day. Owner approved changing the Pi .env to POLL_INTERVAL=30, SLEEP_START=20, SLEEP_END=7 (backup .env.bak-phase12). Restarted 20:02:30, service entered sleep (display cleared until 07:00).
- Note: during the sleep window the display is cleared (existing behavior), not frozen on the last values.

## Still to do (after 07:00 on 2026-11-06)
- Task 2 step 7: restart-check evidence: after wake, "Battery presence from cache: True" and no /sites/{site_id}/devices call since 20:02.
- Task 3: owner display check (steps 1-5) and steady-state hour call count <= 4 (>= 70 min after wake).
