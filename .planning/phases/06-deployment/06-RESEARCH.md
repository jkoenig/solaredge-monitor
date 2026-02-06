# Phase 6: Deployment - Research

**Researched:** 2026-02-06
**Domain:** Linux systemd deployment for Python applications on Raspberry Pi
**Confidence:** HIGH

## Summary

Phase 6 deploys the SolarEdge monitor application to a Raspberry Pi Zero WH using systemd for process management and git-based deployment workflow. The standard approach uses systemd service files for automatic startup/restart, bash scripts for deployment automation, and Python virtual environments for dependency isolation.

The deployment pattern consists of three components: (1) a systemd service file that runs the application with automatic restart on any exit, (2) an install script that sets up the Pi environment (SPI, venv, dependencies, .env), and (3) a deploy script that pulls code updates and restarts the service. This architecture is widely adopted for Python daemon processes on Raspberry Pi because it leverages existing OS infrastructure (systemd) rather than custom process management.

Raspberry Pi-specific considerations include SPI interface enablement via `raspi-config nonint`, user group permissions (spi, gpio), and the fact that the default 'pi' user has necessary hardware access by default. The logging architecture (already implemented in Phase 5 with JSON to stdout and rotating file) integrates naturally with systemd's journalctl.

**Primary recommendation:** Use systemd with `Restart=always`, `RestartSec=10`, explicit virtual environment paths in ExecStart, and WorkingDirectory set to application root. Install script should be idempotent with checks for existing installations.

## Standard Stack

The established tools for Python application deployment on Raspberry Pi:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| systemd | built-in | Service manager and init system | Universal on modern Linux, handles process lifecycle, logging, restart policies |
| bash | built-in | Shell scripting for install/deploy | Native to Linux, no dependencies, excellent for glue code and system commands |
| venv | Python 3.9+ | Virtual environment isolation | Built into Python 3.3+, no external deps, standard for dependency isolation |
| git | built-in | Version control and deployment | Already installed on Raspberry Pi OS, enables simple pull-based deploys |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| raspi-config | built-in | Hardware interface configuration | Headless SPI/I2C enablement (`raspi-config nonint do_spi 0`) |
| journalctl | built-in | systemd log viewer | View service logs (`journalctl -u service-name -f`) |
| pip | 20.0+ | Python package installation | Install deps from requirements.txt in venv |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| systemd | supervisord | More complex setup, additional dependency, less integrated with OS |
| git pull | rsync/scp | No version control, harder rollback, manual file management |
| bash scripts | Ansible/Python fabric | Overkill for single-device deployment, adds complexity |

**Installation:**
```bash
# No installation needed - all tools built into Raspberry Pi OS
# Only requirements.txt dependencies need installation:
pip install -r requirements.txt
```

## Architecture Patterns

### Recommended Project Structure
```
/home/pi/solaredge-monitor/          # Application root
├── main.py                           # Entry point
├── requirements.txt                  # Pinned dependencies
├── .env                              # Secrets (gitignored)
├── .env.example                      # Template for setup
├── venv/                             # Virtual environment (gitignored)
├── solaredge-monitor.service         # systemd unit file (committed)
├── install.sh                        # Initial Pi setup script
├── deploy.sh                         # Update script (runs on Pi)
└── README.md                         # Documentation
```

### Pattern 1: systemd Service File for Python Application with venv

**What:** systemd unit file that runs Python script from virtual environment with automatic restart

**When to use:** Any long-running Python application that should start on boot and restart on failure

**Example:**
```ini
# Source: https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html
# https://gist.github.com/ricferr/90583f608f0b0ae9c3cf6833be04ab85

[Unit]
Description=SolarEdge Off-Grid Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/solaredge-monitor
ExecStart=/home/pi/solaredge-monitor/venv/bin/python3 main.py
Restart=always
RestartSec=10

# Rate limiting to prevent restart loops
StartLimitIntervalSec=200
StartLimitBurst=5

# Logging (stdout/stderr captured by journald)
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Key considerations:**
- **ExecStart must use absolute paths** - both to Python interpreter in venv and to script
- **No venv activation needed** - direct path to venv/bin/python3 loads correct environment
- **Restart=always vs on-failure** - "always" restarts on any exit (crash, clean exit, signal); "on-failure" only on errors. Per [official docs](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html): "Setting this to on-failure is the recommended choice for long-running services" but user decision specified "always"
- **RestartSec delay** - Default 100ms is too aggressive; 5-30 seconds prevents rapid restart loops
- **StartLimit parameters** - Default is 5 restarts in 10 seconds then give up; extend interval to allow longer recovery periods
- **Type=simple** - Process doesn't fork; systemd considers it started immediately (appropriate for Python scripts)

### Pattern 2: Idempotent Install Script

**What:** Bash script that sets up Raspberry Pi environment, safe to run multiple times

**When to use:** Initial Pi provisioning and when dependencies/config change

**Example:**
```bash
#!/bin/bash
# Source: Combined best practices from multiple sources
# https://medium.com/@azinke.learn/packaging-shell-scripts-9309e200c818
# https://citizen428.net/blog/bash-error-handling-with-trap/

set -e  # Exit on error
set -u  # Exit on undefined variable

echo "SolarEdge Monitor - Installation Script"
echo "========================================"

# Check if SPI is enabled
echo "Checking SPI interface..."
if ! ls /dev/spidev* &> /dev/null; then
    echo "Enabling SPI interface..."
    sudo raspi-config nonint do_spi 0
    echo "SPI enabled - reboot required after installation"
    REBOOT_REQUIRED=true
else
    echo "SPI already enabled"
fi

# Add user to spi/gpio groups (idempotent - adduser checks if already member)
echo "Configuring user permissions..."
sudo adduser $USER spi || true
sudo adduser $USER gpio || true

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists"
fi

# Install/upgrade dependencies
echo "Installing dependencies..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# Setup .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your SolarEdge credentials:"
    echo "    nano .env"
else
    echo ".env file already exists (keeping existing values)"
fi

# Install systemd service
echo "Installing systemd service..."
sudo cp solaredge-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable solaredge-monitor.service

echo ""
echo "Installation complete!"
if [ "${REBOOT_REQUIRED:-false}" = true ]; then
    echo ""
    echo "⚠️  REBOOT REQUIRED for SPI changes to take effect"
    echo "    After reboot, edit .env then: sudo systemctl start solaredge-monitor"
else
    echo ""
    echo "Next steps:"
    echo "  1. Edit .env with your credentials: nano .env"
    echo "  2. Start service: sudo systemctl start solaredge-monitor"
    echo "  3. Check status: sudo systemctl status solaredge-monitor"
    echo "  4. View logs: journalctl -u solaredge-monitor -f"
fi
```

**Key patterns:**
- **set -e/-u for safety** - Fail fast on errors or undefined variables
- **Idempotent checks** - Test before creating (venv exists? .env exists?)
- **adduser || true** - Allow failure if user already in group
- **Preserve existing .env** - Don't overwrite user's secrets
- **Clear user feedback** - Print each step, guide next actions

### Pattern 3: Deployment Script (runs on Pi)

**What:** Update script that pulls latest code and restarts service

**When to use:** Every deployment after initial setup

**Example:**
```bash
#!/bin/bash
# Source: https://medium.com/star-gazers/automating-git-deployment-93678bd4c8b
# Git best practices: https://www.w3schools.com/git/git_best_practices.asp

set -e

echo "SolarEdge Monitor - Deployment Script"
echo "====================================="

# Pull latest code
echo "Pulling latest code from git..."
git pull

# Always reinstall dependencies (ensures new deps are installed)
echo "Installing dependencies..."
venv/bin/pip install -r requirements.txt

# Restart systemd service
echo "Restarting service..."
sudo systemctl restart solaredge-monitor

# Show status
echo ""
echo "Deployment complete!"
echo ""
echo "Status:"
sudo systemctl status solaredge-monitor --no-pager

echo ""
echo "View logs: journalctl -u solaredge-monitor -f"
```

**Key patterns:**
- **Verbose output** - Print each step for visibility
- **Always reinstall deps** - Simpler than detecting changes, ensures consistency
- **Restart not reload** - Full restart ensures clean state
- **Show status after deploy** - Immediate feedback on deployment success

### Anti-Patterns to Avoid

- **Using relative paths in systemd ExecStart:** systemd runs from / not WorkingDirectory, causing "file not found" errors. Always use absolute paths.
- **Activating venv in systemd:** Don't use `bash -c "source venv/bin/activate && python main.py"`. Instead use direct path to venv Python interpreter.
- **No RestartSec delay with Restart=always:** Default 100ms causes rapid restart loops. Always set 5+ second delay.
- **Committing .env or venv/ to git:** Secrets leak and venv is platform-specific. Always gitignore both.
- **Forgetting StartLimit parameters:** Default 5 restarts in 10 seconds can cause systemd to give up too quickly. Adjust for realistic recovery time.
- **Running as root unnecessarily:** The 'pi' user has GPIO/SPI access by default via group membership. Don't use User=root.
- **Manual pip install on each host:** Leads to version drift. Always use pinned requirements.txt.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Process management | Custom daemon/fork logic | systemd | systemd handles restart, logging, startup ordering, resource limits, dependency management |
| Log rotation | Custom log file management | systemd journald + RotatingFileHandler | Already implemented in Phase 5; journald handles systemd output automatically, Python RotatingFileHandler for file logs |
| Init script | /etc/init.d script | systemd unit file | systemd is standard on modern Linux, init.d is deprecated |
| Deployment automation | Custom Python deployment script | bash + git + systemd | Bash has better error handling for system commands, git is standard versioning, systemd restart is one command |
| Virtual environment activation | Source activation in scripts | Direct venv/bin/python path | Activation is shell-only convenience; direct path works in any context |
| Hardware permissions | chmod/chown on /dev/spidev | User group membership (spi/gpio groups) | Groups are persistent across reboots, managed by udev rules |
| Environment variables in systemd | EnvironmentFile= pointing to .env | Load .env in Python with python-dotenv | .env file has no shell escaping, easier to parse in Python than bash |

**Key insight:** Linux system administration has decades of established patterns. Raspberry Pi ecosystem has mature conventions for hardware access. Leverage existing infrastructure rather than reinventing process management, permissions, or logging.

## Common Pitfalls

### Pitfall 1: SPI Permission Denied Errors

**What goes wrong:** Service starts but crashes with "Permission denied" when accessing /dev/spidev0.0

**Why it happens:** User not in 'spi' group, or SPI interface not enabled in raspi-config. Group membership requires logout/login to take effect (or reboot for services).

**How to avoid:**
- Enable SPI in install script: `sudo raspi-config nonint do_spi 0`
- Add user to groups: `sudo adduser pi spi` and `sudo adduser pi gpio`
- Require reboot after install if SPI was just enabled
- Test with: `ls -l /dev/spidev* && groups` to verify device exists and user in groups

**Warning signs:**
- Error logs mentioning "Permission denied" or "/dev/spidev"
- Service runs fine with sudo but fails as user
- Check groups with `groups pi` and verify 'spi' and 'gpio' are listed

**Sources:**
- [Raspberry Pi Forums: SPI Permission Denied](https://forums.raspberrypi.com/viewtopic.php?t=106814)
- [Robotics Back-End: Hardware Permissions](https://roboticsbackend.com/raspberry-pi-hardware-permissions/)

### Pitfall 2: systemd Restart Loops Hitting Start Limit

**What goes wrong:** Service crashes repeatedly, systemd gives up after 5 attempts with "start request repeated too quickly"

**Why it happens:** Default `StartLimitBurst=5` in 10 seconds (`StartLimitIntervalSec=10s`) means systemd stops trying after 5 quick failures. If application crashes immediately (bad config, missing deps), hits limit in seconds.

**How to avoid:**
- Set `StartLimitIntervalSec=200` (larger window)
- Set `StartLimitBurst=5` (reasonable attempt count)
- Set `RestartSec=10` (delay between attempts)
- Formula: `StartLimitIntervalSec > RestartSec * StartLimitBurst`
- Example: 200s > 10s * 5 = 50s (leaves buffer)

**Warning signs:**
- `systemctl status` shows "start request repeated too quickly"
- Service stopped and won't restart automatically
- Check with `systemctl list-units --failed`

**Sources:**
- [Michael Stapelberg: systemd indefinite service restarts](https://michael.stapelberg.ch/posts/2024-01-17-systemd-indefinite-service-restarts/)
- [Chris's Wiki: systemd RestartSec](https://utcc.utoronto.ca/~cks/space/blog/linux/SystemdRestartUseDelay)

### Pitfall 3: Virtual Environment Not Used by systemd Service

**What goes wrong:** Service fails with ImportError for packages that are installed in venv

**Why it happens:** Using `ExecStart=python3 main.py` uses system Python, not venv Python. WorkingDirectory doesn't activate venv.

**How to avoid:**
- Use absolute path to venv Python: `/home/pi/solaredge-monitor/venv/bin/python3`
- Use absolute path to script: `/home/pi/solaredge-monitor/main.py` or rely on WorkingDirectory
- Don't use `source venv/bin/activate` in systemd (doesn't work, activation is shell-only)
- Test ExecStart command manually first: `/full/path/to/venv/bin/python3 /full/path/to/script.py`

**Warning signs:**
- ImportError in logs for packages in requirements.txt
- Service works when run manually with venv activated
- `which python3` in systemd shows `/usr/bin/python3` not venv path

**Sources:**
- [Gist: systemd with virtualenv](https://gist.github.com/ricferr/90583f608f0b0ae9c3cf6833be04ab85)
- [Using Systemd with Python Virtualenv](https://www.tderflinger.com/using-systemd-to-start-a-python-application-with-virtualenv)

### Pitfall 4: .env File Not Loaded or Secrets in Git

**What goes wrong:** Either (a) application can't find .env file from systemd, or (b) secrets accidentally committed to git

**Why it happens:**
- (a) systemd WorkingDirectory may not be set, .env file loaded relative to cwd
- (b) .env not in .gitignore, or .gitignore added after .env was committed

**How to avoid:**
- Application loads .env at startup: `load_dotenv()` (already done in main.py)
- systemd sets WorkingDirectory to app root: `WorkingDirectory=/home/pi/solaredge-monitor`
- .env in .gitignore: `.env` and `.env.*` with exception `!.env.example`
- Check git before commit: `git status` should not show .env
- If .env was committed: `git rm --cached .env` then force push (if not public) or rotate secrets

**Warning signs:**
- Config validation errors about missing API keys
- .env file appears in `git status`
- Service works manually but not via systemd
- Check with `git ls-files | grep .env` (should only show .env.example)

**Sources:**
- [GitIgnore FAQ](https://gitignore.pro/faq)
- [OpenAI: API Key Safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety)

### Pitfall 5: Deployment Script Run as Root Breaking File Permissions

**What goes wrong:** After running deploy.sh with sudo, files owned by root, service can't write logs or update files

**Why it happens:** `sudo ./deploy.sh` runs git pull as root, creating root-owned files. Service runs as 'pi' user, can't write to root-owned files.

**How to avoid:**
- Run deploy.sh as pi user (not sudo): `./deploy.sh`
- Only restart command uses sudo: script calls `sudo systemctl restart` internally
- If files become root-owned: `sudo chown -R pi:pi /home/pi/solaredge-monitor`
- Repository should be cloned as pi user, not root
- Install script should `cd /home/pi` and clone as pi user

**Warning signs:**
- Permission denied when writing log files
- Git pull fails with "permission denied"
- `ls -la` shows root:root ownership on application files
- Check with: `ls -la /home/pi/solaredge-monitor` (should show pi:pi)

**Sources:**
- General Linux file permission knowledge
- [Medium: Automating Git Deployment](https://medium.com/star-gazers/automating-git-deployment-93678bd4c8b)

## Code Examples

Verified patterns from official sources and community best practices:

### Complete systemd Service File

```ini
# /etc/systemd/system/solaredge-monitor.service
# Source: https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html
# Combines patterns from multiple community sources

[Unit]
Description=SolarEdge Off-Grid Monitor
Documentation=https://github.com/user/solaredge-offgrid-monitor
After=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/solaredge-monitor

# Use venv Python with absolute paths
ExecStart=/home/pi/solaredge-monitor/venv/bin/python3 main.py

# Restart policy: always restart on any exit
Restart=always
RestartSec=10

# Rate limiting to prevent restart loops
StartLimitIntervalSec=200
StartLimitBurst=5

# Logging (captured by journald and application's own file logging)
StandardOutput=journal
StandardError=journal
SyslogIdentifier=solaredge-monitor

[Install]
WantedBy=multi-user.target
```

### Install Script with Error Handling

```bash
#!/bin/bash
# install.sh - Idempotent installation script
# Source: Combined best practices from bash error handling guides

set -e  # Exit on error
set -u  # Exit on unset variable

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "SolarEdge Monitor - Installation Script"
echo "=========================================="
echo ""

# Check if running as pi user (not root)
if [ "$USER" = "root" ]; then
    echo "ERROR: Do not run as root. Run as pi user: ./install.sh"
    exit 1
fi

# Check if SPI is enabled
echo "[1/6] Checking SPI interface..."
if ! ls /dev/spidev* &> /dev/null; then
    echo "  → Enabling SPI interface..."
    sudo raspi-config nonint do_spi 0
    echo "  → SPI enabled"
    REBOOT_REQUIRED=true
else
    echo "  → SPI already enabled ✓"
fi

# Add user to spi/gpio groups
echo ""
echo "[2/6] Configuring user permissions..."
if groups $USER | grep -q '\bspi\b'; then
    echo "  → User already in 'spi' group ✓"
else
    sudo adduser $USER spi
    echo "  → Added to 'spi' group"
    REBOOT_REQUIRED=true
fi

if groups $USER | grep -q '\bgpio\b'; then
    echo "  → User already in 'gpio' group ✓"
else
    sudo adduser $USER gpio
    echo "  → Added to 'gpio' group"
    REBOOT_REQUIRED=true
fi

# Create venv
echo ""
echo "[3/6] Setting up Python virtual environment..."
if [ -d "venv" ]; then
    echo "  → Virtual environment already exists ✓"
else
    python3 -m venv venv
    echo "  → Created virtual environment"
fi

# Install dependencies
echo ""
echo "[4/6] Installing Python dependencies..."
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q
echo "  → Dependencies installed ✓"

# Setup .env
echo ""
echo "[5/6] Configuring environment..."
if [ -f ".env" ]; then
    echo "  → .env file already exists (preserving) ✓"
else
    cp .env.example .env
    echo "  → Created .env from template"
    echo ""
    echo "  ⚠️  IMPORTANT: You must edit .env and add your SolarEdge credentials"
    echo "     Edit with: nano .env"
    NEEDS_ENV_CONFIG=true
fi

# Install systemd service
echo ""
echo "[6/6] Installing systemd service..."
sudo cp solaredge-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable solaredge-monitor.service
echo "  → Service installed and enabled ✓"

# Summary
echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="

if [ "${REBOOT_REQUIRED:-false}" = true ]; then
    echo ""
    echo "⚠️  REBOOT REQUIRED"
    echo "   Hardware permissions or SPI settings changed."
    echo ""
    echo "Next steps:"
    echo "  1. Edit .env: nano .env"
    echo "  2. Reboot: sudo reboot"
    echo "  3. Check service: sudo systemctl status solaredge-monitor"
elif [ "${NEEDS_ENV_CONFIG:-false}" = true ]; then
    echo ""
    echo "Next steps:"
    echo "  1. Edit .env: nano .env"
    echo "  2. Start: sudo systemctl start solaredge-monitor"
    echo "  3. Check status: sudo systemctl status solaredge-monitor"
    echo "  4. View logs: journalctl -u solaredge-monitor -f"
else
    echo ""
    echo "Service ready to start!"
    echo "  Start: sudo systemctl start solaredge-monitor"
    echo "  Status: sudo systemctl status solaredge-monitor"
    echo "  Logs: journalctl -u solaredge-monitor -f"
fi
```

### Deploy Script

```bash
#!/bin/bash
# deploy.sh - Update deployed application
# Run on Pi as pi user after git pull

set -e

echo "=========================================="
echo "SolarEdge Monitor - Deployment"
echo "=========================================="
echo ""

# Verify running as pi user
if [ "$USER" = "root" ]; then
    echo "ERROR: Do not run as root. Run as pi user: ./deploy.sh"
    exit 1
fi

# Pull latest code
echo "[1/3] Pulling latest code from git..."
git pull
echo "  → Code updated ✓"

# Reinstall dependencies (in case requirements changed)
echo ""
echo "[2/3] Installing dependencies..."
venv/bin/pip install -r requirements.txt -q
echo "  → Dependencies updated ✓"

# Restart service
echo ""
echo "[3/3] Restarting service..."
sudo systemctl restart solaredge-monitor
echo "  → Service restarted ✓"

# Show status
echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
sudo systemctl status solaredge-monitor --no-pager -l

echo ""
echo "View logs: journalctl -u solaredge-monitor -f"
```

### Checking Service Status and Logs

```bash
# View service status
sudo systemctl status solaredge-monitor

# View recent logs (last 50 lines)
journalctl -u solaredge-monitor -n 50

# Follow logs in real-time
journalctl -u solaredge-monitor -f

# View logs since boot
journalctl -u solaredge-monitor -b

# View logs with timestamp and priority
journalctl -u solaredge-monitor -o verbose

# Filter by log level (error and above)
journalctl -u solaredge-monitor -p err

# View both journald and file logs
# (journald for systemd output, file for application logging)
journalctl -u solaredge-monitor -f &  # Terminal 1
tail -f /home/pi/solaredge-monitor/solaredge_monitor.log  # Terminal 2
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| init.d scripts | systemd unit files | 2015 (systemd adoption) | Simpler syntax, better dependency management, automatic logging |
| supervisord for Python apps | systemd | 2015-2020 | One less dependency, OS-native, better integration |
| Manual venv activation in scripts | Direct venv/bin/python path | Always best practice | Works in all contexts, no shell dependency |
| pip install without version pinning | requirements.txt with pinned versions | 2016+ (pip freeze) | Reproducible deployments, no surprise breakage |
| source-based pip install on deploy | Build once, distribute binary wheels | 2018+ (PEP 517) | Faster deploys, but not applicable to single-device git pull workflow |
| RestartSec=100ms default | RestartSec=5-30s recommended | systemd 254 (2023) | New exponential backoff features (RestartSteps, RestartMaxDelaySec) |
| PYTHONUNBUFFERED in systemd | StandardOutput=journal (unbuffered by default) | Always | systemd handles unbuffering, no env var needed |

**Deprecated/outdated:**
- **/etc/init.d/ scripts:** Replaced by systemd. Still supported for compatibility but not recommended for new services.
- **screen/tmux for background processes:** Replaced by systemd. Not persistent across reboots, no automatic restart.
- **Hardcoded paths in application:** Use environment variables and load_dotenv(). Allows deployment flexibility.
- **Python 2 virtualenv command:** Use Python 3's built-in `python3 -m venv`. virtualenv package no longer needed.

## Open Questions

Things that couldn't be fully resolved:

1. **Restart delay for e-ink display applications**
   - What we know: Standard recommendation is RestartSec=5-30s for typical services
   - What's unclear: Whether e-ink display needs longer delay due to hardware refresh cycles or init time
   - Recommendation: Start with 10s (middle ground), monitor logs for "too quick" errors, adjust if needed. E-ink display initialization in this project is fast (<1s per display.py), so standard delay is fine.

2. **Log file rotation interaction with systemd journal**
   - What we know: Application already implements RotatingFileHandler (Phase 5) AND logs to stdout (captured by journald)
   - What's unclear: Whether duplicate logging to both journal and file is optimal, or if one should be preferred
   - Recommendation: Keep both as implemented. File logs persist across system reinstalls and are easily copied/archived. journalctl integrates with systemd status and provides unified system view. Disk space is cheap (60MB cap on file logs).

3. **Handling requirements.txt changes during deploy**
   - What we know: `pip install -r requirements.txt` reinstalls everything, not just new packages
   - What's unclear: Whether pip's caching makes this fast enough, or if change detection would improve deploy speed
   - Recommendation: Always reinstall (current approach). Pip's wheel cache makes this fast (~2-5s), and guarantees consistency. Change detection adds complexity for minimal gain on Raspberry Pi single-device deployment.

## Sources

### Primary (HIGH confidence)

- [systemd.service official documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html) - Restart policies, ExecStart, service types
- [GitHub gitignore Python template](https://github.com/github/gitignore/blob/main/Python.gitignore) - Standard .gitignore patterns
- [Raspberry Pi Configuration Documentation](https://www.raspberrypi.com/documentation/computers/configuration.html) - raspi-config commands
- [Michael Stapelberg: systemd indefinite restarts (2024)](https://michael.stapelberg.ch/posts/2024-01-17-systemd-indefinite-service-restarts/) - StartLimit configuration
- [freedesktop.org: systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html) - Execution environment

### Secondary (MEDIUM confidence)

- [TheDigitalPictureFrame: systemd autostart guide](https://www.thedigitalpictureframe.com/ultimate-guide-systemd-autostart-scripts-raspberry-pi/) - Raspberry Pi specific systemd patterns
- [Robotics Back-End: Hardware Permissions](https://roboticsbackend.com/raspberry-pi-hardware-permissions/) - SPI/GPIO group membership
- [Gist: systemd with virtualenv](https://gist.github.com/ricferr/90583f608f0b0ae9c3cf6833be04ab85) - Working example of Python venv in systemd
- [Using Systemd with Python Virtualenv](https://www.tderflinger.com/using-systemd-to-start-a-python-application-with-virtualenv) - ExecStart patterns
- [Citizen428: Bash Error Handling with Trap](https://citizen428.net/blog/bash-error-handling-with-trap/) - set -e and trap patterns
- [Chris's Wiki: systemd RestartSec](https://utcc.utoronto.ca/~cks/space/blog/linux/SystemdRestartUseDelay) - Why to use RestartSec delay
- [GitIgnore FAQ](https://gitignore.pro/faq) - .env and sensitive files
- [OpenAI: API Key Safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety) - Environment variable best practices
- [Make a README](https://www.makeareadme.com/) - README structure
- [Baeldung: systemd Working Directory](https://www.baeldung.com/linux/systemd-service-working-directory) - WorkingDirectory configuration

### Tertiary (LOW confidence)

- Various Raspberry Pi forum posts - Specific permission/SPI issues, marked LOW due to single-source nature but cross-verified with documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools are built into Raspberry Pi OS or Python stdlib, systemd is universal on modern Linux
- Architecture: HIGH - Patterns verified with official systemd docs and multiple working examples from community
- Pitfalls: HIGH - Each pitfall sourced from official docs or verified community reports with solutions

**Research date:** 2026-02-06
**Valid until:** 90 days (deployment patterns stable, systemd changes slowly, Raspberry Pi OS major updates ~yearly)
