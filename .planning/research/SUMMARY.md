# Project Research Summary

**Project:** SolarEdge Off-Grid Monitor (Containerized Refactor)
**Domain:** Containerized Raspberry Pi IoT monitoring with hardware access
**Researched:** 2026-02-04
**Confidence:** MEDIUM

## Executive Summary

This project transforms a monolithic 828-line Python script into a production-grade containerized application for Raspberry Pi hardware. The challenge is unique: it combines hardware access constraints (GPIO/SPI for e-ink display), ARM architecture deployment, third-party API integration (SolarEdge, BMW, VW), and Kamal-based deployment orchestration.

The recommended approach is evolutionary, not revolutionary. Maintain Python 3.11+ with modern tooling (uv, httpx, pydantic-settings), adopt layered architecture for testability, and embrace Docker with hardware abstraction. The critical insight from research: Docker's isolation model directly conflicts with hardware access requirements, making device passthrough configuration the make-or-break decision for this entire refactoring.

Key risks center on containerization pitfalls unique to Raspberry Pi hardware projects. Missing device passthrough causes silent failures. ARM architecture mismatches produce cryptic errors. API rate limiting during development blocks progress. E-ink display characteristics demand careful UI design for the tiny 250x122 pixel screen. The mitigation strategy is front-load verification testing (Phase 1 validates Docker hardware access before any feature work) and implement fail-safe patterns throughout (cache API responses, graceful degradation when data sources fail).

## Key Findings

### Recommended Stack

The stack modernizes dependencies while maintaining compatibility with Raspberry Pi ARM hardware and existing SolarEdge/BMW/VW APIs. Critical constraint: all choices must support ARM64/ARMv7 architectures and allow GPIO/SPI access from Docker containers.

**Core technologies:**
- **Python 3.11 on Debian Bookworm**: Stable on Pi OS, 10-60% faster than current 3.9, matches Pi OS base for library compatibility. Avoid Alpine (musl libc breaks C extension wheels).
- **uv package manager**: 10-100x faster than pip/poetry, single binary, native lockfiles. Fallback to pip-tools if ARM support problematic.
- **Docker with privileged mode**: Mandatory for SPI/GPIO device access. Use `--device /dev/spidev0.0 --device /dev/gpiomem` flags or full `--privileged`.
- **Kamal 1.x deployment**: SSH-based orchestration designed for single-server scenarios. Simpler than Kubernetes, perfect for single Pi.
- **httpx HTTP client**: Drop-in replacement for requests with async support (future-proof) and modern API. Start in sync mode for easy migration.
- **Pydantic-settings**: Type-safe environment variable config, replaces hardcoded credentials. Essential for clean architecture.
- **Pillow + Waveshare EPD**: Keep existing image rendering stack. Verify ARM wheel availability. Waveshare library is vendor-specific with no alternatives.

**Critical version notes:**
- Python 3.13 too new (library ecosystem lag for Pi)
- Alpine base image risky (C extension compilation issues)
- Verify uv ARM64 support before committing to it

### Expected Features

Solar energy monitors must balance information density with readability on constrained e-ink displays. For 250x122 pixels (31,000 total pixels), the imperative is brutal prioritization: show 3-4 key metrics clearly rather than 10 metrics poorly.

**Must have (table stakes):**
- Current solar power production (kW) - "How much am I generating right now?"
- Battery state of charge (%) - Critical for off-grid systems
- Grid connection status (on/off-grid) - Essential safety information
- Current consumption (kW) - "How much am I using?"
- Daily production total (kWh) - Achievement metric
- Timestamp/last update - Trust that data is current

**Should have (differentiators):**
- Large readable fonts (32-48px for primary metrics) - Glanceable from 1-2 meters
- Icon-based status indicators - Universal understanding, language-agnostic
- Single comprehensive screen - Replaces confusing 4-screen cycling approach
- Trend indicators (up/down arrows) - Show direction without historical graphs
- Status-at-a-glance layout - Answer "Is everything working?" in <5 seconds

**Defer (v2+ / anti-features for small e-ink):**
- Graphs/charts - 250x122 too small for readable visualization
- Historical data displays - Focus on "right now" and "today total"
- Weather forecasting - Scope creep, not core to monitoring
- Cost/savings calculations - Requires electricity rates, currency complexity
- VW/BMW vehicle integrations - Removing per project scope (defer to separate project)
- Time Machine disk monitoring - Removing per project scope

**Key recommendation from features research:** Shift from 4-screen rotation to single comprehensive screen. Rationale: 5-minute update cycle means cycling wastes 3.75 minutes showing non-current screen. User doesn't know which screen they'll see when checking. Single view answers all questions immediately.

### Architecture Approach

Layered architecture transforms monolith into modular system with clear separation of concerns: Data Sources (API clients) → Business Models (domain objects) → Layouts (screen specifications) → Renderer (PIL image generation) → Hardware Driver (e-ink abstraction). This enables testing without hardware, parallel development of components, and graceful degradation when data sources fail.

**Major components:**

1. **Config Loader** - Pydantic-based environment variable loading with validation. Replaces hardcoded credentials (critical security fix). Fails fast with clear error messages if required env vars missing.

2. **Data Sources** - Plugin-based system with abstract base class. Each source (SolarEdge, BMW, VW, Time Machine) implements fetch() method returning domain models. Fail-safe: returns None on error rather than crashing application. Enables async concurrent fetching for future optimization.

3. **Layout Engine** - Separates WHAT to display from HOW to render it. Layouts convert domain models into LayoutSpec objects (positions, text, fonts). Renderer converts LayoutSpec to PIL Image. This decoupling allows testing layouts without image rendering and vice versa.

4. **Hardware Abstraction** - Display interface with two implementations: WaveshareDisplay (real hardware via SPI) and MockDisplay (saves to file for testing). Factory function selects implementation based on config. Enables development without physical Pi.

5. **Orchestrator** - Main application loop coordinates: check active hours (6am-midnight) → fetch data from all sources → select layout → render → display → sleep. Handles rotation logic and graceful shutdown (clears display on SIGTERM to prevent e-ink ghosting).

**Key architectural decisions:**
- Dependency injection throughout (no global state)
- Fail-safe data sources (failures don't crash app)
- Hardware abstraction (develop/test without device)
- Docker privileged mode (only way to access GPIO/SPI reliably)

**Package structure:** 7 top-level modules (config, datasources, models, layouts, rendering, hardware, orchestrator) with clear dependencies flowing Data → Business → Presentation → Hardware. Tests mirror structure with fixtures for API responses.

### Critical Pitfalls

Based on code analysis and domain expertise, five pitfalls pose existential risk to project success:

1. **Missing Device Passthrough** - Container starts successfully but display never updates. Kamal's default config doesn't include `/dev/spidev0.0` device access. Application appears to run but GPIO calls fail silently. Prevention: Configure `docker.options.devices` in deploy.yml from day 1. Address in Phase 1 (Docker Foundation) before any deployment work.

2. **ARM Architecture Mismatch** - Image builds on macOS but exits immediately on Pi with "exec format error". Raspberry Pi can run 32-bit OS on 64-bit hardware. Multi-arch manifests select wrong platform. Prevention: Explicitly specify `FROM --platform=linux/arm/v7` in Dockerfile. Verify Pi architecture first (`uname -m`). Address in Phase 1 before any deployment testing.

3. **Hardcoded Credentials in Fresh Repo** - Fresh repo migration immediately contaminated if code still has hardcoded values (lines 32-44 of current script). Muscle memory leads to commit before implementing env vars. Prevention: FIRST TASK in fresh repo is create .gitignore, implement environment variable loading, never commit actual values. Address in Phase 0 (Repo Setup).

4. **SolarEdge API Rate Limiting** - Free tier allows 300 calls/day. Container restart = fresh API call. Debug cycle (10+ restarts/hour × 3 API calls = 30 calls, exhausts limit by afternoon). Prevention: Implement response caching with 3-minute expiry, persist cache across container restarts. Address in Phase 1 before deployment testing begins.

5. **No Graceful Shutdown** - Kamal stops container mid-display-update. E-ink left in corrupted state (partial image, ghosting). Requires manual power cycle to clear. Prevention: Register SIGTERM handler to clear display and sleep hardware before exit. Configure 10s stop grace period in Kamal. Address in Phase 2 (Deployment Strategy).

**Additional moderate pitfalls:**
- GPIO library incompatibility inside containers (use spidev/gpiozero, avoid RPi.GPIO)
- SPI interface disabled by default in Pi OS (run `raspi-config nonint do_spi 0`)
- Font paths break in container (use `__file__` not `getcwd()` for reliable paths)
- Async code (BMW API) in sync runtime (make main loop async or use ThreadPoolExecutor)

## Implications for Roadmap

Based on research, the refactoring must be incremental and front-load risk verification. The architecture is sound but hardware access is the lynchpin - everything depends on Docker container successfully talking to SPI/GPIO.

### Suggested Phase Structure

**Phase 1: Docker Foundation & Hardware Verification**
**Rationale:** Validate make-or-break assumptions before investing in architecture. If Docker can't access e-ink display, entire containerization approach fails.

**Delivers:**
- Working Dockerfile (Python 3.11, ARM architecture specified)
- Device passthrough configuration (SPI/GPIO access)
- Mock display implementation (testing without hardware)
- Minimal "hello world" image rendering to physical e-ink
- API response caching (prevent rate limit exhaustion)
- Environment variable configuration (no hardcoded credentials)

**Addresses pitfalls:**
- Pitfall 1: Device passthrough tested and verified
- Pitfall 2: ARM architecture confirmed working on target Pi
- Pitfall 3: Fresh repo setup with .gitignore BEFORE any commits
- Pitfall 4: Caching implemented before deployment iteration begins
- Pitfall 11: Font paths fixed to use absolute references

**Stack elements:** Python 3.11-slim-bookworm, uv/pip-tools, Pillow, waveshare_epd, pydantic-settings

**Success criteria:** E-ink display updates from inside Docker container. Cache persists across container restarts. No credentials in git.

---

**Phase 2: Architecture Layers (Data → Presentation)**
**Rationale:** With hardware access proven, build clean architecture incrementally. Start with data layer (no hardware dependency), then presentation (mockable), then integration.

**Delivers:**
- Config loader with Pydantic validation
- Data models (EnergyMetrics, VehicleStatus, etc.)
- SolarEdge API client (primary data source)
- Layout base class and LayoutSpec system
- Display renderer (LayoutSpec → PIL Image)
- Single comprehensive screen layout (replaces 4-screen cycling)
- Hardware abstraction (Display interface with Mock/Waveshare implementations)

**Addresses features:**
- Table stakes: All 6 core metrics on single screen
- Differentiators: Large fonts (32-48px), icon-based status, clear hierarchy

**Architecture components:**
- Complete data → business → presentation flow
- Testable without hardware (mock display)
- Fail-safe data source pattern

**Dependencies:** Phase 1 complete (Docker hardware access working)

**Success criteria:** Display shows real SolarEdge data with improved typography. Layout readable from 2 meters. Tests pass without hardware.

---

**Phase 3: Deployment Orchestration**
**Rationale:** Application works locally in Docker. Now automate deployment to Pi with Kamal, handle lifecycle edge cases.

**Delivers:**
- Kamal configuration (deploy.yml with device passthrough)
- Orchestrator main loop (rotation, active hours logic)
- Graceful shutdown handler (clear display on SIGTERM)
- Volume mounts for persistent cache/logs
- SSH configuration for reliable Pi access
- Build optimization (.dockerignore, multi-stage build)

**Addresses pitfalls:**
- Pitfall 5: Graceful shutdown prevents display corruption
- Pitfall 8: Static IP, SSH reliability configuration
- Pitfall 10: Timezone configuration (Europe/Zurich)
- Pitfall 14: Volume persistence for cache/logs
- Pitfall 15: .dockerignore excludes debug/, display/ directories

**Stack elements:** Kamal 1.x, Docker volumes, signal handling

**Success criteria:** `kamal deploy` succeeds. Container survives restart without corrupted display. Cache persists. Logs accessible.

---

**Phase 4: Polish & Production Readiness**
**Rationale:** Core functionality complete. Address UX refinements and operational concerns.

**Delivers:**
- Display refresh optimization (partial refresh, periodic full clear to prevent ghosting)
- Trend indicators (up/down arrows comparing to previous reading)
- Error handling and retry logic for transient API failures
- Logging configuration (structlog for JSON logs)
- Documentation (Pi setup prerequisites, deployment runbook)

**Addresses:**
- Pitfall 13: E-ink ghosting mitigation
- Pitfall 16: Async BMW API handled properly
- Feature polish: Trend indicators, better error states

**Success criteria:** Display remains crisp over days/weeks. No ghosting. Logs actionable. New Pi can be provisioned from documentation.

---

### Phase Ordering Rationale

**Why this order:**
1. **Hardware first** - Docker device access is existential risk. Validate before architecture investment.
2. **Architecture next** - With hardware proven, build clean layers incrementally. Each layer testable independently.
3. **Deployment third** - Don't automate deployment until application works reliably locally.
4. **Polish last** - UX refinements and operational concerns after core functionality solid.

**Dependency flow:**
- Phase 2 requires Phase 1 (needs working Docker hardware access)
- Phase 3 requires Phase 2 (needs working application to deploy)
- Phase 4 requires Phase 3 (production issues only visible after deployment)

**Risk mitigation:**
- Front-load verification (Phase 1 answers "Is this possible?")
- Incremental validation (each phase independently testable)
- Fail-fast on blockers (architecture mismatch discovered early)

### Research Flags

**Phases likely needing deeper research:**
- **Phase 2 - BMW/VW API Clients:** Complex async APIs with sparse documentation. Current code uses `bimmer_connected` library but mixing async/sync patterns. May need research-phase for proper async integration.
- **Phase 4 - E-ink Optimization:** Display-specific refresh patterns vary by Waveshare model. May need hardware-specific research for optimal ghosting prevention.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 - Docker Foundation:** Well-documented Docker device passthrough and ARM builds. Standard patterns sufficient.
- **Phase 2 - SolarEdge Client:** REST API with official documentation. Straightforward HTTP client implementation.
- **Phase 3 - Kamal Deployment:** Standard Kamal configuration. Official docs cover single-server deployments well.

**Research gaps to address during planning:**
- Verify uv ARM64 support status (fallback to pip-tools if needed)
- Confirm Kamal 1.x privileged mode syntax (training data may be outdated)
- Check SolarEdge API v1 current rate limits (claimed 300/day, verify for account type)
- Validate Waveshare 2.13" V3 partial refresh capabilities (hardware-specific)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Python 3.11/Docker/Kamal choices are sound, but version numbers unverified (no WebSearch access). uv ARM support needs validation. HIGH confidence in technology choices, MEDIUM in specific versions. |
| Features | HIGH | E-ink display constraints well-understood. Table stakes features match solar monitoring domain norms. Layout recommendations based on physics of 250x122 1-bit displays (HIGH confidence). |
| Architecture | HIGH | Layered architecture is standard practice. Component boundaries analyzed from existing 828-line monolith with clear extraction path. Docker device passthrough patterns are well-established for Pi projects. |
| Pitfalls | MEDIUM | Critical pitfalls (device passthrough, ARM arch, credentials) identified from code analysis (HIGH confidence). API rate limits inferred from typical free-tier patterns (MEDIUM confidence). Kamal SSH behavior based on v1 knowledge (MEDIUM confidence, may have changed). |

**Overall confidence:** MEDIUM

Research is based on training knowledge (cutoff January 2025) combined with analysis of existing project code. Technology choices are sound and well-reasoned, but specific version numbers and API limits need verification during implementation. Architecture recommendations are high confidence (based on code analysis). Deployment tooling (Kamal, uv) may have evolved since training cutoff.

### Gaps to Address

**Validation needed during Phase 1:**
- Verify uv supports ARM64/ARMv7 (fallback: pip-tools)
- Check current Python 3.11 Debian Bookworm image ARM availability
- Test Waveshare library compatibility with container environment
- Confirm SPI device paths on target Pi hardware (`/dev/spidev0.0` vs `/dev/spidev0.1`)

**Validation needed during Phase 2:**
- Verify SolarEdge API documentation for current rate limits and endpoints
- Test BMW `bimmer_connected` library async patterns in long-running process
- Confirm font availability in Debian base image (Arial, FontAwesome)

**Validation needed during Phase 3:**
- Check Kamal 1.x (or 2.x if released) documentation for device passthrough syntax
- Verify Docker stop grace period behavior with Waveshare e-ink library
- Test mDNS hostname resolution from Docker container (Time Machine SSH)

**Approach for gaps:** Treat as research spikes during phase execution. If gap becomes blocker, escalate to focused research-phase before continuing.

## Sources

### Primary (HIGH confidence)
- Project code analysis: `/Users/jean-pierrekoenig/Documents/Projects/solaredge-offgrid-monitor/se-overview.py` (828 lines, monolithic structure, hardcoded credentials, current dependencies)
- Project code analysis: `epdconfig.py` (Waveshare library integration, ARM architecture detection, GPIO initialization patterns)
- Architecture patterns: Layered architecture, dependency injection, fail-safe design (standard software engineering practices)

### Secondary (MEDIUM confidence)
- Training knowledge (January 2025 cutoff): Docker device passthrough for Raspberry Pi GPIO/SPI, ARM architecture builds, Python packaging ecosystem
- Training knowledge: Kamal deployment patterns (v1.x, single-server scenarios), SSH-based orchestration
- Training knowledge: E-ink display characteristics (ghosting, refresh rates, resolution constraints), Waveshare hardware API patterns
- Training knowledge: SolarEdge API (REST endpoints, typical rate limiting for monitoring APIs), BMW/VW connected car APIs

### Tertiary (LOW confidence - needs validation)
- Specific version numbers: httpx 0.27, pydantic-settings 2.x, Pillow 10.x, ruff 0.x (versions may have changed post-training)
- uv package manager ARM support status (fast-moving project, verify current status)
- SolarEdge API daily rate limit of 300 calls (inferred from typical free-tier patterns, not verified from official docs)
- Kamal 1.x device passthrough syntax (Kamal may have released v2 since training)

### Research Limitations
- WebSearch and Context7 tools not available during research (permission denied)
- Cannot verify current version numbers or API documentation
- Recommendations based on patterns and training knowledge, not real-time verification

**Recommended next steps:**
1. Verify version numbers and ARM support for critical dependencies (uv, httpx, pydantic-settings)
2. Review SolarEdge API official documentation for rate limits and endpoints
3. Check Kamal current version and documentation for Pi deployment patterns
4. Test hardware access on target Pi before committing to architecture

---

*Research completed: 2026-02-04*
*Ready for roadmap: yes*
*Suggested phases: 4 (Foundation → Architecture → Deployment → Polish)*
