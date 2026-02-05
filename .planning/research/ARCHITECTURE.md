# Architecture Patterns

**Domain:** Containerized Python Raspberry Pi IoT Monitor
**Researched:** 2026-02-04
**Confidence:** HIGH

## Executive Summary

This architecture transforms a monolithic 828-line Python script into a modular, containerized application suitable for Docker deployment on Raspberry Pi with GPIO/SPI hardware access. The design prioritizes clear separation of concerns, testability, and maintainability while preserving the core functionality: polling external APIs, processing data, and rendering to e-ink display hardware.

**Key architectural decisions:**
- Layered architecture (Data → Business → Presentation → Hardware)
- Plugin-based data source system for extensibility
- Hardware abstraction for testing without physical devices
- Docker privileged mode for GPIO/SPI device access
- Single-container deployment via Kamal

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Main Application                        │
│                    (Orchestration Loop)                      │
└───────────┬─────────────────────────────────────────────────┘
            │
    ┌───────┴──────┬──────────┬──────────┬─────────────┐
    │              │          │          │             │
┌───▼────┐  ┌──────▼──┐  ┌───▼────┐  ┌──▼──────┐  ┌──▼───────┐
│ Config │  │ Data    │  │ Layout │  │ Display │  │ Hardware │
│ Loader │  │ Sources │  │ Engine │  │ Renderer│  │ Driver   │
└────────┘  └─────────┘  └────────┘  └─────────┘  └──────────┘
                │                                       │
        ┌───────┴─────────┐                       ┌────▼────┐
        │                 │                       │ E-Ink   │
    ┌───▼────┐      ┌─────▼──────┐              │ Display │
    │ Solar  │      │ Vehicle    │              │ (SPI)   │
    │ Edge   │      │ APIs       │              └─────────┘
    │ Client │      │ (BMW/VW)   │
    └────────┘      └────────────┘
```

## Package Structure

```
solaredge_monitor/
├── __init__.py
├── __main__.py                    # Entry point for 'python -m solaredge_monitor'
├── config/
│   ├── __init__.py
│   ├── loader.py                  # Environment/YAML config loading
│   └── schema.py                  # Pydantic models for config validation
├── datasources/
│   ├── __init__.py
│   ├── base.py                    # Abstract base class for data sources
│   ├── solaredge.py              # SolarEdge API client
│   ├── bmw.py                    # BMW Connected Drive API
│   ├── volkswagen.py             # VW WeConnect API
│   └── timemachine.py            # SSH-based disk space check
├── models/
│   ├── __init__.py
│   ├── energy.py                 # Data classes for energy metrics
│   ├── vehicle.py                # Data classes for vehicle status
│   └── storage.py                # Data classes for backup storage
├── layouts/
│   ├── __init__.py
│   ├── base.py                   # Abstract layout interface
│   ├── energy_overview.py        # Layout 1: Energy details
│   ├── power_flow.py             # Layout 2: Current power flow
│   ├── vehicle_status.py         # Layouts 5,6: Vehicle charging
│   └── storage_status.py         # Layout 4: Time Machine status
├── rendering/
│   ├── __init__.py
│   ├── renderer.py               # PIL-based image rendering
│   └── fonts.py                  # Font loading and scaling
├── hardware/
│   ├── __init__.py
│   ├── display.py                # Display hardware abstraction
│   ├── waveshare.py              # Waveshare e-ink driver wrapper
│   └── mock.py                   # Mock display for testing
└── orchestrator.py               # Main loop and rotation logic

tests/
├── __init__.py
├── test_datasources/
├── test_layouts/
├── test_rendering/
└── fixtures/                     # Mock API responses
```

## Component Boundaries

### 1. Config Loader (`config/`)

**Responsibility:** Load and validate configuration from environment variables or YAML files

**Inputs:** Environment variables, optional config file path

**Outputs:** Validated `Config` object (Pydantic model)

**Dependencies:** None (pure configuration layer)

**Interface:**
```python
from solaredge_monitor.config import load_config

config = load_config()  # Returns validated Config object
```

**Configuration scope:**
- API keys and credentials
- Device identifiers (site_id, VIN, etc.)
- Display settings (rotation interval, scale factor)
- Hardware settings (SPI device path, debug mode)
- Timing configuration (sleep interval, active hours)

---

### 2. Data Sources (`datasources/`)

**Responsibility:** Fetch data from external APIs and services

**Inputs:** Configuration (credentials, endpoints), optional cache

**Outputs:** Domain models (`EnergyMetrics`, `VehicleStatus`, etc.)

**Dependencies:** `config`, `models`

**Base interface:**
```python
class DataSource(ABC):
    @abstractmethod
    async def fetch(self) -> Any:
        """Fetch data from source"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Data source identifier"""
        pass
```

**Concrete implementations:**
- `SolarEdgeClient`: Site overview, energy details, power flow
- `BMWClient`: Vehicle status, charging state, range
- `VolkswagenClient`: Vehicle status via WeConnect
- `TimeMachineMonitor`: SSH-based disk space check

**Error handling:** Each data source handles its own retries and returns `None` on failure (fail-safe)

---

### 3. Data Models (`models/`)

**Responsibility:** Type-safe data structures for domain objects

**Inputs:** Raw API responses (dict/JSON)

**Outputs:** Pydantic models with validation

**Dependencies:** None (pure data layer)

**Key models:**
```python
@dataclass
class EnergyMetrics:
    last_update: datetime
    lifetime_energy_mwh: float
    current_power_kw: float
    daily_energy_kwh: float
    # ... etc

@dataclass
class VehicleStatus:
    name: str
    state_of_charge_pct: int
    range_km: int
    charging_state: str
    plug_state: str
```

**Validation:** Use Pydantic for automatic validation and type coercion

---

### 4. Layouts (`layouts/`)

**Responsibility:** Define screen layouts - what information to display and where

**Inputs:** Domain models (from data sources)

**Outputs:** `LayoutSpec` object defining text positions, icons, values

**Dependencies:** `models`

**Base interface:**
```python
class Layout(ABC):
    @abstractmethod
    def render_spec(self, data: Any) -> LayoutSpec:
        """Convert data into layout specification"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Layout identifier"""
        pass
```

**LayoutSpec structure:**
```python
@dataclass
class TextElement:
    text: str
    position: tuple[int, int]
    font: str  # font key, resolved by renderer
    color: tuple[int, int, int]

@dataclass
class LayoutSpec:
    elements: list[TextElement]
    background: tuple[int, int, int] = (255, 255, 255)
```

**Separation of concerns:** Layouts define WHAT to display, not HOW to render it

---

### 5. Display Renderer (`rendering/`)

**Responsibility:** Convert `LayoutSpec` to PIL Image

**Inputs:** `LayoutSpec` object

**Outputs:** PIL `Image` object

**Dependencies:** `layouts`, PIL/Pillow

**Interface:**
```python
class DisplayRenderer:
    def __init__(self, width: int, height: int, scale_factor: int = 4):
        self.width = width
        self.height = height
        self.scale_factor = scale_factor
        self.fonts = FontManager()

    def render(self, spec: LayoutSpec) -> Image:
        """Render layout spec to PIL Image"""
        # Create high-res image
        # Draw all elements
        # Downscale with LANCZOS
        return image
```

**Font management:** Separate `FontManager` class handles font loading and caching

**Anti-aliasing strategy:** Render at 4x resolution, then downscale for crisp text on e-ink

---

### 6. Hardware Driver (`hardware/`)

**Responsibility:** Abstract hardware display operations

**Inputs:** PIL `Image` object

**Outputs:** Physical display update

**Dependencies:** `waveshare_epd` (optional, only on device)

**Interface:**
```python
class Display(ABC):
    @abstractmethod
    def init(self) -> None:
        """Initialize display hardware"""
        pass

    @abstractmethod
    def show(self, image: Image) -> None:
        """Display image on hardware"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear display"""
        pass

    @abstractmethod
    def sleep(self) -> None:
        """Put display to sleep"""
        pass

class WaveshareDisplay(Display):
    """Real e-ink display via SPI"""
    pass

class MockDisplay(Display):
    """Mock display for testing (saves to file)"""
    pass
```

**Conditional import:** Import `waveshare_epd` only when needed, gracefully fall back to mock

---

### 7. Orchestrator (`orchestrator.py`)

**Responsibility:** Main application loop - coordinate data fetch, layout selection, rendering, display

**Inputs:** Configuration

**Outputs:** Running application (infinite loop)

**Dependencies:** All other components

**Flow:**
```python
class MonitorOrchestrator:
    def __init__(self, config: Config):
        self.config = config
        self.datasources = self._init_datasources()
        self.layouts = self._init_layouts()
        self.renderer = DisplayRenderer(...)
        self.display = self._init_display()

    async def run(self):
        """Main loop"""
        while True:
            if self._is_active_hours():
                for layout_func in self.rotation:
                    data = await layout_func.fetch_data()
                    spec = layout_func.layout.render_spec(data)
                    image = self.renderer.render(spec)
                    self.display.show(image)
                    await asyncio.sleep(self.config.sleep_interval)
            else:
                await asyncio.sleep(self.config.sleep_interval)
```

**Rotation management:** Define display rotation sequence in configuration

---

## Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│ 1. Configuration Phase (Startup)                             │
└──────────────────────────────────────────────────────────────┘
    Config Loader
        ↓
    Load env vars / YAML
        ↓
    Validate with Pydantic
        ↓
    Config object

┌──────────────────────────────────────────────────────────────┐
│ 2. Initialization Phase (Startup)                            │
└──────────────────────────────────────────────────────────────┘
    Orchestrator.__init__()
        ↓
    ├─→ Initialize DataSources (with config)
    ├─→ Initialize Layouts
    ├─→ Initialize Renderer (with dimensions)
    └─→ Initialize Display (hardware or mock)

┌──────────────────────────────────────────────────────────────┐
│ 3. Runtime Loop (Repeating)                                  │
└──────────────────────────────────────────────────────────────┘
    Check active hours (6am - 12am)
        ↓
    For each layout in rotation:
        ↓
    DataSource.fetch()  ──→  API call
        ↓                       ↓
    Raw JSON            ←───────┘
        ↓
    Parse to Model (Pydantic validation)
        ↓
    Domain object (EnergyMetrics, VehicleStatus, etc.)
        ↓
    Layout.render_spec(domain_object)
        ↓
    LayoutSpec (positions, text, fonts)
        ↓
    Renderer.render(spec)
        ↓
    PIL Image (high-res → downscaled)
        ↓
    Display.show(image)
        ↓
    SPI write to e-ink display
        ↓
    Sleep (180s)
        ↓
    Next layout in rotation
```

## Docker Container Architecture

### Device Access Requirements

E-ink displays on Raspberry Pi use SPI interface (`/dev/spidev0.0`) and GPIO pins. Docker containers need explicit device access.

**Dockerfile:**
```dockerfile
FROM python:3.11-slim-bookworm

# Install system dependencies for SPI/GPIO
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    python3-pip \
    libgpiod2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY solaredge_monitor/ ./solaredge_monitor/

# Run as non-root user (with gpio group access)
RUN groupadd -r gpio && useradd -r -g gpio monitor
USER monitor

# Entry point
CMD ["python", "-m", "solaredge_monitor"]
```

**Container runtime requirements:**
```bash
docker run \
  --device /dev/spidev0.0 \
  --device /dev/gpiomem \
  --privileged \
  -e CONFIG_FILE=/config/monitor.yaml \
  -v /path/to/config:/config:ro \
  solaredge-monitor:latest
```

**Why privileged mode:**
- SPI device access requires `/dev/spidev0.0`
- GPIO access requires `/dev/gpiomem`
- Some SPI libraries require direct memory access
- Alternative: Use `--device` flags + `--cap-add SYS_RAWIO` (more secure but library-dependent)

**Device mapping:**
- `/dev/spidev0.0` → SPI bus for e-ink display
- `/dev/gpiomem` → GPIO memory access (safer than /dev/mem)

**Testing without hardware:**
Set `DISPLAY_MODE=mock` environment variable to use `MockDisplay` instead of hardware driver.

---

## Kamal Deployment Architecture

Kamal is designed for multi-host deployments, but works well for single-host IoT scenarios.

**deploy.yml configuration:**
```yaml
service: solaredge-monitor
image: your-registry/solaredge-monitor

servers:
  web:
    hosts:
      - 192.168.1.100  # Raspberry Pi IP

registry:
  server: registry.example.com
  username: deploy
  password:
    - KAMAL_REGISTRY_PASSWORD

env:
  secret:
    - SOLAREDGE_API_KEY
    - BMW_EMAIL
    - BMW_PASSWORD
    - VW_EMAIL
    - VW_PASSWORD
  clear:
    DISPLAY_MODE: hardware
    SLEEP_INTERVAL: "180"
    SCALE_FACTOR: "4"

accessories:
  # None needed - no database, no Redis

volumes:
  - "/home/pi/monitor-config:/config:ro"  # Config file
  - "/home/pi/monitor-debug:/app/debug"   # Debug output (optional)

# Critical: Device access
docker:
  options:
    devices:
      - "/dev/spidev0.0:/dev/spidev0.0"
      - "/dev/gpiomem:/dev/gpiomem"
    cap-add:
      - SYS_RAWIO
    # Alternative if above doesn't work:
    # privileged: true

healthcheck:
  path: /health  # Optional: Add health endpoint
  interval: 30s
  timeout: 5s

# No load balancer needed
traefik:
  enabled: false
```

**Deployment flow:**
```bash
# Initial setup
kamal setup

# Deploy updates
kamal deploy

# View logs
kamal app logs

# SSH to container
kamal app exec -i bash

# Rollback
kamal rollback
```

**Single-host considerations:**
- No load balancing needed (single container)
- No blue-green deployment (just restart)
- Zero-downtime not critical (brief display gap acceptable)
- Health checks optional (no external dependencies to check)

**Secrets management:**
Store secrets in `.kamal/secrets`:
```bash
SOLAREDGE_API_KEY=xxx
BMW_EMAIL=xxx
BMW_PASSWORD=xxx
VW_EMAIL=xxx
VW_PASSWORD=xxx
KAMAL_REGISTRY_PASSWORD=xxx
```

**SSH key setup:**
Kamal requires SSH access to Raspberry Pi. Add deployment key:
```bash
ssh-copy-id pi@192.168.1.100
```

---

## Build Order Recommendations

Based on component dependencies, suggested implementation order:

### Phase 1: Foundation (No external dependencies)
1. **Config schema** (`config/schema.py`)
   - Define Pydantic models for configuration
   - No dependencies

2. **Data models** (`models/*.py`)
   - Define domain objects
   - No dependencies

3. **Config loader** (`config/loader.py`)
   - Implement environment/YAML loading
   - Depends on: config schema

### Phase 2: Data Layer (External APIs)
4. **DataSource base class** (`datasources/base.py`)
   - Define abstract interface
   - Depends on: models

5. **Individual data sources** (`datasources/*.py`)
   - Implement API clients
   - Depends on: base class, models, config
   - Can be built in parallel
   - Start with SolarEdge (simplest HTTP API)

### Phase 3: Presentation Layer
6. **Layout base class** (`layouts/base.py`)
   - Define LayoutSpec and Layout interface
   - Depends on: models

7. **Font manager** (`rendering/fonts.py`)
   - Font loading and caching
   - No dependencies (pure PIL)

8. **Renderer** (`rendering/renderer.py`)
   - Implement LayoutSpec → Image conversion
   - Depends on: layouts (base), fonts

9. **Individual layouts** (`layouts/*.py`)
   - Implement specific screens
   - Depends on: base class, models
   - Can be built in parallel

### Phase 4: Hardware Layer
10. **Display abstraction** (`hardware/display.py`)
    - Define Display interface
    - No dependencies

11. **Mock display** (`hardware/mock.py`)
    - For testing without hardware
    - Depends on: display interface

12. **Waveshare driver** (`hardware/waveshare.py`)
    - Real hardware implementation
    - Depends on: display interface, waveshare_epd library

### Phase 5: Orchestration
13. **Orchestrator** (`orchestrator.py`)
    - Main application loop
    - Depends on: ALL other components

14. **Entry point** (`__main__.py`)
    - CLI setup, error handling
    - Depends on: orchestrator, config

### Phase 6: Containerization
15. **Dockerfile**
    - Container image definition
    - Depends on: complete application

16. **Kamal configuration**
    - Deployment automation
    - Depends on: Dockerfile

**Parallel work opportunities:**
- Data sources can be built simultaneously (Phase 2)
- Layouts can be built simultaneously (Phase 3)
- Mock and Waveshare displays can be built simultaneously (Phase 4)

**Testing strategy:**
- Each phase should have tests before moving to next
- Use mock data sources in Phase 3 (layouts) to avoid API dependencies
- Use mock display for Phases 1-5 (defer hardware testing)

---

## Patterns to Follow

### Pattern 1: Dependency Injection

**What:** Pass dependencies to constructors rather than importing globals

**When:** Any class that depends on configuration or external services

**Why:** Improves testability, makes dependencies explicit

**Example:**
```python
# Good: Dependencies injected
class SolarEdgeClient:
    def __init__(self, api_key: str, site_id: str):
        self.api_key = api_key
        self.site_id = site_id

# Usage
client = SolarEdgeClient(config.solaredge_api_key, config.site_id)

# Bad: Global imports
api_key = "HARDCODED"  # Module level
class SolarEdgeClient:
    def fetch(self):
        # Uses global api_key
        pass
```

---

### Pattern 2: Fail-Safe Data Sources

**What:** Data source failures should not crash the application

**When:** Any external API call

**Why:** IoT applications should be resilient to network issues

**Example:**
```python
class DataSource(ABC):
    async def fetch(self) -> Optional[Model]:
        try:
            data = await self._fetch_impl()
            return self._parse(data)
        except Exception as e:
            logger.error(f"{self.name} fetch failed: {e}")
            return None  # Fail-safe: return None

    @abstractmethod
    async def _fetch_impl(self) -> dict:
        """Subclass implements actual fetch"""
        pass
```

**Orchestrator handling:**
```python
data = await data_source.fetch()
if data is None:
    continue  # Skip this layout, move to next
```

---

### Pattern 3: Hardware Abstraction

**What:** Use abstract interface for display hardware

**When:** Any hardware interaction

**Why:** Enables testing without physical device

**Example:**
```python
# Abstract interface
class Display(ABC):
    @abstractmethod
    def show(self, image: Image) -> None:
        pass

# Production implementation
class WaveshareDisplay(Display):
    def show(self, image: Image) -> None:
        self.epd.display(self.epd.getbuffer(image))

# Test implementation
class MockDisplay(Display):
    def show(self, image: Image) -> None:
        image.save(f"debug/display_{time.time()}.png")

# Factory function
def create_display(config: Config) -> Display:
    if config.display_mode == "mock":
        return MockDisplay()
    else:
        return WaveshareDisplay()
```

---

### Pattern 4: Layout Specification

**What:** Separate layout definition from rendering

**When:** Defining screen layouts

**Why:** Decouples "what to display" from "how to render"

**Example:**
```python
# Layout defines WHAT
class EnergyOverviewLayout(Layout):
    def render_spec(self, data: EnergyMetrics) -> LayoutSpec:
        return LayoutSpec(elements=[
            TextElement(
                text=f"{data.current_power_kw:.2f} kW",
                position=(10, 50),
                font="large_bold",
                color=(0, 0, 0)
            ),
            # ... more elements
        ])

# Renderer defines HOW
class DisplayRenderer:
    def render(self, spec: LayoutSpec) -> Image:
        for element in spec.elements:
            font = self.fonts.get(element.font)
            self.draw.text(element.position, element.text, font=font, fill=element.color)
```

**Benefits:**
- Layouts can be tested without rendering
- Rendering can be tested with mock layouts
- Easy to add new layouts without touching renderer

---

### Pattern 5: Configuration Validation

**What:** Use Pydantic for configuration with validation

**When:** Loading configuration at startup

**Why:** Fail fast with clear error messages

**Example:**
```python
from pydantic import BaseModel, Field, validator

class SolarEdgeConfig(BaseModel):
    api_key: str = Field(..., min_length=20)
    site_id: str = Field(..., regex=r'^\d+$')

class Config(BaseModel):
    solaredge: SolarEdgeConfig
    sleep_interval: int = Field(default=180, ge=30, le=3600)
    scale_factor: int = Field(default=4, ge=1, le=8)

    @validator('sleep_interval')
    def check_reasonable_interval(cls, v):
        if v < 30:
            raise ValueError('Sleep interval too short (min 30s)')
        return v

# Usage
config = Config(**yaml.safe_load(config_file))  # Validates automatically
```

---

### Pattern 6: Async/Await for Data Sources

**What:** Use async/await for API calls

**When:** Fetching data from multiple sources

**Why:** Enables concurrent fetching, reduces wait time

**Example:**
```python
# Fetch multiple sources concurrently
async def fetch_all_data(datasources: list[DataSource]):
    results = await asyncio.gather(
        *[ds.fetch() for ds in datasources],
        return_exceptions=True
    )
    return results

# In orchestrator
data_sources = [solaredge, bmw, vw, timemachine]
results = await fetch_all_data(data_sources)
```

**Note:** Current implementation is sequential. Async is optional but recommended for future performance.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Mixing Data Fetch and Rendering

**What:** Functions that both fetch data and create images

**Current code:**
```python
def display(energy_details):
    # Fetches data
    data = get_energy_details()
    # Renders display
    draw.text(...)
    epd.display(...)
```

**Why bad:**
- Impossible to test rendering without API calls
- Impossible to test API logic without display hardware
- Violates single responsibility principle

**Instead:** Separate concerns
```python
# Separate functions
data = await data_source.fetch()  # Data layer
spec = layout.render_spec(data)   # Presentation layer
image = renderer.render(spec)     # Rendering layer
display.show(image)               # Hardware layer
```

---

### Anti-Pattern 2: Hardcoded Credentials

**What:** API keys, passwords in source code

**Current code:**
```python
api_key = "[REDACTED-API-KEY]"
bmw_password = "[REDACTED-PASSWORD]"
```

**Why bad:**
- Credentials visible in git history
- Can't change without code changes
- Security risk

**Instead:** Environment variables or config files
```python
config = Config(
    solaredge_api_key=os.getenv("SOLAREDGE_API_KEY"),
    bmw_password=os.getenv("BMW_PASSWORD")
)
```

---

### Anti-Pattern 3: Global State

**What:** Module-level variables for fonts, images, devices

**Current code:**
```python
# Module level
font30 = ImageFont.truetype(font_path, 50 * scale_factor)
epd = None  # Initialized later
```

**Why bad:**
- Makes testing difficult (can't isolate tests)
- Hidden dependencies (unclear what uses what)
- Race conditions in concurrent code

**Instead:** Encapsulate in classes
```python
class FontManager:
    def __init__(self, fonts_dir: str, scale_factor: int):
        self.fonts_dir = fonts_dir
        self.scale_factor = scale_factor
        self._cache = {}

    def get(self, name: str, size: int) -> ImageFont:
        key = f"{name}_{size}"
        if key not in self._cache:
            self._cache[key] = ImageFont.truetype(
                f"{self.fonts_dir}/{name}.ttf",
                size * self.scale_factor
            )
        return self._cache[key]
```

---

### Anti-Pattern 4: Silent Failures

**What:** Catching exceptions without logging or handling

**Current code:**
```python
try:
    data = get_api_data()
except:
    pass  # Silent failure
```

**Why bad:**
- Impossible to debug when things go wrong
- May lead to partial state or corruption

**Instead:** Log errors and handle gracefully
```python
try:
    data = await data_source.fetch()
except Exception as e:
    logger.error(f"Failed to fetch {data_source.name}: {e}", exc_info=True)
    return None  # Explicit fail-safe return
```

---

### Anti-Pattern 5: Conditional Imports in Functions

**What:** Importing hardware libraries inside display functions

**Current code:**
```python
def display(data):
    if debug == False:
        from waveshare_epd import epd2in13_V3  # Import inside function
        epd = epd2in13_V3.EPD()
```

**Why bad:**
- Import side effects on every call
- Harder to mock for testing
- Mixes hardware logic with display logic

**Instead:** Factory pattern with abstraction
```python
def create_display(mode: str) -> Display:
    if mode == "hardware":
        from hardware.waveshare import WaveshareDisplay
        return WaveshareDisplay()
    else:
        from hardware.mock import MockDisplay
        return MockDisplay()

# In orchestrator __init__
self.display = create_display(config.display_mode)
```

---

### Anti-Pattern 6: Magic Numbers

**What:** Unexplained constants scattered in code

**Current code:**
```python
draw.text((225 * scale_factor, 1 * scale_factor), icon, ...)
sleep_timer = 180
scale_factor = 4
```

**Why bad:**
- Meaning unclear
- Hard to maintain consistency
- Difficult to adjust

**Instead:** Named constants or configuration
```python
# In layout class
class EnergyOverviewLayout:
    ICON_RIGHT_MARGIN = 225
    ICON_TOP_MARGIN = 1

    def render_spec(self, data):
        return LayoutSpec(elements=[
            TextElement(
                position=(self.ICON_RIGHT_MARGIN, self.ICON_TOP_MARGIN),
                ...
            )
        ])

# In config
class DisplayConfig(BaseModel):
    scale_factor: int = 4
    sleep_interval: int = 180
```

---

## Scalability Considerations

| Concern | Current (1 Pi) | 10 Pis | 100+ Pis |
|---------|----------------|--------|----------|
| **Deployment** | Kamal single-host | Kamal multi-host (same config) | Consider Ansible/Fleet |
| **Configuration** | Env vars / YAML per Pi | Centralized config service | Config management system |
| **Monitoring** | Local logs | Centralized logging (Loki) | Full observability stack |
| **Updates** | Kamal deploy (manual) | Kamal deploy (parallel) | GitOps (Flux/ArgoCD) |
| **Secrets** | .env file per Pi | Secret management (Vault) | Secret management mandatory |
| **API rate limits** | No issue (1 client) | May hit SolarEdge limits | Need request coordination |

**Current architecture supports:**
- Single Pi: Perfect fit
- 10 Pis: Works well with Kamal multi-host
- 100+ Pis: Needs additional tooling (but architecture remains sound)

**Not needed now, but future-proof:**
- Metrics endpoint (for Prometheus)
- Health endpoint (for monitoring)
- Graceful shutdown (for rolling updates)

---

## Testing Strategy

### Unit Testing

**Per-component tests:**
```
tests/
├── test_config/
│   ├── test_loader.py          # Config loading, validation
│   └── test_schema.py          # Pydantic model validation
├── test_datasources/
│   ├── test_solaredge.py       # Mock HTTP responses
│   ├── test_bmw.py
│   └── test_volkswagen.py
├── test_models/
│   └── test_validation.py      # Data model validation
├── test_layouts/
│   ├── test_energy_overview.py # Layout spec generation
│   └── test_vehicle_status.py
├── test_rendering/
│   ├── test_renderer.py        # Image generation
│   └── test_fonts.py           # Font loading
└── test_hardware/
    └── test_display.py         # Mock display behavior
```

**Fixture strategy:**
```python
# tests/fixtures/api_responses.py
SOLAREDGE_OVERVIEW = {
    "overview": {
        "lastUpdateTime": "2026-02-04 12:00:00",
        "currentPower": {"power": 5000.0},
        # ... complete response
    }
}

# In tests
@pytest.fixture
def mock_solaredge_response():
    return SOLAREDGE_OVERVIEW
```

### Integration Testing

**Test complete flow without hardware:**
```python
@pytest.mark.asyncio
async def test_full_cycle():
    config = load_test_config()
    orchestrator = MonitorOrchestrator(config)
    orchestrator.display = MockDisplay()  # Use mock

    # Run one cycle
    await orchestrator.run_once()

    # Assert display was updated
    assert orchestrator.display.last_image is not None
```

### Hardware Testing

**Manual testing on device:**
```bash
# Run with mock display first
DISPLAY_MODE=mock python -m solaredge_monitor

# Check generated images
ls -la debug/*.png

# Run with real hardware
DISPLAY_MODE=hardware python -m solaredge_monitor
```

---

## Migration Path from Monolith

**Phase-by-phase refactoring strategy:**

1. **Extract models** (low risk)
   - Copy data structures to `models/`
   - Keep monolith working

2. **Extract config** (low risk)
   - Move credentials to config loader
   - Update monolith to use config objects

3. **Extract data sources** (medium risk)
   - Refactor API functions to classes
   - Test against real APIs
   - Replace in monolith

4. **Extract rendering** (low risk)
   - Create renderer from display functions
   - Test image output matches

5. **Extract layouts** (medium risk)
   - Convert display functions to layouts
   - Verify visual output

6. **Extract hardware** (high risk - requires device testing)
   - Create display abstraction
   - Test on actual hardware

7. **Create orchestrator** (high risk)
   - Wire everything together
   - Test complete flow

8. **Add Docker** (low risk if orchestrator works)
   - Create Dockerfile
   - Test device access

9. **Add Kamal** (low risk)
   - Create deploy.yml
   - Test deployment

**Validation at each step:** Old and new code should produce identical output

---

## Sources

**Architecture patterns:**
- Based on standard layered architecture (Presentation → Business → Data → Infrastructure)
- Informed by Python packaging best practices (PEP 420, PEP 517)

**Docker + GPIO/SPI:**
- Raspberry Pi Docker documentation (device access patterns)
- Common practice: `--device /dev/spidev0.0` + `--privileged` or `--cap-add SYS_RAWIO`
- Waveshare e-ink documentation for SPI requirements

**Kamal deployment:**
- Kamal official documentation (v1.x patterns)
- Single-host deployment is standard Kamal configuration (no special considerations)

**Confidence levels:**
- Package structure: HIGH (standard Python practices)
- Component boundaries: HIGH (domain-driven design)
- Docker device access: HIGH (well-established pattern)
- Kamal configuration: HIGH (official documentation)
- Build order: HIGH (dependency analysis of current code)

**Current code analysis:**
- File: `/Users/jean-pierrekoenig/Documents/Projects/solaredge-offgrid-monitor/se-overview.py`
- Structure: 828 lines, monolithic, no modularization
- Functions identified: 12 display/fetch functions, 1 main loop
- Dependencies: SolarEdge API, BMW Connected Drive, VW WeConnect, SSH/SFTP, Waveshare e-ink, PIL

---

## Recommendations Summary

**For immediate implementation:**
1. Start with foundation (config, models) - lowest risk
2. Use dependency injection throughout - improves testability
3. Create hardware abstraction early - enables development without device
4. Use mock display for testing - avoids hardware dependency
5. Implement fail-safe data sources - resilience to API failures

**For Docker deployment:**
1. Use `--device` flags for SPI/GPIO access
2. Add `--cap-add SYS_RAWIO` if needed
3. Test with mock display first, then hardware
4. Use multi-stage build for smaller images (optional)

**For Kamal deployment:**
1. Standard configuration works for single host
2. Store secrets in `.kamal/secrets` (not git)
3. No load balancer needed
4. Health checks optional (no external dependencies)

**For future scalability:**
1. Add metrics endpoint when scaling to 10+ devices
2. Consider centralized logging when scaling to 10+ devices
3. Current architecture supports up to ~50 Pis without changes
