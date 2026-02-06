# Phase 5: Operations - Context

**Gathered:** 2026-02-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Production-ready operational behavior for the solar monitor: polling loop that fetches API data and cycles through display screens, time-gated sleep mode, structured logging, and graceful shutdown. No new screens, no new data sources, no deployment automation (Phase 6).

</domain>

<decisions>
## Implementation Decisions

### Screen cycling behavior
- Show all 4 screens each poll cycle, 60 seconds per screen
- Fixed order: Produktion -> Verbrauch -> Einspeisung -> Bezug
- After cycling all 4, return to Produktion and hold until next poll
- Full cycle takes 4 minutes, then ~1 minute idle showing Produktion before next poll

### Night mode & sleep behavior
- Clear display to white when entering sleep mode
- Sleep window configurable via environment variables (SOLAREDGE_SLEEP_START, SOLAREDGE_SLEEP_END), default midnight to 6 AM
- On wake: immediately fetch fresh data and start screen cycling
- Poll interval configurable via SOLAREDGE_POLL_INTERVAL env var, default 5 minutes

### Error & recovery behavior
- On API failure: keep showing last successful data (stale data displayed)
- After 3 consecutive failures (~15 min): switch to error screen indicating API is unreachable
- Keep retrying every poll interval even while showing error screen
- On first successful poll after errors: resume normal screen cycling
- On SIGTERM/SIGINT: clear display to white before exiting

### Logging & observability
- Log to both stdout and rotating log file (Pi has limited storage)
- Log rotation to keep disk usage bounded on Raspberry Pi
- INFO level (default): startup, shutdown, errors, sleep/wake transitions, each poll result (success/fail with data summary)
- DEBUG level: detailed API responses, screen renders, timing info
- Log level configurable via SOLAREDGE_LOG_LEVEL env var
- Structured JSON log format

### Claude's Discretion
- Log file location and rotation size/count
- Exact error screen design
- How to handle edge cases around sleep window boundaries (e.g., poll starts at 23:59)
- Internal threading/async approach for the poll loop

</decisions>

<specifics>
## Specific Ideas

- Raspberry Pi has limited resources — log rotation is important to avoid filling the SD card
- systemd journal will also capture stdout, so file logging is supplementary for direct access
- E-ink displays should not be refreshed too frequently — 60s per screen is appropriate

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-operations*
*Context gathered: 2026-02-06*
