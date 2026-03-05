# Phase 4: Docs & Options from Todo - Research

**Researched:** 2026-03-05
**Domain:** GTMetrix API test parameters, documentation, changelog
**Confidence:** HIGH

## Summary

This phase adds three test parameters (adblock, browser, simulated device) to the existing `gtmetrix_analyze` tool, creates a CHANGELOG, and updates the README. The GTMetrix API v2.0 supports all three parameters as attributes on `POST /tests`. Browser and simulated device values come from API endpoints (`GET /browsers`, `GET /simulated-devices`), while adblock is a simple `0`/`1` flag. Simulated devices are PRO-only.

The existing codebase has clean, consistent patterns: `config.py` with pydantic-settings, `start_test()` kwargs passed into an `attributes` dict, and the `_analyze_impl()` function signature with `str | None = None` optional params. All three new parameters follow this exact pattern with minimal new code.

**Primary recommendation:** Extend the existing parameter pipeline (config field -> `_analyze_impl` kwarg -> `start_test` kwarg -> attributes dict) for each new parameter. Use the user's decided device name mapping (phone/tablet/desktop) with raw ID passthrough fallback. No API-fetched validation for browser/device -- let the API enforce.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Device naming: Three simple category names (phone, tablet, desktop) mapping to GTMetrix device IDs internally. Unknown values pass through as raw GTMetrix device IDs (power user escape hatch). Configurable default via `GTMETRIX_DEFAULT_DEVICE` env var; if unset, don't send device param.
- Default strategy: All params (location, adblock, browser, device) follow same pattern: optional `GTMETRIX_DEFAULT_X` env var. If env var unset, don't send param. Explicit tool param overrides env default. PRO requirements documented in docstring only -- no runtime PRO checks. Adblock: configurable only, no implicit default.
- Changelog format: Keep a Changelog format (keepachangelog.com). Backfill all 3 completed phases as single v1.0 entry. Tool-level detail per entry.
- README updates: Reference tables inline under Reference section. PRO features marked with inline (PRO) tag. Tool table updated with new param signatures. .env.example updated with new default env vars as commented-out lines.

### Claude's Discretion
- Whether device mapping is hardcoded or fetched from API (depends on GTMetrix API structure)
- Exact device ID mappings for phone/tablet/desktop categories
- Changelog entry wording and grouping within the v1.0 section
- Reference table format details (column widths, sorting)

### Deferred Ideas (OUT OF SCOPE)
- Connection throttle presets (3G, 4G, broadband) -- OPTS-01, keep for v2
- Lighthouse audit category filter -- OPTS-03, keep for v2
- Granular tools (separate lighthouse/HAR endpoints) -- GRAN-01, GRAN-02, keep for v2

</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic-settings | >=2.13 | Config with env var loading | Already in use, `extra="ignore"` handles unknown vars |

### Supporting
No new libraries needed. All changes use existing dependencies.

## Architecture Patterns

### Parameter Pipeline (existing pattern to extend)

The codebase has an established pipeline for optional test parameters. Location already follows it:

```
config.py (Settings field)
  -> tools/analyze.py (_analyze_impl kwarg)
    -> client/gtmetrix.py (start_test kwarg)
      -> POST /tests attributes dict
```

**Extend this exact pattern for browser, device, and adblock.**

### Pattern 1: Config Field with Optional Default

**What:** Add `Optional[str]` fields to Settings for each env var default.
**When to use:** Every new configurable parameter.
**Example:**
```python
# config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    gtmetrix_api_key: str
    gtmetrix_default_location: str | None = None
    gtmetrix_default_browser: str | None = None
    gtmetrix_default_device: str | None = None
    gtmetrix_default_adblock: str | None = None  # "0" or "1"
```

### Pattern 2: Default Resolution in _analyze_impl

**What:** Tool param > env var > no value (don't send).
**Example:**
```python
async def _analyze_impl(
    client, url: str, *,
    location: str | None = None,
    browser: str | None = None,
    device: str | None = None,
    adblock: str | None = None,
    config=None,  # injected for testing, defaults to global settings
) -> dict:
    from config import settings as default_settings
    cfg = config or default_settings

    # Resolve defaults: explicit param > env var > None (don't send)
    effective_browser = browser if browser is not None else cfg.gtmetrix_default_browser
    effective_device = device if device is not None else cfg.gtmetrix_default_device
    effective_adblock = adblock if adblock is not None else cfg.gtmetrix_default_adblock
```

### Pattern 3: Device Name Mapping (Hardcoded)

**What:** Map simple names to GTMetrix device IDs. Pass unknown values through as raw IDs.
**Recommendation:** Hardcode the mapping. The GTMetrix API has 50+ device IDs from `GET /simulated-devices` but they change infrequently. Fetching and caching adds complexity for minimal benefit. The passthrough fallback ensures power users can always use any device ID directly.

**Example device mappings** (based on GTMetrix API simulated device reference):
```python
DEVICE_ALIASES = {
    "phone": "iphone_16",      # Modern default phone
    "tablet": "ipad_air",      # Modern default tablet
    "desktop": None,            # No simulate_device param = desktop (default behavior)
}

def resolve_device(device_input: str | None) -> str | None:
    if device_input is None:
        return None
    # Check alias map first, then pass through as raw ID
    if device_input.lower() in DEVICE_ALIASES:
        return DEVICE_ALIASES[device_input.lower()]
    return device_input  # Raw GTMetrix device ID
```

Note: "desktop" maps to `None` because not sending `simulate_device` at all means GTMetrix runs as desktop (the default behavior).

### Pattern 4: Extending start_test kwargs

**What:** Add new kwargs to `start_test()` and include them in the attributes dict.
**Example:**
```python
async def start_test(
    self, url: str, *,
    location: str | None = None,
    browser: str | None = None,
    adblock: int | None = None,
    simulate_device: str | None = None,
) -> dict:
    attributes: dict = {"url": url}
    if location is not None:
        attributes["location"] = location
    if browser is not None:
        attributes["browser"] = browser
    if adblock is not None:
        attributes["adblock"] = adblock
    if simulate_device is not None:
        attributes["simulate_device"] = simulate_device
    # ... rest of method
```

### Anti-Patterns to Avoid
- **Don't validate browser/device IDs against API:** Adds complexity, caching burden, and latency. Let the GTMetrix API return errors for invalid IDs. Document valid values in README instead.
- **Don't add runtime PRO account checks:** The API enforces PRO requirements. Adding checks means maintaining feature-gate logic that may change. Document PRO requirements in tool docstrings only.
- **Don't use boolean for adblock:** The GTMetrix API uses `0`/`1` integer. Keep it as string in config/params, convert to int for API. Booleans cause env var parsing ambiguity.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Env var defaults | Custom argparse/env loading | pydantic-settings `Optional[str]` fields | Already in use, handles type coercion and `.env` files |
| Changelog format | Custom template | Keep a Changelog format manually | It's a text file; no tooling needed for a one-time backfill |

## Common Pitfalls

### Pitfall 1: Adblock Type Mismatch
**What goes wrong:** Sending `adblock=True` or `adblock="true"` instead of `adblock=1`.
**Why it happens:** Python booleans vs GTMetrix's `0`/`1` integer.
**How to avoid:** Accept string "0"/"1" in config and tool param. Convert to `int` when building API attributes dict.
**Warning signs:** API returns 400 or ignores the parameter silently.

### Pitfall 2: Desktop Device Mapping
**What goes wrong:** Sending `simulate_device="desktop"` to the API, which is not a valid device ID.
**Why it happens:** User expects "desktop" as a valid device choice.
**How to avoid:** Map "desktop" to `None` (don't send param). GTMetrix default behavior without `simulate_device` IS desktop.
**Warning signs:** API 400 error mentioning invalid simulated_device.

### Pitfall 3: Config Import at Module Level
**What goes wrong:** Importing `settings` at module level in `_analyze_impl` makes testing harder.
**Why it happens:** Need defaults from config but also need testability.
**How to avoid:** Accept an optional `config` parameter in `_analyze_impl` that defaults to the global `settings` object. Tests can pass mock config.

### Pitfall 4: Changelog Missing Entries
**What goes wrong:** Backfilling v1.0 changelog but missing some features from earlier phases.
**Why it happens:** Not checking all phases for what was actually built.
**How to avoid:** Review STATE.md decisions and each phase's context/plans for comprehensive feature list.

## Code Examples

### GTMetrix API: Test Attributes
```python
# Source: https://gtmetrix.com/api/docs/2.0/
# POST /api/2.0/tests attributes:
{
    "url": "https://example.com",
    "location": "1",          # Location ID (optional)
    "browser": "3",           # Browser ID (optional)
    "adblock": 1,             # 0 or 1 (optional)
    "simulate_device": "iphone_16",  # Device ID, PRO only (optional)
}
```

### GTMetrix API Defaults
```
# Source: https://gtmetrix.com/api/docs/2.0/
location: user's default (typically 24)
browser: user's default (typically 3)
adblock: 0 (disabled)
simulate_device: not sent = desktop
```

### Keep a Changelog Format
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-03-05

### Added
- `gtmetrix_analyze(url)` tool: full performance analysis with Core Web Vitals, Lighthouse audits, and resource waterfall
- `gtmetrix_check_status()` tool: API credits and account info
- `gtmetrix_list_locations()` tool: available test locations
- Location parameter for `gtmetrix_analyze` with validation
- Browser, device, and adblock parameters for `gtmetrix_analyze`
- Configurable parameter defaults via environment variables
- Automatic polling with 3-second intervals and 5-minute timeout
- Structured error responses with actionable hints
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GTMetrix API v1 | GTMetrix API v2.0 (JSON:API) | ~2022 | v1 deprecated; all code uses v2 |
| YSlow scores | Lighthouse audits | ~2022 | Report type defaults to "lighthouse" |

## Open Questions

1. **Exact device ID for "phone" and "tablet" aliases**
   - What we know: GTMetrix has 50+ device IDs (iphone_16, iphone_16_pro, ipad_air, etc.)
   - What's unclear: Which specific IDs are the best "generic" choices for the simplified aliases
   - Recommendation: Use `iphone_16` for phone and `ipad_air` for tablet. These are current-gen, widely representative devices. The passthrough escape hatch covers everything else. If the IDs become outdated, updating two strings in a dict is trivial.

2. **Browser IDs available to the account**
   - What we know: `GET /browsers` returns available browsers. Documentation doesn't enumerate IDs publicly.
   - What's unclear: Exact browser IDs (likely numeric strings like "1", "3", etc.)
   - Recommendation: Don't validate browser IDs. Accept any value and let the API reject invalid ones. Document in README that users should call `gtmetrix_list_locations()` or check the API for valid browser IDs. The browser parameter is a simple passthrough.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=9.0.2 + pytest-asyncio >=1.3.0 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| (none) | adblock param passed to API | unit | `uv run pytest tests/test_analyze.py -x -k adblock` | No - Wave 0 |
| (none) | browser param passed to API | unit | `uv run pytest tests/test_analyze.py -x -k browser` | No - Wave 0 |
| (none) | device alias resolution | unit | `uv run pytest tests/test_analyze.py -x -k device` | No - Wave 0 |
| (none) | device passthrough (raw ID) | unit | `uv run pytest tests/test_analyze.py -x -k device` | No - Wave 0 |
| (none) | env var default resolution | unit | `uv run pytest tests/test_analyze.py -x -k default` | No - Wave 0 |
| (none) | explicit param overrides env default | unit | `uv run pytest tests/test_analyze.py -x -k override` | No - Wave 0 |
| (none) | config new fields | unit | `uv run pytest tests/test_config.py -x` | Partial (existing config tests) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_analyze.py` -- new tests for browser, device, adblock params (add to existing file)
- [ ] `tests/test_config.py` -- test new optional config fields (add to existing file)
- [ ] No new test files needed -- extend existing test files

## Sources

### Primary (HIGH confidence)
- GTMetrix API v2.0 official docs (https://gtmetrix.com/api/docs/2.0/) -- test attributes, browser/device endpoints, adblock parameter, PRO requirements
- Existing codebase -- config.py, tools/analyze.py, client/gtmetrix.py patterns

### Secondary (MEDIUM confidence)
- GTMetrix simulated devices reference -- specific device IDs (iphone_16, ipad_air, etc.)
- Keep a Changelog format (https://keepachangelog.com/) -- changelog structure

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, extending existing patterns
- Architecture: HIGH -- follows established codebase patterns exactly
- Pitfalls: HIGH -- based on GTMetrix API docs and Python type system knowledge
- API parameters: HIGH -- verified against official GTMetrix API v2.0 documentation

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable -- GTMetrix API v2 and pydantic-settings are mature)
