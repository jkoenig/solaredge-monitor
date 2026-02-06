---
phase: 06-deployment
plan: 01
subsystem: infra
tags: [systemd, raspberry-pi, bash, deployment, automation]

# Dependency graph
requires:
  - phase: 05-operations
    provides: Main loop with logging and lifecycle management
provides:
  - systemd service file with auto-restart and journal logging
  - Idempotent install.sh for full Pi setup (SPI, venv, deps, .env, systemd)
  - deploy.sh for code updates and service restarts
affects: [06-deployment (future plans in this phase)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "systemd service with Restart=always and rate limiting"
    - "Idempotent setup scripts with conditional flags"
    - "Root user detection and refusal pattern"

key-files:
  created:
    - solaredge-monitor.service
    - install.sh
    - deploy.sh
  modified: []

key-decisions:
  - "Restart=always for all exit codes (agreed with user in 06-RESEARCH.md)"
  - "RestartSec=10 with rate limiting (5 starts in 200s) per systemd best practices"
  - "Absolute venv path in ExecStart (no activation needed)"
  - "Journal logging via StandardOutput/StandardError (works with existing dual logging)"
  - "User=pi for GPIO/SPI access (default groups)"
  - "Idempotent install.sh checks (preserves .env, detects existing venv/SPI)"
  - "Root user refusal in both scripts (must run as pi user)"

patterns-established:
  - "SCRIPT_DIR pattern for reliable working directory"
  - "REBOOT_REQUIRED and NEEDS_ENV_CONFIG flags for conditional next-steps"
  - "Numbered progress steps [1/6] through [6/6] for visibility"
  - "Verbose deploy.sh showing git pull, pip install, systemctl restart, and status"

# Metrics
duration: 1.2min
completed: 2026-02-06
---

# Phase 6 Plan 1: Deployment Automation Summary

**systemd service with auto-restart, idempotent Pi setup script, and one-command deployment**

## Performance

- **Duration:** 1.2 min
- **Started:** 2026-02-06T19:44:29Z
- **Completed:** 2026-02-06T19:45:38Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- systemd service file with Restart=always, rate limiting, and journal logging integration
- install.sh automates full Pi provisioning (SPI enable, user groups, venv, dependencies, .env creation, systemd installation)
- deploy.sh provides single-command updates (git pull, pip install, service restart with status output)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create systemd service file** - `8c72bf6` (feat)
2. **Task 2: Create install and deploy scripts** - `67b872e` (feat)

## Files Created/Modified
- `solaredge-monitor.service` - systemd unit file with auto-restart, rate limiting, and journal logging
- `install.sh` - idempotent Pi setup script (SPI, venv, deps, .env, systemd installation) with conditional next-steps
- `deploy.sh` - update script (git pull, pip install, systemctl restart, status display)

## Decisions Made

All key decisions were pre-determined in 06-RESEARCH.md after user consultation:

1. **Restart=always**: Restart service on any exit code (not just failures)
2. **RestartSec=10 with rate limiting**: 10-second delay between restarts, max 5 starts in 200 seconds
3. **Absolute venv path**: ExecStart uses `/home/pi/solaredge-monitor/venv/bin/python3` (no activation)
4. **Journal logging**: StandardOutput=journal and StandardError=journal (integrates with existing dual logging from Phase 5)
5. **User=pi**: Service runs as pi user for GPIO/SPI access (default Raspberry Pi user groups)
6. **Idempotent install.sh**: Checks for existing venv, .env, SPI before creating/enabling
7. **Root refusal**: Both scripts refuse to run as root (must run as pi user)
8. **Conditional next-steps**: install.sh shows different instructions based on REBOOT_REQUIRED and NEEDS_ENV_CONFIG flags

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all scripts created successfully and passed syntax validation.

## User Setup Required

**Pi deployment requires manual steps.** The user will need to:

1. Copy repo to Raspberry Pi Zero WH at `/home/pi/solaredge-monitor`
2. Run `./install.sh` on Pi as pi user
3. Edit `.env` with SolarEdge API credentials
4. Reboot if SPI or user groups were modified
5. Use `./deploy.sh` for future updates

These steps are intentionally manual (not in USER-SETUP.md) as they are one-time Pi provisioning, not recurring service configuration.

## Next Phase Readiness

**Ready for Pi hardware setup.** Next plan (06-02) will provide:
- Hardware wiring guide for e-ink display connection
- Physical installation instructions
- Troubleshooting guide for common Pi/display issues

**Blockers:** None

**Concerns:** None - deployment automation complete and tested (syntax validation passed)

---
*Phase: 06-deployment*
*Completed: 2026-02-06*
