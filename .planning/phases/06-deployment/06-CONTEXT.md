# Phase 6: Deployment - Context

**Gathered:** 2026-02-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy the SolarEdge monitor application to a Raspberry Pi Zero WH via git pull + systemd. Includes systemd service file, deploy script, install script, setup documentation (README), and proper .gitignore. The Pi already has Raspberry Pi OS and SSH access.

</domain>

<decisions>
## Implementation Decisions

### Update workflow
- Single deploy script (`deploy.sh`) lives on the Pi in the repo root
- SSH into Pi, run `./deploy.sh` to update
- Script runs `git pull`, always reinstalls deps (`pip install -r requirements.txt`), restarts systemd service
- Verbose output: print each step as it happens (Pulling... Installing deps... Restarting...)

### systemd behavior
- Restart policy: always restart (on any exit — crash, error, or clean)
- Auto-start on boot: enabled (`systemctl enable`)
- Runs as the `pi` user (has GPIO/SPI access by default)
- Logging: both rotating file log AND systemd journal (keep existing dual logging)

### Initial Pi setup
- Assumes Raspberry Pi OS already installed with SSH access
- Guide starts from SPI enable and application setup
- Both an install script (`install.sh`) and step-by-step README
- `install.sh` automates: SPI check, venv creation, pip install, .env setup prompt, systemd service install + enable
- Application cloned to `/home/pi/solaredge-monitor`
- Documentation in English

### Repository structure
- systemd service file (`solaredge-monitor.service`) committed to repo root — install script copies to `/etc/systemd/system/`
- `deploy.sh` and `install.sh` in repo root
- Full README.md: project description, what it does, hardware list, setup guide, usage instructions
- .gitignore: standard Python + project exclusions (.env, __pycache__, venv/, debug/, *.log, .planning/)

### Claude's Discretion
- Restart delay between systemd restart attempts
- Exact install.sh error handling and idempotency approach
- README structure and section ordering
- Whether to include a hardware photo placeholder or skip it

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for Raspberry Pi deployment.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 06-deployment*
*Context gathered: 2026-02-06*
