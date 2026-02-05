# Phase 2: Configuration Foundation - Context

**Gathered:** 2026-02-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract all hardcoded credentials and configuration values into environment-based configuration with startup validation. Covers loading, validation, documentation, and .gitignore setup. Does not include the config consumers (API clients, display, operations) — those are later phases.

</domain>

<decisions>
## Implementation Decisions

### Config structure
- All env vars use `SOLAREDGE_` prefix (e.g., `SOLAREDGE_API_KEY`, `SOLAREDGE_SITE_ID`)
- Scope includes credentials AND key operational settings (poll interval, sleep hours, debug mode) — things you'd tweak per deployment
- .env.example grouped with comment sections: `# SolarEdge API`, `# Display Settings`, `# Operations`
- Single Config dataclass in Python — all settings in one place, not split by concern

### Validation behavior
- Report all missing/invalid values at once, then exit — operator fixes everything in one pass
- Credentials (API key, site ID) are required; operational settings have sensible defaults (poll interval: 5 min, sleep hours: 00:00–06:00, debug: off)
- Basic type checks beyond presence: is poll_interval a number? is debug a boolean? Catch obvious mistakes early
- Error format is a structured list:
  ```
  ERROR: Missing required configuration:
    - SOLAREDGE_API_KEY: SolarEdge API key
    - SOLAREDGE_SITE_ID: Site identifier
  ```

### Config loading approach
- Use python-dotenv to load .env files (standard library, handles edge cases)
- Real environment variables override .env file values — standard behavior, good for systemd deployments
- Look for .env in the current working directory (standard python-dotenv behavior)
- No CLI argument parsing — debug mode and all settings controlled purely via env vars

### Variable naming & documentation
- .env.example includes comments with descriptions for each variable and valid values
- Booleans use `true`/`false` format (e.g., `SOLAREDGE_DEBUG=true`)
- Sleep hours use two separate integer variables: `SOLAREDGE_SLEEP_START=0` and `SOLAREDGE_SLEEP_END=6`
- App logs loaded config at startup with secrets masked (e.g., `SOLAREDGE_API_KEY=****abcd`)

### Claude's Discretion
- Exact Config dataclass field names and types
- How python-dotenv is integrated (load_dotenv call placement)
- Internal validation implementation details
- Config module file structure

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The key principle is: a fresh Pi deployment should only need to copy `.env.example` to `.env`, fill in credentials, and the app runs with sensible defaults for everything else.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-configuration-foundation*
*Context gathered: 2026-02-05*
