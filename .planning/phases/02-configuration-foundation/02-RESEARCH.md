# Phase 2: Configuration Foundation - Research

**Researched:** 2026-02-05
**Domain:** Python environment-based configuration with python-dotenv
**Confidence:** HIGH

## Summary

Python-based environment configuration follows the twelve-factor app methodology, using environment variables for all deployment-specific settings while keeping code environment-agnostic. The standard approach uses **python-dotenv v1.2.1** to load .env files into os.environ, combined with Python dataclasses and `__post_init__` validation for type-safe configuration objects.

The user has locked several decisions: use python-dotenv, implement a single Config dataclass, validate all errors at once before exit, use `SOLAREDGE_` prefix for all variables, and support both .env files (development) and real environment variables (production) with env vars taking precedence.

Key findings indicate that environment variables are always strings, requiring explicit type conversion with careful handling of booleans (avoid `bool()` trap where "false" is truthy) and integers (use try/except for ValueError). Validation should accumulate all errors and report them together, letting operators fix everything in one pass. Secret masking in logs is critical—show only last 4 characters of sensitive values.

**Primary recommendation:** Use python-dotenv's `load_dotenv()` at application entry point, build a dataclass with `__post_init__` for validation and type conversion, accumulate all validation errors before raising, and log sanitized config at startup.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-dotenv | 1.2.1 | Load .env files into os.environ | De facto standard, follows 12-factor principles, handles edge cases (quotes, multiline, variable expansion) |
| dataclasses | stdlib (3.7+) | Type-safe configuration structure | Built-in, lightweight, provides `__post_init__` hook for validation |
| os.environ | stdlib | Access environment variables | Standard library, no dependencies |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing | stdlib (3.5+) | Type hints for config fields | Always—improves IDE support and documentation |
| sys | stdlib | Exit with error codes | For validation failures (sys.exit(1)) |
| logging | stdlib | Masked config output at startup | Log loaded config with secrets redacted |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-dotenv + dataclass | Pydantic Settings | Pydantic provides automatic type conversion and more sophisticated validation, but adds dependency weight. User chose simpler approach with manual validation. |
| python-dotenv | environs or python-decouple | These libraries offer type parsing helpers, but python-dotenv is more widely adopted and user explicitly chose it. |
| Dataclass validation | Custom config class | Dataclasses provide `__post_init__` hook naturally, reducing boilerplate vs manual __init__ methods. |

**Installation:**
```bash
pip install python-dotenv==1.2.1
```

## Architecture Patterns

### Recommended Project Structure
```
solaredge-offgrid-monitor/
├── .env                    # Local config (gitignored, not committed)
├── .env.example            # Template (committed, no secrets)
├── .gitignore              # Excludes .env and .env.*
├── src/
│   └── config.py           # Config dataclass, validation, loading
└── main.py                 # Entry point, calls load_dotenv() early
```

### Pattern 1: Early Load + Dataclass Validation

**What:** Call `load_dotenv()` at application entry point before any imports that might access config, then construct a Config dataclass that validates and type-converts in `__post_init__`.

**When to use:** Always for environment-based configuration (this is the standard twelve-factor approach).

**Example:**
```python
# main.py - Application entry point
from dotenv import load_dotenv
import os

# Load .env BEFORE importing config module
load_dotenv()

# Now safe to import modules that access environment
from src.config import Config

def main():
    try:
        config = Config()
        config.log_startup()  # Log with secrets masked
    except ValueError as e:
        print(f"Configuration error:\n{e}", file=sys.stderr)
        sys.exit(1)

    # Application logic here

if __name__ == "__main__":
    main()
```

```python
# src/config.py - Configuration dataclass
from dataclasses import dataclass
import os
import logging

@dataclass
class Config:
    """Application configuration loaded from environment variables.

    All variables use SOLAREDGE_ prefix.
    """

    # Required credentials
    api_key: str
    site_id: str

    # Optional operational settings with defaults
    poll_interval_minutes: int = 5
    sleep_start_hour: int = 0
    sleep_end_hour: int = 6
    debug: bool = False

    def __post_init__(self):
        """Load from environment and validate."""
        errors = []

        # Load and validate required credentials
        self.api_key = os.environ.get("SOLAREDGE_API_KEY", "")
        if not self.api_key:
            errors.append("- SOLAREDGE_API_KEY: SolarEdge API key (required)")

        self.site_id = os.environ.get("SOLAREDGE_SITE_ID", "")
        if not self.site_id:
            errors.append("- SOLAREDGE_SITE_ID: Site identifier (required)")

        # Load operational settings with type conversion
        try:
            poll_str = os.environ.get("SOLAREDGE_POLL_INTERVAL", "5")
            self.poll_interval_minutes = int(poll_str)
            if self.poll_interval_minutes < 1:
                errors.append("- SOLAREDGE_POLL_INTERVAL: Must be >= 1 minute")
        except ValueError:
            errors.append(f"- SOLAREDGE_POLL_INTERVAL: Must be an integer (got '{poll_str}')")

        try:
            start_str = os.environ.get("SOLAREDGE_SLEEP_START", "0")
            self.sleep_start_hour = int(start_str)
            if not (0 <= self.sleep_start_hour <= 23):
                errors.append("- SOLAREDGE_SLEEP_START: Must be 0-23")
        except ValueError:
            errors.append(f"- SOLAREDGE_SLEEP_START: Must be an integer (got '{start_str}')")

        try:
            end_str = os.environ.get("SOLAREDGE_SLEEP_END", "6")
            self.sleep_end_hour = int(end_str)
            if not (0 <= self.sleep_end_hour <= 23):
                errors.append("- SOLAREDGE_SLEEP_END: Must be 0-23")
        except ValueError:
            errors.append(f"- SOLAREDGE_SLEEP_END: Must be an integer (got '{end_str}')")

        # Parse boolean (CRITICAL: avoid bool() trap)
        debug_str = os.environ.get("SOLAREDGE_DEBUG", "false").lower()
        self.debug = debug_str in ("true", "1", "yes", "on")

        # Report all errors at once
        if errors:
            error_msg = "ERROR: Configuration validation failed:\n" + "\n".join(errors)
            raise ValueError(error_msg)

    def log_startup(self):
        """Log configuration at startup with secrets masked."""
        masked_key = f"****{self.api_key[-4:]}" if len(self.api_key) >= 4 else "****"
        logging.info("Configuration loaded:")
        logging.info(f"  SOLAREDGE_API_KEY: {masked_key}")
        logging.info(f"  SOLAREDGE_SITE_ID: {self.site_id}")
        logging.info(f"  SOLAREDGE_POLL_INTERVAL: {self.poll_interval_minutes} min")
        logging.info(f"  SOLAREDGE_SLEEP_START: {self.sleep_start_hour}:00")
        logging.info(f"  SOLAREDGE_SLEEP_END: {self.sleep_end_hour}:00")
        logging.info(f"  SOLAREDGE_DEBUG: {self.debug}")
```

```bash
# .env.example - Committed template
# SolarEdge API credentials (required)
SOLAREDGE_API_KEY=your_api_key_here
SOLAREDGE_SITE_ID=your_site_id_here

# Display settings
# (future phase - display configuration goes here)

# Operations
SOLAREDGE_POLL_INTERVAL=5        # Minutes between API polls (default: 5)
SOLAREDGE_SLEEP_START=0          # Hour to pause polling (0-23, default: 0)
SOLAREDGE_SLEEP_END=6            # Hour to resume polling (0-23, default: 6)
SOLAREDGE_DEBUG=false            # Enable debug logging (true/false, default: false)
```

### Pattern 2: Override Behavior (Development vs Production)

**What:** python-dotenv's `load_dotenv(override=False)` default means real environment variables override .env file values.

**When to use:** Always—supports twelve-factor deployment model where .env is for local development but production systems (systemd, Docker, Kubernetes) inject real env vars.

**Example:**
```python
# Default behavior (override=False)
load_dotenv()  # .env file loaded, but existing env vars take precedence

# This allows:
# - Development: uses .env file
# - Production: systemd EnvironmentFile= or Docker -e FLAGS override .env
# - CI/CD: secrets injected at runtime override any .env
```

### Pattern 3: Error Accumulation for Validation

**What:** Collect all validation errors in a list, then raise once with complete error message. User requirement: "operator fixes everything in one pass."

**When to use:** Startup validation where user needs to see all problems at once.

**Example:**
```python
def __post_init__(self):
    errors = []

    # Check all fields, accumulating errors
    if not self.api_key:
        errors.append("- SOLAREDGE_API_KEY: Required")

    if not self.site_id:
        errors.append("- SOLAREDGE_SITE_ID: Required")

    try:
        if self.poll_interval < 1:
            errors.append("- SOLAREDGE_POLL_INTERVAL: Must be >= 1")
    except (ValueError, TypeError) as e:
        errors.append(f"- SOLAREDGE_POLL_INTERVAL: {e}")

    # Only raise after checking everything
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(errors))
```

### Anti-Patterns to Avoid

- **Using `bool(os.environ.get("DEBUG"))`**: WRONG—both "true" and "false" are truthy strings. Always check `value.lower() in ("true", "1", "yes")`.
- **Calling load_dotenv() late**: WRONG—imported modules miss the variables. Call at entry point before other imports.
- **Storing .env in version control**: WRONG—secrets leak. Always .gitignore .env, only commit .env.example.
- **Stopping at first validation error**: WRONG—user must fix one error at a time. Accumulate all errors and report together.
- **Logging secrets unmasked**: WRONG—logs may be readable by people without secret access. Always mask sensitive values (show last 4 chars max).
- **Using different prefixes**: WRONG—user decided on `SOLAREDGE_` prefix for all variables. Consistency matters for grep/documentation.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| .env file parsing | Custom parser for KEY=VALUE | python-dotenv | Handles quotes, multiline values, escape sequences, variable expansion (${VAR}), export directives, comments. Edge cases are subtle. |
| Boolean parsing | `if os.environ.get("DEBUG"):` or `bool(...)` | Explicit `value.lower() in ("true", "1", "yes")` | String "false" is truthy. Must explicitly check string value. |
| Type conversion | Manual int()/float() calls without error handling | Try/except with error accumulation | Need to catch ValueError and continue validating other fields. |
| Secret masking | String slicing/replacement by hand | `f"****{secret[-4:]}" if len(secret) >= 4 else "****"` | Easy to get wrong (negative indices, empty strings). Pattern is well-established. |
| .gitignore patterns | Manual list of .env variants | Standard Python .gitignore templates | Community-vetted patterns catch .env.local, .env.production, .venv, env/, etc. |

**Key insight:** Environment variable handling has many subtle edge cases (type conversion, string truthiness, .env file parsing rules) that look trivial but cause production bugs. Use established libraries and patterns rather than custom solutions.

## Common Pitfalls

### Pitfall 1: Boolean String Truthiness Trap

**What goes wrong:** Using `bool(os.environ.get("DEBUG"))` treats both "true" and "false" as True because non-empty strings are truthy.

**Why it happens:** Python's `bool()` converts strings to boolean based on emptiness, not content. "false" is a non-empty string, so `bool("false")` returns True.

**How to avoid:**
```python
# WRONG
debug = bool(os.environ.get("DEBUG", "false"))  # Always True!

# RIGHT
debug_str = os.environ.get("DEBUG", "false").lower()
debug = debug_str in ("true", "1", "yes", "on")
```

**Warning signs:** Config behaves as if debug is always on, regardless of .env value.

### Pitfall 2: load_dotenv() Timing and Import Order

**What goes wrong:** Importing modules that access `os.environ` before calling `load_dotenv()` means those modules see empty environment variables.

**Why it happens:** Python imports are executed immediately. If a module's top-level code accesses `os.environ.get("SOMETHING")` during import, and `load_dotenv()` hasn't run yet, the variable isn't loaded.

**How to avoid:**
```python
# WRONG - config module imported before load_dotenv()
from src.config import Config  # This might access os.environ during import!
from dotenv import load_dotenv
load_dotenv()

# RIGHT - load_dotenv() called first
from dotenv import load_dotenv
load_dotenv()
from src.config import Config  # Now env vars are loaded
```

**Warning signs:** Config works when running directly but fails when imported from another module. Environment variables mysteriously empty.

### Pitfall 3: Integer Parsing Without Validation

**What goes wrong:** `int(os.environ.get("PORT", "8080"))` raises ValueError if the env var contains non-numeric strings like "abc" or "8080.5", crashing the application at startup.

**Why it happens:** Environment variables are always strings. Type conversion can fail if user provides malformed input.

**How to avoid:**
```python
# WRONG - crash on invalid input
port = int(os.environ.get("PORT", "8080"))

# RIGHT - validate and accumulate error
try:
    port_str = os.environ.get("PORT", "8080")
    port = int(port_str)
    if port < 1 or port > 65535:
        errors.append(f"- PORT: Must be 1-65535 (got {port})")
except ValueError:
    errors.append(f"- PORT: Must be an integer (got '{port_str}')")
```

**Warning signs:** Application crashes with ValueError during startup instead of showing helpful error message.

### Pitfall 4: Quote Handling in .env Files

**What goes wrong:** Values with spaces like `NAME=John Doe` are parsed as `NAME="John"` (stops at space). Using quotes like `NAME="John Doe"` works, but `NAME="quoted value"` in .env accessed via Docker may include literal quote characters.

**Why it happens:** Different .env parsers handle quotes inconsistently. python-dotenv strips quotes, but Docker's native env-file parsing may not.

**How to avoid:**
- Use quotes for values with spaces: `API_KEY="value with spaces"`
- Test in target environment (development python-dotenv vs production Docker/systemd)
- Document quoting rules in .env.example

**Warning signs:** Values work in development but fail in production with literal quote characters in strings.

### Pitfall 5: .env File Accidentally Committed

**What goes wrong:** .env file with real credentials gets committed to version control (git), exposing secrets in repository history.

**Why it happens:** Forgetting to add .env to .gitignore, or using `git add .` before .gitignore is set up.

**How to avoid:**
- Add .env to .gitignore immediately when creating project
- Use .env.example (committed) as template, .env (gitignored) for real values
- Use pre-commit hooks or tools like Gitleaks to catch secrets

**Warning signs:** `git status` shows .env as untracked or staged. GitHub secret scanning alerts.

### Pitfall 6: Config Validation Fails Silently or Partially

**What goes wrong:** Validation finds first error, raises exception, but user doesn't see other errors. Must fix one error at a time, re-run, see next error. Frustrating iteration.

**Why it happens:** Raising exception immediately on first error (fail-fast) is common pattern, but wrong for startup validation.

**How to avoid:**
```python
# WRONG - stops at first error
def validate(self):
    if not self.api_key:
        raise ValueError("API key required")
    if not self.site_id:
        raise ValueError("Site ID required")

# RIGHT - accumulates all errors
def validate(self):
    errors = []
    if not self.api_key:
        errors.append("- API key required")
    if not self.site_id:
        errors.append("- Site ID required")
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(errors))
```

**Warning signs:** User reports having to "fix errors one at a time" and re-run repeatedly.

### Pitfall 7: Logging Secrets Unmasked

**What goes wrong:** Logging config at startup includes full API keys, tokens, passwords. Logs are often readable by more people than should have secret access.

**Why it happens:** Helpful to log config for debugging, but easy to forget secrets are sensitive.

**How to avoid:**
```python
# WRONG - logs full secret
logging.info(f"API_KEY: {config.api_key}")

# RIGHT - masks secret, shows last 4 for verification
masked = f"****{config.api_key[-4:]}" if len(config.api_key) >= 4 else "****"
logging.info(f"API_KEY: {masked}")
```

**Warning signs:** Security audit finds secrets in log files. Logs uploaded to external monitoring contain credentials.

## Code Examples

Verified patterns from official sources and documentation:

### Load .env at Application Entry Point

```python
# Source: https://github.com/theskumar/python-dotenv (official README)
from dotenv import load_dotenv
import os

# Load .env file into os.environ
# override=False (default): real env vars take precedence over .env
load_dotenv()

# Access variables
api_key = os.environ.get("SOLAREDGE_API_KEY")
```

### Dataclass with __post_init__ Validation

```python
# Source: https://docs.python.org/3/library/dataclasses.html (official Python docs)
from dataclasses import dataclass

@dataclass
class Config:
    api_key: str
    site_id: str
    poll_interval: int = 5

    def __post_init__(self):
        """Called after __init__ to perform validation."""
        # Load from environment
        self.api_key = os.environ.get("SOLAREDGE_API_KEY", "")
        self.site_id = os.environ.get("SOLAREDGE_SITE_ID", "")

        # Validate
        if not self.api_key:
            raise ValueError("SOLAREDGE_API_KEY required")
        if not self.site_id:
            raise ValueError("SOLAREDGE_SITE_ID required")
```

### Boolean Parsing (Avoiding Truthiness Trap)

```python
# Source: Community best practice from multiple sources
# https://github.com/theskumar/python-dotenv/issues/291
debug_str = os.environ.get("DEBUG", "false").lower()
debug = debug_str in ("true", "1", "yes", "on")

# Alternative: explicit false check
debug = debug_str not in ("false", "0", "no", "off", "")
```

### Error Accumulation Pattern

```python
# Source: Pattern documented in Pydantic validation and validation frameworks
# https://docs.pydantic.dev/latest/errors/validation_errors/
def validate_config():
    errors = []

    if not self.api_key:
        errors.append("- SOLAREDGE_API_KEY: Required")

    if not self.site_id:
        errors.append("- SOLAREDGE_SITE_ID: Required")

    try:
        self.poll_interval = int(os.environ.get("POLL_INTERVAL", "5"))
    except ValueError as e:
        errors.append(f"- POLL_INTERVAL: Must be integer ({e})")

    if errors:
        raise ValueError("Configuration validation failed:\n" + "\n".join(errors))
```

### Secret Masking in Logs

```python
# Source: Community best practice
# https://dev.to/camillehe1992/mask-sensitive-data-using-python-built-in-logging-module-45fa
def mask_secret(secret: str, show_chars: int = 4) -> str:
    """Mask secret, showing only last N characters."""
    if len(secret) <= show_chars:
        return "****"
    return f"****{secret[-show_chars:]}"

# Usage
logging.info(f"API_KEY: {mask_secret(config.api_key)}")
```

### .env.example Template with Comments

```bash
# Source: python-dotenv documentation and twelve-factor best practices
# https://12factor.net/config

# SolarEdge API credentials (required)
SOLAREDGE_API_KEY=your_api_key_here
SOLAREDGE_SITE_ID=your_site_id_here

# Operations
SOLAREDGE_POLL_INTERVAL=5        # Minutes between polls (default: 5)
SOLAREDGE_DEBUG=false            # Enable debug logging (true/false)
```

### .gitignore Patterns for Secrets

```gitignore
# Source: Standard Python .gitignore templates
# https://github.com/github/gitignore/blob/main/Python.gitignore

# Environment files
.env
.env.*
.envrc

# Virtual environments
.venv
venv/
env/
ENV/
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Config files (config.ini, config.yaml) | Environment variables + .env files | ~2012 (Twelve-Factor) | Better separation of config from code, no per-environment config files in repo |
| Custom parsers for .env | python-dotenv library | ~2014 (library created) | Handles edge cases (quotes, multiline, variable expansion) correctly |
| Manual type conversion | Libraries with type parsing (Pydantic Settings, environs) | ~2018-2020 | Automatic type conversion, but adds dependencies. User chose manual approach for simplicity. |
| Single validation error | Error accumulation | ~2020+ (better UX) | Users fix all errors at once instead of iterative fixing |
| Plain text secrets in logs | Masked logging | ~2020+ (security awareness) | Prevents secret leakage via logs |

**Deprecated/outdated:**
- **ConfigParser for app config**: Still in stdlib, but twelve-factor methodology prefers environment variables over config files. ConfigParser useful for complex structured config but overkill for deployment settings.
- **python-dotenv < 1.0**: Older versions had different encoding defaults (None instead of utf-8). Current version is 1.2.1 (October 2025).
- **Boolean parsing with json.loads()**: Previously recommended (Issue #291 on python-dotenv), but explicit string checking is clearer and doesn't require JSON parsing overhead.

## Open Questions

Things that couldn't be fully resolved:

1. **Pydantic Settings vs Manual Validation**
   - What we know: Pydantic Settings offers automatic type conversion, rich validation, and better error messages. User chose manual approach with dataclass + __post_init__.
   - What's unclear: Whether manual approach will scale if config grows significantly (more fields, more complex types).
   - Recommendation: Start with chosen approach (manual validation). If validation logic becomes complex (>50 lines, many custom type conversions), consider migrating to Pydantic Settings in a future refactor.

2. **dotenv_values() vs load_dotenv()**
   - What we know: `load_dotenv()` mutates os.environ. `dotenv_values()` returns dict without side effects, enabling testing and isolation.
   - What's unclear: Whether user wants to use `dotenv_values()` for easier testing (can inject mock config) vs `load_dotenv()` for simplicity.
   - Recommendation: Use `load_dotenv()` as specified by user. If testing becomes difficult (mocking os.environ is awkward), consider switching to `dotenv_values()` approach.

3. **Variable Expansion Feature**
   - What we know: python-dotenv supports POSIX variable expansion like `BASE_URL=${PROTOCOL}://${HOST}:${PORT}`.
   - What's unclear: Whether user needs this feature. Not mentioned in requirements.
   - Recommendation: Document the feature exists in .env.example comments, but don't use it unless user requests. Adds complexity to understanding config values.

4. **Config Reload / Hot Reload**
   - What we know: User's phase focuses on startup validation. No mention of runtime config reload.
   - What's unclear: Whether the application should support reloading config without restart (useful for changing poll interval without downtime).
   - Recommendation: Out of scope for this phase. Config is loaded once at startup. If hot reload is needed later, it's a separate feature (probably involves signal handling and re-validation).

## Sources

### Primary (HIGH confidence)
- python-dotenv GitHub (v1.2.1): https://github.com/theskumar/python-dotenv - API, behavior, override semantics
- python-dotenv PyPI: https://pypi.org/project/python-dotenv/ - Current version (1.2.1, October 2025)
- python-dotenv official docs: https://saurabh-kumar.com/python-dotenv/ - Best practices, placement, format rules
- Python dataclasses documentation: https://docs.python.org/3/library/dataclasses.html - `__post_init__` usage, validation patterns
- Twelve-Factor App (Config section): https://12factor.net/config - Environment variable principles

### Secondary (MEDIUM confidence)
- Pydantic Settings documentation: https://docs.pydantic.dev/latest/concepts/pydantic_settings/ - Type conversion behavior, comparison point
- Best Practices for Python Env Variables (Dagster): https://dagster.io/blog/python-environment-variables - Type conversion, validation patterns
- Managing Secrets and API Keys (KDnuggets): https://www.kdnuggets.com/managing-secrets-and-api-keys-in-python-projects-env-guide - Secret handling, .gitignore patterns
- Settings object using dataclasses: https://roderik.no/python-settings-revisited - Dataclass configuration patterns

### Tertiary (LOW confidence)
- Community discussions on python-dotenv boolean parsing (GitHub Issues #291, #86): Workarounds and pain points
- Various Medium and Dev.to articles on environment variables: General patterns, not authoritative but consistent

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - python-dotenv is locked decision, version verified from PyPI (1.2.1, Oct 2025)
- Architecture: HIGH - Patterns from official docs (Python dataclasses, python-dotenv README), twelve-factor methodology
- Pitfalls: HIGH - Boolean truthiness, type conversion, and load timing issues verified in official docs and GitHub issues
- Code examples: HIGH - All examples based on official documentation or well-established community patterns

**Research date:** 2026-02-05
**Valid until:** ~2026-04-05 (60 days) - python-dotenv is stable library, unlikely to change significantly. Python stdlib (dataclasses) extremely stable.

**Notes:**
- User locked decisions constraining research scope: use python-dotenv (not alternatives), single Config dataclass, error accumulation, SOLAREDGE_ prefix
- Research focused on HOW to implement these decisions well, not WHETHER to use them
- Claude's discretion areas: exact dataclass field names, validation implementation details, config module file structure
