# Domain Pitfalls: Dockerized Raspberry Pi E-Ink Monitor with Kamal Deployment

**Domain:** Containerized Raspberry Pi hardware monitoring with SPI/GPIO access
**Researched:** 2026-02-04
**Confidence:** MEDIUM (based on training knowledge + project code analysis)

## Executive Summary

Containerizing Raspberry Pi hardware projects with GPIO/SPI access presents unique challenges that differ fundamentally from standard web application containerization. The combination of hardware device passthrough, ARM architecture constraints, Kamal's SSH-based deployment model, and third-party API integration creates a minefield of subtle failures that only manifest in production.

**Critical insight:** Docker's isolation model directly conflicts with hardware access requirements. Most pitfalls stem from attempting to treat hardware-accessing containers like stateless web services.

---

## Critical Pitfalls

These mistakes cause complete failures or require architectural rewrites.

### Pitfall 1: Missing Device Passthrough in Docker Run
**What goes wrong:** Container starts successfully but fails with "No such file or directory" or "Permission denied" when accessing `/dev/spidev0.0` or GPIO pins. The e-ink display never updates.

**Why it happens:** Docker containers are isolated from host hardware by default. SPI devices and GPIO aren't accessible without explicit device passthrough. Many developers test with `--privileged` (which works), then deploy with Kamal's default configuration (which doesn't include devices).

**Consequences:**
- Application appears to run (no startup errors)
- Silent failures in display update functions
- GPIO libraries throw cryptic errors
- Zero visual feedback that anything is wrong

**Prevention:**
```yaml
# config/deploy.yml
service: solaredge-monitor

servers:
  web:
    - 192.168.1.x

docker:
  options:
    devices:
      - /dev/spidev0.0:/dev/spidev0.0
      - /dev/spidev0.1:/dev/spidev0.1  # Some displays need both
      - /dev/gpiomem:/dev/gpiomem
    cap_add:
      - SYS_RAWIO  # Required for GPIO access
```

**Detection:**
- Application logs show import errors for `spidev` or `gpiozero`
- Display functions complete without errors but screen doesn't update
- `ls /dev/spi*` inside container returns empty
- GPIO pin state reads return None or 0 consistently

**Phase to address:** Phase 1 (Docker Foundation) - Must be configured correctly from the start, otherwise all hardware testing is invalid.

**Known variations:**
- Some Waveshare displays require `/dev/mem` access (even more privileged)
- Older Raspberry Pi OS versions use different device paths
- RPi 5 has different GPIO chip paths (`/dev/gpiochip4`)

---

### Pitfall 2: ARM64 vs ARMv7 Architecture Mismatch
**What goes wrong:** Docker image builds successfully on macOS (ARM64) or Linux (x86_64) but fails to start on Raspberry Pi with "exec format error" or pulls wrong architecture images.

**Why it happens:**
1. Raspberry Pi OS can run in 32-bit mode (ARMv7) even on 64-bit hardware (RPi 3B+, 4, 5)
2. Docker Hub's `linux/arm64` images won't run on 32-bit OS
3. Multi-arch image manifests can select wrong platform automatically
4. Python wheels for ARM aren't always available for both architectures

**Consequences:**
- Container exits immediately with cryptic error
- Dependency installation hangs or fails
- Native libraries (like Pillow) install wrong binaries
- Works on Pi 4 (64-bit OS) but fails on Pi 3 (32-bit OS)

**Prevention:**
```dockerfile
# Dockerfile
# ALWAYS specify exact platform for Raspberry Pi
FROM --platform=linux/arm/v7 python:3.11-slim-bookworm

# OR for 64-bit Pi OS
FROM --platform=linux/arm64/v8 python:3.11-slim-bookworm

# Check architecture in build output
RUN uname -m && echo "Architecture: $(dpkg --print-architecture)"
```

**Build commands:**
```bash
# On development machine, build for target Pi architecture
docker buildx build --platform linux/arm/v7 -t myapp:latest .

# Check what architecture your Pi is running
ssh pi@raspberrypi.local "uname -m"
# armv7l = 32-bit, aarch64 = 64-bit
```

**Detection:**
- Container logs show: `exec /usr/local/bin/python: exec format error`
- `docker inspect` shows wrong architecture
- Container status is "Exited (1)" immediately after start
- Kamal deploy succeeds but container won't stay running

**Phase to address:** Phase 1 (Docker Foundation) - Verify before any deployment work.

**Additional notes:**
- Raspberry Pi 3B+ commonly runs 32-bit OS by default
- Raspberry Pi 4/5 can run either, check with `getconf LONG_BIT`
- Cross-compilation adds 5-10 minutes to build time
- Some Python packages (RPi.GPIO, spidev) compile C extensions - architecture matters

---

### Pitfall 3: GPIO Library Incompatibility Inside Containers
**What goes wrong:** Code works perfectly on Pi outside Docker but crashes inside container with "RuntimeError: Not running on a RPi!" or "No access to /dev/gpiomem."

**Why it happens:** GPIO libraries (RPi.GPIO, gpiozero) detect Raspberry Pi by reading `/proc/cpuinfo` or checking specific file paths. Inside containers:
- `/proc/cpuinfo` may show container host architecture
- Library initialization fails before attempting hardware access
- Some libraries refuse to run if they don't detect "Raspberry Pi" in CPU info

**Consequences:**
- Application fails at startup during GPIO library import
- Can't test display code in container
- Different behavior between direct Python execution and containerized execution
- Error messages blame hardware when issue is containerization

**Prevention:**
```dockerfile
# Waveshare's library uses gpiozero and spidev - both are container-friendly
# Avoid RPi.GPIO (explicitly checks for Raspberry Pi)

RUN pip install --no-cache-dir \
    spidev \
    gpiozero \
    pillow

# If forced to use RPi.GPIO, set environment variable
ENV GPIOZERO_PIN_FACTORY=mock  # For testing only
```

**Alternative:** Use the approach from your existing code (`epdconfig.py` lines 312-317) which auto-detects Raspberry Pi from `/proc/cpuinfo` inside container.

**Detection:**
- Import fails with "Not running on a RPi"
- Library initialization succeeds on host, fails in container
- GPIO library gives generic "No access" errors
- `/proc/cpuinfo` inside container doesn't match Pi hardware

**Phase to address:** Phase 1 (Docker Foundation) - Library selection affects entire architecture.

---

### Pitfall 4: SPI Not Enabled in Raspberry Pi OS
**What goes wrong:** Docker container has all correct device passthrough, but `/dev/spidev0.0` doesn't exist on the host.

**Why it happens:** SPI interface is disabled by default in Raspberry Pi OS. Most tutorials assume it's enabled. When setting up fresh Pi for Kamal deployment, easy to forget this prerequisite.

**Consequences:**
- Kamal deployment succeeds
- Container starts but display code fails
- `/dev/spidev*` devices missing entirely
- Error: "No such file or directory: '/dev/spidev0.0'"

**Prevention:**
```bash
# On Raspberry Pi (run once during Pi setup)
sudo raspi-config nonint do_spi 0  # 0 = enable

# Verify SPI is enabled
ls -l /dev/spidev*
# Should show: /dev/spidev0.0 and /dev/spidev0.1

# Add to Pi provisioning checklist
lsmod | grep spi
# Should show spi_bcm2835 module loaded
```

**Detection:**
- Host doesn't have `/dev/spidev*` devices
- `lsmod | grep spi` returns empty on Pi
- Container logs show FileNotFoundError for SPI device
- Display code imports successfully but device access fails

**Phase to address:** Phase 0 (Prerequisites Documentation) - Document Pi setup before deployment configuration.

**Additional notes:**
- Survives reboots once enabled
- Some Pi OS images have SPI enabled by default
- Waveshare displays also need I2C disabled if pins conflict
- Different display models use different SPI buses

---

### Pitfall 5: Kamal Deploy Overwrites Container Without Graceful Shutdown
**What goes wrong:** During deployment, Kamal stops running container immediately. If display is mid-update, e-ink display can be left in corrupted state (partial image, ghosting, or stuck pixels).

**Why it happens:**
- Kamal's default deployment strategy: stop old container, start new one
- E-ink displays require proper shutdown sequence (clear screen, power off)
- Container receives SIGTERM but Python script may not handle it
- Display update cycle takes 2-3 seconds, container killed mid-cycle

**Consequences:**
- Display shows corrupted partial images after deploy
- E-ink "ghosting" effect where old image persists
- Requires manual power cycle of Pi to clear display
- No graceful cleanup of GPIO pins

**Prevention:**
```python
# In main application
import signal
import sys

def signal_handler(signum, frame):
    """Handle container shutdown gracefully"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")

    try:
        # Clear display before exit
        if not debug:
            from waveshare_epd import epd2in13_V3
            epd = epd2in13_V3.EPD()
            epd.init()
            epd.Clear(0xFF)
            epd.sleep()
            epd.module_exit()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
```

```yaml
# config/deploy.yml
docker:
  options:
    stop_grace_period: 10s  # Give container time to cleanup
```

**Detection:**
- Display shows partial/corrupted images after deployment
- Container logs show abrupt termination mid-update
- No cleanup messages in logs before container stops
- GPIO pins left in indeterminate state

**Phase to address:** Phase 2 (Deployment Strategy) - After basic containerization works.

---

### Pitfall 6: Hardcoded Credentials in Fresh Repo
**What goes wrong:** Migrating to fresh repo to remove credential history, but credentials still end up committed in new repo because code has hardcoded values (lines 32-44 of current `se-overview.py`).

**Why it happens:**
- Muscle memory: edit file, test, commit
- Environment variables not configured before first commit
- `.env` file not in `.gitignore` of new repo
- Testing with real credentials before implementing env var loading

**Consequences:**
- Fresh repo immediately contaminated with secrets
- SolarEdge API key exposed in first commit
- BMW/VW account passwords in git history forever
- SSH credentials to Time Machine server committed
- Entire migration exercise wasted

**Prevention:**
```python
# BEFORE first commit to new repo
import os

# Load from environment variables
api_key = os.environ.get('SOLAREDGE_API_KEY')
site_id = os.environ.get('SOLAREDGE_SITE_ID')
hostname = os.environ.get('TIMEMACHINE_HOST')
username = os.environ.get('TIMEMACHINE_USER')
password = os.environ.get('TIMEMACHINE_PASSWORD')

we_connect_email = os.environ.get('WE_CONNECT_EMAIL')
we_connect_password = os.environ.get('WE_CONNECT_PASSWORD')
we_connect_vin = os.environ.get('WE_CONNECT_VIN')

bmw_email = os.environ.get('BMW_EMAIL')
bmw_password = os.environ.get('BMW_PASSWORD')
bmw_vin = os.environ.get('BMW_VIN')

# Fail fast if any required credential is missing
required_vars = [
    'SOLAREDGE_API_KEY', 'SOLAREDGE_SITE_ID',
    'WE_CONNECT_EMAIL', 'WE_CONNECT_PASSWORD', 'WE_CONNECT_VIN',
    'BMW_EMAIL', 'BMW_PASSWORD', 'BMW_VIN'
]

missing = [var for var in required_vars if not os.environ.get(var)]
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
```

```gitignore
# .gitignore in new repo (CREATE BEFORE FIRST COMMIT)
.env
.env.local
.env.production
credentials.py
debug/
*.pyc
__pycache__/
```

```bash
# Kamal secrets management
# config/deploy.yml
env:
  secret:
    - SOLAREDGE_API_KEY
    - SOLAREDGE_SITE_ID
    - WE_CONNECT_EMAIL
    - WE_CONNECT_PASSWORD
    - WE_CONNECT_VIN
    - BMW_EMAIL
    - BMW_PASSWORD
    - BMW_VIN
    - TIMEMACHINE_HOST
    - TIMEMACHINE_USER
    - TIMEMACHINE_PASSWORD
```

**Detection:**
- Running `git log` in new repo shows credential values
- `git grep "api_key ="` finds hardcoded values
- First commit contains assignment statements with string literals
- `.env` file tracked by git

**Phase to address:** Phase 0 (Repo Setup) - FIRST TASK before any code migration.

---

### Pitfall 7: SolarEdge API Rate Limiting with Container Restarts
**What goes wrong:** During development/debugging, container restarts frequently. Each restart makes API calls on startup. SolarEdge API rate limit (300 calls/day for free tier) exhausted quickly, causing service outage.

**Why it happens:**
- Container restart = fresh Python process = immediate API call
- No rate limiting logic in application code
- No caching of API responses between restarts
- Debug cycle: change code -> restart container -> test (10+ times/hour)
- Each display cycle calls API 3 times (overview, energy details, power flow)

**Consequences:**
- API returns 429 Too Many Requests
- Display stuck showing stale data
- No monitoring data for rest of day
- Can't debug display rendering without hitting rate limit
- Development completely blocked during testing

**Prevention:**
```python
import time
import json
from pathlib import Path

CACHE_DIR = Path("/data/cache")  # Mount persistent volume here
CACHE_EXPIRY = 180  # Match API refresh interval (3 minutes)

def get_cached_or_fetch(cache_key, fetch_func):
    """Cache API responses to avoid rate limiting during restarts"""
    cache_file = CACHE_DIR / f"{cache_key}.json"

    # Check if cache exists and is fresh
    if cache_file.exists():
        cache_age = time.time() - cache_file.stat().st_mtime
        if cache_age < CACHE_EXPIRY:
            logger.info(f"Using cached data for {cache_key} (age: {cache_age:.0f}s)")
            with open(cache_file) as f:
                return json.load(f)

    # Cache miss or expired - fetch fresh data
    logger.info(f"Fetching fresh data for {cache_key}")
    data = fetch_func()

    # Save to cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump(data, f)

    return data

# Usage
site_overview = get_cached_or_fetch("site_overview", get_site_overview)
```

```dockerfile
# Dockerfile - create cache directory
RUN mkdir -p /data/cache && chmod 777 /data/cache
VOLUME /data/cache
```

```yaml
# config/deploy.yml - persist cache between deployments
volumes:
  - solaredge-cache:/data/cache
```

**Detection:**
- HTTP 429 errors in logs
- `response.status_code == 429`
- API calls succeed early in day, fail later
- Retries don't help (rate limit is per-day)
- Response headers show `X-RateLimit-Remaining: 0`

**Phase to address:** Phase 1 (Docker Foundation) - Implement before deployment testing begins.

**Additional notes:**
- SolarEdge API documentation: https://knowledge-center.solaredge.com/sites/kc/files/se_monitoring_api.pdf
- Daily limit resets at midnight UTC
- Some endpoints share rate limit pool
- Power flow endpoint can return stale data (check `lastUpdateTime`)

---

### Pitfall 8: Kamal's Single-Server SSH Connection Failures
**What goes wrong:** Kamal deployment fails intermittently with "SSH connection timeout" or "Host key verification failed." Works locally on Pi, fails from Kamal.

**Why it happens:**
- Kamal connects via SSH for every command (no persistent connection)
- Raspberry Pi's WiFi can be flaky (dropped connections)
- Pi's SSH server may be rate-limiting connections
- `~/.ssh/known_hosts` on deploy machine doesn't have Pi's key
- mDNS hostname resolution (`raspberrypi.local`) fails from some networks

**Consequences:**
- Deployments fail randomly
- Can't reproduce failure (works when SSH'd manually)
- Kamal retries exhaust without success
- Have to manually SSH to Pi to diagnose
- Rollback attempts also fail (same SSH issues)

**Prevention:**
```yaml
# config/deploy.yml
servers:
  web:
    - 192.168.1.100  # Use static IP, not .local hostname

ssh:
  user: pi
  port: 22
  keys:
    - ~/.ssh/id_rsa
  options:
    - StrictHostKeyChecking=no  # Only for home network
    - ConnectTimeout=10
    - ServerAliveInterval=15
    - ServerAliveCountMax=3
```

**On Raspberry Pi:**
```bash
# Set static IP in router DHCP reservation
# OR configure static IP on Pi
sudo nmtui  # Network Manager TUI
# Or edit /etc/dhcpcd.conf for older Pi OS

# Improve SSH reliability
echo "ClientAliveInterval 60" | sudo tee -a /etc/ssh/sshd_config
echo "ClientAliveCountMax 3" | sudo tee -a /etc/ssh/sshd_config
sudo systemctl restart sshd

# Verify SSH key is added
ssh-copy-id pi@192.168.1.100
```

**Detection:**
- Kamal output shows: "Connection timeout"
- SSH manually works, Kamal deploy fails
- Intermittent failures (works 80% of time)
- Hostname resolution errors for `.local` addresses
- Kamal hangs at "Connecting to servers..."

**Phase to address:** Phase 2 (Deployment Strategy) - Network reliability is deployment prerequisite.

---

## Moderate Pitfalls

These cause delays, workarounds, or technical debt.

### Pitfall 9: Python Package Dependencies with Native Extensions on ARM
**What goes wrong:** `pip install` takes forever in Docker build, or fails with "no matching distribution" for packages with C extensions (Pillow, numpy, cryptography).

**Why it happens:**
- PyPI wheels for `linux/arm/v7` are limited compared to x86_64
- Packages without ARM wheels must compile from source
- Compilation requires build tools (gcc, make, headers)
- ARM compilation is slow (5-10 minutes for Pillow)
- Multi-stage builds don't help if runtime needs compiled libs

**Consequences:**
- Docker builds take 15-30 minutes
- Build failures due to missing development headers
- Image size bloat from build dependencies
- Timeout during `kamal deploy` build phase

**Prevention:**
```dockerfile
# Use Python slim image (has gcc, but smaller than full)
FROM --platform=linux/arm/v7 python:3.11-slim-bookworm

# Install build dependencies first (separate layer for caching)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages (will compile if no wheel)
RUN pip install --no-cache-dir \
    pillow \
    spidev \
    gpiozero \
    requests \
    paramiko

# Alternative: Use piwheels (Raspberry Pi-specific wheel repository)
RUN pip install --index-url=https://www.piwheels.org/simple \
    pillow spidev gpiozero requests
```

**Detection:**
- Build output shows "Building wheel for pillow"
- Build hangs at "Running setup.py install"
- Error: "Command 'gcc' failed with exit status 1"
- Build takes >10 minutes

**Phase to address:** Phase 1 (Docker Foundation) - Optimize before iterating on deployment.

---

### Pitfall 10: Time Zone Mismatch Between Container and Host
**What goes wrong:** Display shows wrong timestamp, API calls use wrong date ranges, scheduled tasks run at wrong times (e.g., night mode between 00:00-06:00 triggers at wrong hours).

**Why it happens:**
- Container defaults to UTC
- Code uses `datetime.datetime.now()` which is TZ-aware
- Display formatting shows UTC time, not local time
- API date range queries use wrong timezone
- Your code has time-based logic (lines 823-824: skip between 00:00-06:00)

**Consequences:**
- Display shows incorrect "last update time"
- Night mode activates at wrong hours (6am local = 5am or 7am UTC depending on DST)
- Energy "today" queries span wrong 24-hour period
- User confusion ("Why is display updating at 2am?")

**Prevention:**
```dockerfile
# Dockerfile
ENV TZ=Europe/Zurich
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
```

```python
# Or in code, use explicit timezone
from zoneinfo import ZoneInfo

swiss_tz = ZoneInfo("Europe/Zurich")
current_hour = datetime.datetime.now(swiss_tz).hour

# API date queries
today = datetime.date.today()  # Uses system TZ (now set correctly)
```

**Detection:**
- Container `date` command shows UTC
- Application logs show UTC timestamps
- Scheduled behavior triggers at offset hours
- API "today" data is from yesterday/tomorrow

**Phase to address:** Phase 1 (Docker Foundation) - Set during initial containerization.

---

### Pitfall 11: Waveshare Library Not Finding Font Files in Container
**What goes wrong:** Application starts but crashes when rendering display with "IOError: cannot open resource" for font files (Arial.ttf, FontAwesome6-Free-Solid-900.otf).

**Why it happens:**
- Font paths use `os.getcwd()` which differs in container (lines 53-54)
- Fonts directory not copied to Docker image
- Relative paths break when working directory changes
- Dockerfile sets `WORKDIR` but fonts aren't there

**Consequences:**
- Display rendering fails completely
- Hard to debug (works in development)
- Error message cryptic (font file path)
- Can't display any screens

**Prevention:**
```dockerfile
# Dockerfile
WORKDIR /app

# Copy fonts directory
COPY fonts/ /app/fonts/

# Verify fonts are present
RUN ls -la /app/fonts/ && \
    test -f /app/fonts/Arial.ttf && \
    test -f /app/fonts/ArialBlack.ttf && \
    test -f /app/fonts/FontAwesome6-Free-Solid-900.otf
```

```python
# Fix font path code (lines 53-54)
import os
from pathlib import Path

# Use __file__ not getcwd() for reliable path
BASE_DIR = Path(__file__).parent
FONTS_DIR = BASE_DIR / "fonts"

icon_path = FONTS_DIR / "FontAwesome6-Free-Solid-900.otf"
font_path_bold = FONTS_DIR / "ArialBlack.ttf"
font_path = FONTS_DIR / "Arial.ttf"

# Validate fonts exist at startup
for font_file in [icon_path, font_path_bold, font_path]:
    if not font_file.exists():
        raise FileNotFoundError(f"Required font missing: {font_file}")
```

**Detection:**
- Error: "cannot open resource"
- Traceback shows ImageFont.truetype() call
- `ls /app/fonts` inside container returns empty
- Works on host, fails in container

**Phase to address:** Phase 1 (Docker Foundation) - Fix during initial containerization.

---

### Pitfall 12: Container Networking Breaks SSH to Time Machine
**What goes wrong:** Code successfully retrieves SolarEdge/WeConnect/BMW data, but fails when SSH'ing to Time Machine server (line 256-284) with "No route to host" or "Connection refused."

**Why it happens:**
- Container network is isolated by default
- Time Machine is on local network (timemachine.local)
- Container can't resolve `.local` mDNS hostnames
- Docker bridge network doesn't route to local LAN
- Paramiko tries IPv6 before IPv4 (can timeout)

**Consequences:**
- Display 4 (Time Machine disk usage) never works
- Timeout adds delay to display cycle (30s default SSH timeout)
- Other displays work fine (confusing failure)
- Network error but other network calls succeed

**Prevention:**
```yaml
# config/deploy.yml - Use host network mode
docker:
  options:
    network: host  # Container uses host's network directly
```

**Alternative (if host network not desired):**
```python
# Replace mDNS hostname with IP address
hostname = os.environ.get('TIMEMACHINE_HOST', '192.168.1.50')  # Static IP

# Or add timeout to avoid long hangs
ssh.connect(hostname, username=username, password=password, timeout=5)
```

**Detection:**
- SSH connection hangs then times out
- Error: "getaddrinfo failed" for `.local` hostname
- Can ping Time Machine from Pi host, not from container
- Other network calls (HTTPS APIs) work fine

**Phase to address:** Phase 2 (Deployment Strategy) - Test after basic containerization.

---

### Pitfall 13: E-Ink Display Ghosting from Incomplete Updates
**What goes wrong:** Display shows faint "ghost" of previous image overlaid on current image, or partial screen clears leave artifacts.

**Why it happens:**
- E-ink displays require full refresh cycles to prevent ghosting
- Partial updates (faster) don't clear previous image fully
- Code uses `epd.Clear(0xFF)` but not enough refresh cycles
- Display power cycled before full clear completes
- Container restart during multi-second update operation

**Consequences:**
- Display becomes harder to read over time
- "Burnt in" images visible
- Users assume display is broken
- Requires full power cycle to clear

**Prevention:**
```python
def display_with_full_refresh(image_func):
    """Wrapper to ensure full refresh cycle"""
    try:
        epd = epd2in13_V3.EPD()
        epd.init()

        # Full clear before new image (prevents ghosting)
        epd.Clear(0xFF)
        time.sleep(1)  # Let clear settle

        # Display new image
        image_func(epd)

        # Optional: Add periodic deep refresh (every 10 updates)
        if should_deep_refresh():
            epd.init()  # Re-init forces full refresh
            epd.Clear(0xFF)
            time.sleep(2)
            image_func(epd)
    finally:
        epd.sleep()  # Always sleep display
```

**Detection:**
- Visible "ghost" images on display
- Display becomes less crisp over time
- Black areas appear gray
- Previous numbers visible behind current numbers

**Phase to address:** Phase 3 (Polish) - After basic display functionality works.

---

## Minor Pitfalls

These cause annoyance but are easily fixable.

### Pitfall 14: Kamal Volume Mounts for Persistent Data
**What goes wrong:** Each deployment wipes debug logs, cached API responses, and any persistent state.

**Why it happens:**
- Kamal creates fresh containers on each deploy
- Container filesystem is ephemeral
- Debug directory (line 21) exists in container, not mounted
- No volume configuration in deploy.yml

**Consequences:**
- Can't view historical logs
- Debug data lost on deploy
- Cache (from Pitfall 7 fix) doesn't persist
- Can't troubleshoot intermittent issues

**Prevention:**
```yaml
# config/deploy.yml
volumes:
  - solaredge-data:/app/data
```

```dockerfile
# Dockerfile
RUN mkdir -p /app/data/debug /app/data/cache
VOLUME /app/data
```

```python
# Update paths to use persistent volume
debugdir = "/app/data/debug"
CACHE_DIR = "/app/data/cache"
```

**Detection:**
- Debug files missing after deploy
- Can't find historical API responses
- Each deploy starts "fresh" with no state

**Phase to address:** Phase 2 (Deployment Strategy) - Add when debugging production issues.

---

### Pitfall 15: Docker Build Context Includes Large Unnecessary Files
**What goes wrong:** `kamal deploy` uploads 100+ MB to Pi, build takes forever, times out.

**Why it happens:**
- Current repo has `debug/` directory with logs
- `display/` directory with generated images
- `.git` directory (especially in fresh repo)
- `__pycache__`, `*.pyc` files
- Docker includes everything not in `.dockerignore`

**Consequences:**
- Deploy command hangs at "Uploading context"
- Slow builds (especially over WiFi to Pi)
- Large Docker images
- Network timeouts during upload

**Prevention:**
```dockerignore
# .dockerignore
.git
.gitignore
debug/
display/
**/__pycache__
**/*.pyc
**/*.pyo
**/*.pyd
.DS_Store
*.md
.vscode
.idea
```

**Detection:**
- `docker build` shows "Sending build context" >50MB
- Deploy hangs at context upload
- Image size >500MB
- Build output includes "debug/" files

**Phase to address:** Phase 1 (Docker Foundation) - Create `.dockerignore` during Dockerfile creation.

---

### Pitfall 16: Async Code (BMW API) in Sync Container Runtime
**What goes wrong:** BMW API call (line 338: `asyncio.run(account.get_vehicles())`) causes warnings or event loop errors in long-running container.

**Why it happens:**
- Code mixes async (`asyncio.run()`) with sync main loop
- Running `asyncio.run()` in already-running event loop fails
- BMW library (`bimmer_connected`) requires async context
- Works in script, problematic in long-running process

**Consequences:**
- RuntimeError: "This event loop is already running"
- BMW display works sometimes, fails other times
- Warnings about coroutines not awaited
- Unpredictable behavior

**Prevention:**
```python
# Option 1: Make main loop async
async def main():
    while True:
        current_hour = dt.datetime.now().hour
        if 6 <= current_hour < 24:
            for func in functions:
                result = await func() if asyncio.iscoroutinefunction(func) else func()
                time.sleep(sleep_timer)
        else:
            await asyncio.sleep(sleep_timer)

if __name__ == "__main__":
    asyncio.run(main())
```

```python
# Option 2: Run async calls in separate thread
import asyncio
from concurrent.futures import ThreadPoolExecutor

def get_bmw_state_of_charge_sync():
    """Sync wrapper for async BMW API"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(get_bmw_state_of_charge())
    finally:
        loop.close()
```

**Detection:**
- Warnings about event loops
- RuntimeError when calling BMW API
- Works first time, fails on subsequent calls
- Container logs show asyncio errors

**Phase to address:** Phase 3 (Refinement) - After basic container operation works.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Repo Migration | Pitfall 6: Credentials committed to fresh repo | First task: setup .gitignore, env vars |
| Docker Foundation | Pitfall 1: Missing device passthrough | Test hardware access in container before any other work |
| Docker Foundation | Pitfall 2: Wrong ARM architecture | Verify architecture on target Pi, specify in FROM |
| Docker Foundation | Pitfall 7: API rate limiting | Implement caching from day 1 |
| Docker Foundation | Pitfall 11: Font paths broken | Fix relative paths before testing display |
| Deployment Config | Pitfall 8: SSH connection issues | Use static IP, verify SSH before Kamal |
| Deployment Config | Pitfall 5: No graceful shutdown | Add signal handlers before deploying regularly |
| Testing | Pitfall 4: SPI not enabled | Document Pi setup prerequisites |
| Production | Pitfall 13: Display ghosting | Monitor for visual degradation |

---

## Domain-Specific Warning Signs

**Red flags that indicate you're heading for a pitfall:**

1. "It works locally but not in Docker" - Check Pitfall 1, 3, 11
2. "Container starts then immediately exits" - Check Pitfall 2
3. "Deployment succeeds but display never updates" - Check Pitfall 1, 4
4. "API calls work fine in development" - Check Pitfall 7
5. "Everything works on Pi 4, fails on Pi 3" - Check Pitfall 2
6. "Fresh repo but git warns about large commit" - Check Pitfall 6
7. "Build takes >15 minutes" - Check Pitfall 9, 15
8. "Display shows wrong times" - Check Pitfall 10
9. "Deployment flaky, works sometimes" - Check Pitfall 8
10. "Display looks 'muddy' or ghosted" - Check Pitfall 13

---

## Testing Checklist (Avoid Pitfalls Before Production)

Before declaring deployment "done," verify:

- [ ] `/dev/spidev0.0` visible inside running container (`docker exec <container> ls /dev/spi*`)
- [ ] Display updates successfully from inside container
- [ ] Container survives restart without hitting API rate limit
- [ ] Architecture matches Pi OS (`docker inspect` shows correct platform)
- [ ] SPI enabled on Pi (`ls /dev/spidev*` on host)
- [ ] Fonts load successfully (check logs for font errors)
- [ ] All API calls succeed from container
- [ ] Time zone correct (`docker exec <container> date`)
- [ ] SSH to Time Machine works from container
- [ ] Graceful shutdown clears display properly
- [ ] Debug/cache directories persist across deploys
- [ ] Build context <50MB (`docker build` output)
- [ ] No credentials in git history (`git log --all -- "*password*"`)
- [ ] .env file NOT committed (`git status`)

---

## Sources

**Confidence Assessment:**

| Source Type | Examples | Confidence Level |
|-------------|----------|------------------|
| Direct code analysis | se-overview.py, epdconfig.py | HIGH |
| Training knowledge | Docker device passthrough, SPI, ARM architecture | MEDIUM |
| Known patterns | Kamal deployment, Raspberry Pi GPIO | MEDIUM |
| Inferred from context | SolarEdge API limits, e-ink ghosting | MEDIUM-LOW |

**Note on research limitations:**
- WebSearch tools not available during research (permission denied)
- Context7 not available (permission denied)
- Analysis based on:
  - Existing project code (se-overview.py, epdconfig.py)
  - Training knowledge of Docker, Raspberry Pi, Kamal (as of Jan 2025)
  - Common pitfall patterns in similar projects

**Recommended validation steps:**
1. Verify SolarEdge API rate limits in official documentation
2. Check Kamal's latest documentation for ARM/Pi-specific guidance
3. Consult Waveshare e-ink display technical specs for refresh cycle recommendations
4. Test each pitfall prevention strategy in actual deployment environment

---

## Research Metadata

**Knowledge cutoff note:** This research was conducted with training data current to January 2025. Kamal, Docker, and Raspberry Pi OS are actively developed. Verify version-specific behavior for:
- Kamal 2.x deployment configuration format
- Docker Compose v2 device passthrough syntax
- Raspberry Pi OS Bookworm SPI configuration
- SolarEdge API v1 rate limits and endpoints

**Confidence in specific claims:**
- Device passthrough requirement: HIGH (fundamental Docker limitation)
- ARM architecture issues: HIGH (verified in provided epdconfig.py code)
- SPI enable requirement: HIGH (standard Raspberry Pi configuration)
- SolarEdge rate limits: MEDIUM (common in free tier APIs, needs verification)
- Kamal SSH behavior: MEDIUM (based on Kamal v1 knowledge, may have changed)
- E-ink ghosting: MEDIUM (physics of e-ink displays, but model-specific)

**Where research would benefit from verification:**
- Exact SolarEdge API daily rate limit (claimed 300, may vary by account type)
- Kamal 2.x volume mount syntax (if version changed since training)
- Raspberry Pi 5 GPIO device paths (new hardware post-training)
- Best practices for bimmer_connected library in long-running processes
