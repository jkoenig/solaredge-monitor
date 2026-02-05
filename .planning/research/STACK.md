# Technology Stack

**Project:** SolarEdge Off-Grid Monitor (Containerized Refactor)
**Research Date:** 2026-02-04
**Research Confidence:** MEDIUM (based on training data, unable to verify with Context7/WebSearch)

## Executive Summary

**Target:** Modernize existing Python 3.9 monolithic script into containerized application with clean architecture, deployed via Kamal to Raspberry Pi with Waveshare e-ink display.

**Critical Constraint:** GPIO/SPI hardware access from Docker container on ARM architecture.

**Recommended Approach:** Python 3.11+ on Alpine-based ARM image with privileged container mode for hardware access, uv for dependency management, Pydantic for configuration, httpx for async API calls.

## Recommended Stack

### Core Runtime

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **Python** | 3.11+ | Runtime environment | **Use 3.11**: Stable on Raspberry Pi OS, faster than 3.9 (10-60% speedup), better error messages. **Avoid 3.13**: Too new for Raspberry Pi ecosystem (released Oct 2024), may have library compatibility issues with waveshare_epd. Python 3.12 is safe alternative. **HIGH confidence in 3.11-3.12 range.** |
| **Docker** | 24.x+ | Containerization | Standard container runtime. Raspberry Pi OS supports Docker natively. Must run with `--privileged` flag for GPIO/SPI access. **HIGH confidence.** |
| **Kamal** | 1.x | Deployment orchestration | SSH-based deployment, designed for single-server scenarios. Simpler than Kubernetes for single Pi. **MEDIUM confidence** - verify Kamal supports ARM/Pi explicitly. |

### Dependency Management

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **uv** | latest | Package management | **RECOMMENDED over pip/poetry/pipenv**: 10-100x faster installs, native Rust implementation, handles virtual envs + lockfiles. Single binary, no bootstrap issues in containers. **As of training cutoff (Jan 2025)**, uv is production-ready and rapidly becoming standard. **MEDIUM confidence** - verify current version supports ARM. |
| **pyproject.toml** | standard | Dependency declaration | PEP 621 standard, replaces requirements.txt/setup.py. Works with uv, pip, poetry. **HIGH confidence.** |

**Alternative:** `pip-tools` (compile requirements.txt.in → requirements.txt) if uv ARM support is problematic. More mature, slower.

### HTTP Client

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **httpx** | 0.27+ | REST API client | **RECOMMENDED over requests**: Async support (future-proof), HTTP/2, timeout defaults, modern API. Can drop to sync mode (`httpx.Client()`) for compatibility with current code. Same API surface as requests, easy migration. **MEDIUM confidence** - version may be outdated. |
| **requests** | 2.31+ | REST API client (fallback) | **KEEP if migration cost too high**: Proven, stable, widely supported. But synchronous-only, no HTTP/2. Fine for MVP refactor. **HIGH confidence.** |

**Recommendation:** Start with httpx in sync mode. Refactor to async later if needed.

### Configuration Management

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **pydantic-settings** | 2.x | Environment-based config | **REQUIRED for clean architecture**: Type-safe settings from env vars, validation, IDE autocomplete. Replaces hardcoded credentials. Integrates with Pydantic models. **HIGH confidence on concept, LOW confidence on version.** |
| **python-dotenv** | 1.x | .env file loading | Load `.env` files for local dev. Pydantic-settings has built-in support. **MEDIUM confidence.** |

### Image Processing

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **Pillow** | 10.x+ | Image rendering | **KEEP**: Standard for Python image manipulation. Already in use. Supports font rendering for e-ink display. Verify ARM wheel availability. **HIGH confidence on choice, LOW confidence on version.** |

### Hardware Interface

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **waveshare_epd** | latest | E-ink display driver | **KEEP**: Vendor-provided driver for Waveshare displays. No alternatives. Uses spidev and RPi.GPIO internally. **HIGH confidence on necessity.** |
| **spidev** | latest | SPI interface | Transitive dependency via waveshare_epd. Must be accessible from container. **HIGH confidence.** |
| **RPi.GPIO** | latest | GPIO interface | Transitive dependency via waveshare_epd. Requires privileged container. **HIGH confidence.** |

**Critical:** Hardware access requires Docker container to run with:
- `--privileged` flag OR
- `--device /dev/spidev0.0 --device /dev/gpiomem` (more secure)

### Testing & Code Quality

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **pytest** | 8.x+ | Test framework | Standard Python testing. Async support for httpx. **MEDIUM confidence.** |
| **pytest-mock** | 3.x+ | Mocking for tests | Mock hardware interfaces in tests. **MEDIUM confidence.** |
| **ruff** | 0.x | Linting + formatting | **RECOMMENDED over black+flake8+isort**: All-in-one tool, 10-100x faster (Rust), auto-fix. Replaces multiple tools. **As of training**, ruff is rapidly becoming standard. **MEDIUM confidence.** |
| **mypy** | 1.x+ | Type checking | Static type checking. Use with Pydantic models. **MEDIUM confidence.** |

**Alternative:** `black` + `isort` + `flake8` if ruff ARM support is problematic.

### Logging & Observability

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **structlog** | 24.x+ | Structured logging | **RECOMMENDED over stdlib logging**: JSON logs, context binding, better for container environments. **MEDIUM confidence on version.** |
| Standard `logging` | stdlib | Logging (fallback) | Fine for simple use case. Less features. **HIGH confidence.** |

**Recommendation:** Use structlog for production, stdlib logging acceptable for MVP refactor.

## Docker Base Image

### Recommended: `python:3.11-slim-bookworm` (Debian-based)

```dockerfile
FROM python:3.11-slim-bookworm
```

**Rationale:**
- **Debian Bookworm**: Matches Raspberry Pi OS 12 base (compatibility)
- **Slim**: Smaller than full image (~150MB vs ~1GB)
- **Python 3.11**: Stable, fast, good library support
- **ARM64 support**: Official Python images have multi-arch manifests

**Pros:**
- Official Python image
- Good package availability (apt)
- Matches Pi OS ecosystem

**Cons:**
- Larger than Alpine (~150MB vs ~50MB)
- Slower build times

### Alternative: `python:3.11-alpine3.19` (Alpine-based)

```dockerfile
FROM python:3.11-alpine3.19
```

**Rationale:**
- **Smaller**: ~50MB base
- **Faster startup**: Less to load
- **Security**: Minimal attack surface

**Pros:**
- Smallest image size
- Faster container start

**Cons:**
- **RISK for this project**: Alpine uses musl libc, not glibc. Some Python packages (especially with C extensions) may have wheel compatibility issues.
- Pillow, spidev, RPi.GPIO may require compilation from source (slow ARM builds)
- More debugging if dependencies break

**Recommendation:** Start with `python:3.11-slim-bookworm`. Optimize to Alpine later if image size becomes issue.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| **Python Version** | 3.11 | **3.13** | Too new, library ecosystem lag, waveshare_epd may not support |
| | | **3.9** (current) | Slower, missing features (better error messages, match statements) |
| | | **3.12** | Safe alternative, slightly newer than 3.11 |
| **Package Manager** | uv | **poetry** | Slower, more complex, overkill for this project |
| | | **pipenv** | Slower, less maintained, deprecated by some |
| | | **pip + pip-tools** | Mature fallback if uv has ARM issues |
| **HTTP Client** | httpx | **aiohttp** | Async-only, no sync fallback, less requests-like API |
| | | **requests** | Fine fallback, proven, but no async/HTTP/2 |
| **Config** | pydantic-settings | **python-decouple** | Less validation, no type safety |
| | | **environs** | Less integrated with Pydantic ecosystem |
| **Linter** | ruff | **black + flake8 + isort** | 3 tools instead of 1, slower |
| **Base Image** | python:3.11-slim-bookworm | **python:3.11-alpine** | musl libc issues with C extensions |
| | | **balenalib/raspberry-pi-python** | Vendor lock-in, less maintained |
| **Deployment** | Kamal | **Docker Compose** | Manual, no zero-downtime, no rollback |
| | | **Kubernetes** | Massive overkill for single Pi |

## Hardware Access Configuration

### Docker Run Flags

**Privileged Mode (simplest):**
```bash
docker run --privileged -v /dev:/dev myapp
```

**Pros:** Works reliably for GPIO/SPI
**Cons:** Full root access, security concern (mitigated by single-user Pi)

**Device-Specific Mode (more secure):**
```bash
docker run \
  --device /dev/spidev0.0:/dev/spidev0.0 \
  --device /dev/gpiomem:/dev/gpiomem \
  myapp
```

**Pros:** Minimal permissions
**Cons:** May need additional devices, more debugging

**Recommendation:** Start with `--privileged` for MVP refactor. Tighten to device-specific after confirming it works.

### Kamal Configuration Considerations

```yaml
# config/deploy.yml (conceptual)
service: solaredge-monitor
image: <registry>/solaredge-monitor
servers:
  - <raspberry-pi-ip>

# CRITICAL: Hardware access flags
accessories:
  - docker_options:
      - "--privileged"
      - "-v /dev:/dev"

# ARM build
builder:
  arch: arm64
```

**Key points:**
1. Kamal must pass `--privileged` flag to Docker
2. Build for ARM64 architecture (cross-compile or build on Pi)
3. Single-server deployment (no load balancing)
4. Consider health check for display rendering

**MEDIUM confidence** - verify Kamal 1.x syntax for privileged mode and ARM deployment.

## Installation & Setup

### Development (on Pi or ARM Mac)

```bash
# Install uv (if ARM supported)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create project
cd /path/to/solaredge-offgrid-monitor
uv init  # Creates pyproject.toml

# Add dependencies
uv add httpx pillow pydantic-settings python-dotenv
uv add --dev pytest pytest-mock ruff mypy

# Run
uv run python -m solaredge_monitor
```

### Production (Docker)

```dockerfile
FROM python:3.11-slim-bookworm

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application
COPY . .

# Run
CMD ["uv", "run", "python", "-m", "solaredge_monitor"]
```

### Kamal Deployment

```bash
# Setup (one-time)
kamal setup

# Deploy
kamal deploy

# Rollback if issues
kamal rollback
```

## Dependency Lock Files

### With uv

```toml
# pyproject.toml
[project]
name = "solaredge-monitor"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27.0",
    "pillow>=10.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    # Add waveshare_epd if available on PyPI, else install separately
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.12.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
]
```

Run `uv lock` to generate `uv.lock` file (commit to git).

### Fallback with pip-tools

```
# requirements.in
httpx>=0.27.0
pillow>=10.0.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0

# Generate requirements.txt
pip-compile requirements.in
```

## Critical Dependencies Notes

### waveshare_epd

**Status:** May not be on PyPI. Often installed from GitHub or included in project.

**Options:**
1. Copy vendor code into project (`src/waveshare_epd/`)
2. Install from GitHub: `uv add git+https://github.com/waveshare/e-Paper.git#subdirectory=RaspberryPi_JetsonNano/python`
3. Manual pip install in Dockerfile

**Recommendation:** Check if waveshare_epd is pip-installable. If not, vendor the code (copy into project) for clean container builds.

### RPi.GPIO Alternative: lgpio

**Context:** RPi.GPIO development has slowed. `lgpio` is newer, actively maintained.

**Compatibility:** Check if waveshare_epd supports lgpio. If not, stick with RPi.GPIO.

**Not recommended** for refactor phase - introduces too much change. Consider for future optimization.

## Migration Path from Current Stack

### Current (Python 3.9 monolith)
```
requirements.txt:
- Pillow
- requests
- waveshare_epd (vendored?)
```

### Phase 1: Modernize Dependencies (no architecture change)
```
pyproject.toml:
- httpx (drop-in for requests, sync mode)
- Pillow
- pydantic-settings (replace hardcoded config)
- waveshare_epd
```

### Phase 2: Containerize
```dockerfile
FROM python:3.11-slim-bookworm
# Add uv, dependencies, app code
```

### Phase 3: Kamal Deployment
```yaml
# config/deploy.yml with --privileged flag
```

**Rationale for incremental approach:** Test each layer before adding next. Ensures GPIO access works before Kamal complexity.

## Version Verification Notes

**CONFIDENCE ASSESSMENT:**

| Technology | Confidence | Reason |
|------------|------------|--------|
| Python 3.11 | HIGH | Stable, well-supported on Raspberry Pi |
| uv | MEDIUM | Rapidly maturing, verify ARM support |
| httpx | MEDIUM | Version may be outdated, verify latest |
| pydantic-settings | MEDIUM | Version 2.x exists, verify current |
| Pillow | MEDIUM | Major version may have changed |
| Docker flags | HIGH | Privileged mode is standard for GPIO |
| Kamal syntax | LOW | Unable to verify 1.x ARM/privileged config |
| ruff | MEDIUM | Fast-moving project, verify ARM support |

**VERIFICATION NEEDED:**
1. uv ARM64 support status (check astral.sh/uv docs)
2. httpx current version and breaking changes
3. pydantic-settings 2.x current API
4. Kamal 1.x privileged mode syntax
5. waveshare_epd installation method (PyPI vs GitHub vs vendored)

## Anti-Recommendations

### DO NOT USE

| Technology | Why Avoid |
|------------|-----------|
| **Python 3.13** | Too new for Raspberry Pi ecosystem, library compatibility risk |
| **Python <3.10** | Missing modern features (match, better errors), slower |
| **Alpine base image** | musl libc breaks many wheels, slow ARM compilation of C extensions |
| **Kubernetes** | Massive overkill for single Pi, complex, resource-intensive |
| **Poetry 1.x** | Slower than uv, more complex configuration |
| **aiohttp** | Async-only, harder migration from current sync code |
| **Configparser/os.getenv** | No validation, no type safety, manual parsing |
| **Docker Compose** | No deployment orchestration, manual updates, no rollback |

### DO NOT

- Run container in host network mode (`--network host`) - breaks container isolation
- Use `latest` tags in production - breaks reproducibility
- Install system packages in Dockerfile without pinning versions
- Skip the lockfile (uv.lock or requirements.txt) - non-reproducible builds
- Mount entire `/dev` without `--privileged` - permission errors

## Build Optimization

### Multi-Stage Build (production Dockerfile)

```dockerfile
# Stage 1: Build dependencies
FROM python:3.11-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.11-slim-bookworm
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY . .
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "solaredge_monitor"]
```

**Benefit:** Smaller final image, faster rebuilds.

### ARM Build Strategy

**Option 1: Build on Raspberry Pi**
```bash
# SSH to Pi, build locally
docker build -t solaredge-monitor:latest .
```
**Pros:** Native ARM, no cross-compilation
**Cons:** Slow Pi CPU, long build times

**Option 2: Cross-compile from x86 Mac/PC**
```bash
# Use buildx for multi-arch
docker buildx build --platform linux/arm64 -t solaredge-monitor:latest .
```
**Pros:** Fast build machine
**Cons:** Requires QEMU, slower than native

**Recommendation:** Build on Pi for MVP. Move to CI/CD with cross-compilation later.

## Sources

**PRIMARY SOURCES (verified during research):**
- None (tool access denied, based on training data)

**TRAINING DATA (as of January 2025):**
- Python 3.11/3.12 Raspberry Pi compatibility
- Docker privileged mode for GPIO access
- uv package manager (Astral)
- httpx HTTP client library
- Pydantic v2 settings management
- Kamal deployment tool (37signals/Basecamp)
- Ruff linter/formatter
- Waveshare e-Paper display drivers

**UNVERIFIED CLAIMS:**
- Specific version numbers (httpx 0.27, pydantic-settings 2.x, etc.)
- uv ARM64 support status
- Kamal 1.x privileged mode syntax
- Current Python version compatibility with Raspberry Pi OS

**RECOMMENDATION:** Verify all version numbers and ARM compatibility before implementing.

## Next Steps

1. **Verify versions:** Check Context7 or official docs for current versions of:
   - httpx
   - pydantic-settings
   - uv (ARM support)
   - ruff (ARM support)

2. **Test hardware access:** Build minimal Docker container with waveshare_epd, test `--privileged` vs device-specific flags

3. **Kamal ARM testing:** Verify Kamal can deploy to ARM Pi with privileged mode

4. **Dependency audit:** Confirm waveshare_epd installation method (PyPI vs vendored)

5. **Benchmark:** Compare uv vs pip-tools build times on Raspberry Pi

---

**Research Complete:** Stack recommendations provided with confidence levels. Ready for roadmap creation, but version verification required before implementation.
