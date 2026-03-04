# Phase 3: Location and Test Parameters - Research

**Researched:** 2026-03-04
**Domain:** GTMetrix API v2.0 location endpoints, test parameter extension, in-memory caching
**Confidence:** HIGH

## Summary

Phase 3 adds location selection to the existing `gtmetrix_analyze` tool. The GTMetrix API v2.0 provides a `GET /locations` endpoint that returns all available test locations as a JSON:API list. Each location has an ID, name, region, default flag, and list of compatible browser IDs. When creating a test via `POST /tests`, the location is passed as a `location` attribute in the JSON:API body alongside the URL.

The scope is intentionally small: extend `start_test()` to accept an optional `location` parameter, add a `list_locations()` client method, cache the result in memory on the `GTMetrixClient` instance, and add validation that returns a structured error with available locations when an invalid ID is given. The existing codebase patterns (structured error dicts, `_impl` functions, `unwrap_jsonapi` parser) apply directly. The one new concern is that `unwrap_jsonapi()` currently handles single-resource JSON:API responses (`data` is a dict), but the locations endpoint returns a list (`data` is an array). A new `unwrap_jsonapi_list()` parser function is needed.

This phase requires no new dependencies. The entire implementation is a small extension of the Phase 2 client and tool code.

**Primary recommendation:** Add `list_locations()` and `unwrap_jsonapi_list()`, cache locations on the client instance with a simple `dict | None` pattern, extend `start_test()` to accept `location`, and validate location IDs before sending the test request.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEST-04 | User can specify test location via location parameter | `POST /tests` accepts `location` attribute in JSON:API body; `gtmetrix_analyze` tool needs optional `location` parameter -- see API Details and Code Examples |
| TEST-05 | Location IDs fetched from API and cached in memory | `GET /locations` returns all locations as JSON:API list; cache on GTMetrixClient instance with `_locations_cache: dict | None` pattern -- see Caching Pattern |
</phase_requirements>

---

## Standard Stack

### Core (already installed from Phase 1)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | 0.28.1 | Async HTTP for locations and test API calls | Already configured with auth, JSON:API headers |
| `mcp` | 1.26.0 | FastMCP tool registration | Already wired in main.py |

### Supporting (no new dependencies)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `logging` | stdlib | Debug logging for cache hits/misses | Already configured to stderr |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Instance-level `dict` cache | `functools.lru_cache` | `lru_cache` does not work with async methods and requires hashable args; a simple `_cache` attribute is cleaner |
| TTL-based cache expiry | Simple `None`-check cache | Locations change rarely (months/years); TTL adds complexity for no benefit. Cache lives as long as the server process. |

**Installation:** No new packages needed.

---

## Architecture Patterns

### Recommended Project Structure (Phase 3 additions)

```
gtmetrix-mcp-server/
├── main.py                  # No changes needed
├── client/
│   ├── gtmetrix.py          # Add: list_locations(), extend start_test() with location param
│   └── parsers.py           # Add: unwrap_jsonapi_list()
├── tools/
│   └── analyze.py           # Extend: _analyze_impl() and tool to accept location param, validate location
└── tests/
    ├── conftest.py           # Add: mock location response fixtures
    ├── test_parsers.py       # Add: test_unwrap_jsonapi_list
    ├── test_client.py        # Add: test_list_locations, test_start_test_with_location
    └── test_analyze.py       # Add: test_analyze_with_location, test_analyze_invalid_location
```

### Pattern 1: JSON:API List Response Parsing

**What:** The locations endpoint returns a JSON:API list response where `data` is an array, not a single object. The existing `unwrap_jsonapi()` only handles single resources.

**When to use:** Any endpoint that returns a collection (locations, browsers).

```python
# Source: GTMetrix API v2.0 docs (JSON:API v1.1 convention)
def unwrap_jsonapi_list(response: dict) -> list[dict]:
    """Strip JSON:API envelope from a list response.

    Returns a list of flat dicts, each with 'id', 'type', and all attributes.
    """
    data = response.get("data")
    if not data or not isinstance(data, list):
        return []
    return [
        {"id": item.get("id"), "type": item.get("type"), **item.get("attributes", {})}
        for item in data
    ]
```

### Pattern 2: In-Memory Cache on Client Instance

**What:** Cache locations on the `GTMetrixClient` instance. First call fetches from API; subsequent calls return cached data. Cache lives for the lifetime of the server process.

**When to use:** Data that changes rarely and is fetched repeatedly (locations, browsers).

```python
class GTMetrixClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._locations_cache: list[dict] | None = None  # Phase 3

    async def list_locations(self) -> list[dict]:
        """Fetch available test locations, cached in memory."""
        if self._locations_cache is not None:
            return self._locations_cache
        assert self._client is not None
        response = await self._client.get("/locations")
        response.raise_for_status()
        self._locations_cache = unwrap_jsonapi_list(response.json())
        return self._locations_cache
```

**Why instance-level cache:** The client instance is created once in the lifespan context manager and shared across all tool invocations. Instance-level state is the natural place for caching. No globals, no module-level state, no external cache library.

### Pattern 3: Location Validation Before Test Creation

**What:** Validate the location ID against the cached location list before sending the POST /tests request. If invalid, return a structured error listing available locations.

```python
async def _validate_location(client, location: str) -> dict | None:
    """Validate location ID. Returns error dict if invalid, None if valid."""
    locations = await client.list_locations()
    valid_ids = {loc["id"] for loc in locations}
    if location not in valid_ids:
        available = [
            {"id": loc["id"], "name": loc.get("name", ""), "region": loc.get("region", "")}
            for loc in locations
        ]
        return {
            "error": f"Invalid location: '{location}'",
            "hint": "Use one of the available location IDs listed below",
            "available_locations": available,
        }
    return None
```

### Pattern 4: Extending start_test() with Optional Location

**What:** The `start_test()` method accepts an optional `location` parameter. When provided, it is included in the JSON:API attributes.

```python
async def start_test(self, url: str, *, location: str | None = None) -> dict:
    """Start a new GTMetrix test. Optionally specify a test location."""
    assert self._client is not None
    attributes = {"url": url}
    if location is not None:
        attributes["location"] = location
    payload = {
        "data": {
            "type": "test",
            "attributes": attributes,
        }
    }
    response = await self._client.post("/tests", json=payload)
    response.raise_for_status()
    return unwrap_jsonapi(response.json())
```

### Anti-Patterns to Avoid

- **Global/module-level cache dict:** Use instance-level cache on the client. Module-level state is harder to test and reset.
- **Cache with TTL for locations:** Over-engineering. Locations change at most a few times per year. The server process restarts frequently enough.
- **Fetching locations on every test request:** Defeats the purpose. Fetch once, cache forever (for the process lifetime).
- **Raising ValueError for invalid location:** Must return structured error dict, not raise. Follows project convention.
- **Validating location server-side only:** Client-side validation provides better error messages with the available locations list. The API would return a generic 400 error.

---

## GTMetrix API: Location Endpoint Details

### GET /locations -- List Available Locations

**Endpoint:** `GET /api/2.0/locations`

**Response:** JSON:API list (not paginated -- returns all locations at once).

**Location resource attributes:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Location identifier (e.g., numeric ID like `"1"`, `"2"`) |
| `name` | string | Human-readable name (e.g., `"Vancouver, Canada"`) |
| `region` | string | Geographic region grouping (e.g., `"North America"`, `"Europe"`, `"Asia Pacific"`) |
| `default` | bool | Whether this is the account's default location |
| `account_has_access` | bool | Whether the current account plan has access to this location |
| `browsers` | list[int] | Browser IDs available at this location |
| `ips` | list[str] | IP addresses for this location (for allowlisting) |

**Expected response structure:**

```json
{
  "data": [
    {
      "type": "location",
      "id": "1",
      "attributes": {
        "name": "Vancouver, Canada",
        "region": "North America",
        "default": true,
        "account_has_access": true,
        "browsers": [1, 3],
        "ips": ["172.255.48.130", "172.255.48.131"]
      }
    },
    {
      "type": "location",
      "id": "2",
      "attributes": {
        "name": "London, UK",
        "region": "Europe",
        "default": false,
        "account_has_access": true,
        "browsers": [1, 3],
        "ips": ["52.56.101.30"]
      }
    }
  ]
}
```

**Note on access:** Basic accounts may not have access to all locations. The `account_has_access` field indicates availability. When displaying available locations in error messages, filter to locations where `account_has_access` is `true`.

### POST /tests -- Location Parameter

When creating a test, pass `location` as an attribute:

```json
{
  "data": {
    "type": "test",
    "attributes": {
      "url": "https://example.com",
      "location": "2"
    }
  }
}
```

If `location` is omitted, GTMetrix uses the account's default location.

**Error on invalid location:** The API returns HTTP 400 with error code `E40004` ("Invalid parameter"). Our client-side validation provides a better UX by listing valid locations.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON:API list parsing | Custom recursive walker | `unwrap_jsonapi_list()` (simple list comprehension) | Straightforward; same pattern as `unwrap_jsonapi` but for arrays |
| Location caching | Redis, SQLite, file-based cache | Instance attribute `_locations_cache` | Process-lifetime cache is sufficient; locations change rarely |
| Location validation | Rely on API 400 error | Pre-validate against cached list | Better error messages with available locations; saves an API round-trip |

**Key insight:** This phase is a small extension, not a new subsystem. The caching and validation logic combined is roughly 30 lines of code.

---

## Common Pitfalls

### Pitfall 1: unwrap_jsonapi() Fails on List Responses

**What goes wrong:** The existing `unwrap_jsonapi()` expects `data` to be a dict (single resource). The locations endpoint returns `data` as a list. Calling `data.get("id")` on a list crashes.

**Why it happens:** Phase 1 only dealt with single-resource responses.

**How to avoid:** Create `unwrap_jsonapi_list()` for collection endpoints. Do not modify the existing `unwrap_jsonapi()` -- keep both functions for clarity.

**Warning signs:** `AttributeError: 'list' object has no attribute 'get'` when parsing locations response.

### Pitfall 2: Caching Locations Without Filtering by Access

**What goes wrong:** The cache contains all locations including ones the account cannot access. When listing available locations in an error message, inaccessible locations confuse the user.

**Why it happens:** The API returns all locations regardless of account access level.

**How to avoid:** When displaying available locations (e.g., in error messages), filter to `account_has_access == True`. Store all locations in cache (the access field may be useful), but filter on display.

### Pitfall 3: Location ID Type Mismatch

**What goes wrong:** Location IDs from the API are strings (e.g., `"1"`, `"2"`). If the user passes an integer or the tool parameter is typed as `int`, the validation comparison fails.

**Why it happens:** JSON:API resource IDs are always strings. But users may type `location=1` instead of `location="1"`.

**How to avoid:** Accept `location` as `str` in the tool signature. Convert to string internally if needed: `location = str(location)`.

### Pitfall 4: Cache Not Reset Between Tests

**What goes wrong:** Not a real problem in production (cache should persist). But in tests, shared cache state between test cases causes flaky tests.

**Why it happens:** If using a module-level mock client across tests, the cache persists between test functions.

**How to avoid:** Use fresh mock client instances per test (already the pattern in conftest.py with function-scoped fixtures). The cache attribute initializes to `None` in `__init__`.

---

## Code Examples

### Complete Location Validation Flow (tools/analyze.py extension)

```python
# Source: GTMetrix API v2.0 docs + project patterns

async def _analyze_impl(client, url: str, location: str | None = None) -> dict:
    """Core analyze logic with optional location parameter."""
    try:
        # Validate location if provided
        if location is not None:
            location = str(location)
            locations = await client.list_locations()
            valid_ids = {loc["id"] for loc in locations}
            if location not in valid_ids:
                accessible = [
                    {"id": loc["id"], "name": loc.get("name", ""), "region": loc.get("region", "")}
                    for loc in locations
                    if loc.get("account_has_access", False)
                ]
                return {
                    "error": f"Invalid location: '{location}'",
                    "hint": "Use one of the available location IDs listed below",
                    "available_locations": accessible,
                }

        # Start test (with optional location)
        test = await client.start_test(url, location=location)
        # ... rest of existing analyze flow unchanged ...
    except ...:
        # ... existing error handling unchanged ...
```

### Tool Registration Extension

```python
# In tools/analyze.py register() function:
@mcp.tool()
async def gtmetrix_analyze(url: str, location: str | None = None, *, ctx: Context) -> dict:
    """Analyze a URL's performance with GTMetrix.

    Args:
        url: The URL to analyze.
        location: Optional test location ID. Use gtmetrix_list_locations()
                  to see available locations. Defaults to account default.
    """
    client = ctx.request_context.lifespan_context["client"]
    return await _analyze_impl(client, url, location=location)
```

### Optional: Standalone List Locations Tool

```python
# Consider adding a separate tool so Claude can discover locations:
@mcp.tool()
async def gtmetrix_list_locations(ctx: Context) -> dict:
    """List available GTMetrix test locations.

    Returns location IDs, names, and regions. Use the ID when specifying
    a location in gtmetrix_analyze().
    """
    client = ctx.request_context.lifespan_context["client"]
    try:
        locations = await client.list_locations()
        accessible = [
            {"id": loc["id"], "name": loc.get("name", ""), "region": loc.get("region", "")}
            for loc in locations
            if loc.get("account_has_access", False)
        ]
        return {"locations": accessible, "count": len(accessible)}
    except httpx.HTTPStatusError as exc:
        return {"error": "Failed to fetch locations", "hint": f"HTTP {exc.response.status_code}"}
```

**Note:** A `gtmetrix_list_locations` tool is not explicitly required by TEST-04/TEST-05, but it enables Claude to discover available locations interactively, which makes the `location` parameter on `gtmetrix_analyze` much more useful. Recommend including it.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Numeric location IDs (v0.1: `location=1`) | String location IDs in JSON:API (v2.0: `"location": "1"`) | GTMetrix API v2.0 (2020) | IDs are strings in JSON:API; always use string type |
| Separate location/browser per endpoint | All test params in single POST /tests attributes | GTMetrix API v2.0 | Simpler; one JSON:API body with all options |

**Deprecated/outdated:**
- API v0.1 location format (integer IDs, non-JSON:API): Superseded by v2.0 string IDs in JSON:API envelope.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEST-04 | `gtmetrix_analyze(url, location=...)` passes location to `start_test()` and runs test from that region | unit | `uv run pytest tests/test_analyze.py::test_analyze_with_location -x` | No - Wave 0 |
| TEST-04 | Invalid location returns structured error listing available locations | unit | `uv run pytest tests/test_analyze.py::test_analyze_invalid_location -x` | No - Wave 0 |
| TEST-05 | `list_locations()` fetches from API on first call | unit | `uv run pytest tests/test_client.py::test_list_locations -x` | No - Wave 0 |
| TEST-05 | `list_locations()` returns cached data on subsequent calls (no HTTP) | unit | `uv run pytest tests/test_client.py::test_list_locations_cached -x` | No - Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_client.py` additions -- test_list_locations, test_list_locations_cached, test_start_test_with_location
- [ ] `tests/test_analyze.py` additions -- test_analyze_with_location, test_analyze_invalid_location
- [ ] `tests/test_parsers.py` additions -- test_unwrap_jsonapi_list
- [ ] `tests/conftest.py` additions -- mock location list response fixture

---

## Open Questions

1. **Exact location ID format in API v2.0**
   - What we know: v0.1 used numeric IDs (1, 2, 3...). v2.0 uses JSON:API where IDs are strings. The nodejs-gtmetrix library shows `id: '1'`.
   - What's unclear: Whether v2.0 IDs are still numeric strings (`"1"`, `"2"`) or have changed to slugs (`"vancouver-canada"`). The official docs do not show a concrete example.
   - Recommendation: Accept any string. Validate against the cached list by exact match. The actual ID format does not affect implementation -- we compare strings regardless.
   - Confidence: MEDIUM -- implementation is format-agnostic, so this is a documentation gap, not a risk.

2. **Should we also add a `gtmetrix_list_locations` standalone tool?**
   - What we know: Requirements only specify TEST-04 (location param) and TEST-05 (cache). A standalone tool is not required.
   - What's unclear: Whether Claude can effectively use the location parameter without a way to discover valid IDs first.
   - Recommendation: Include `gtmetrix_list_locations` as a convenience tool. It makes the location feature actually usable by Claude. Low effort (~10 lines), high value.

3. **Browser parameter (deferred to v2)**
   - What we know: `POST /tests` also accepts a `browser` attribute. OPTS-02 (simulated devices) is deferred to v2.
   - Recommendation: Do not add browser parameter now. But `start_test()` can be structured to accept `**kwargs` for future extensibility, or just add `browser` when needed later.

---

## Sources

### Primary (HIGH confidence)
- [GTMetrix REST API v2.0 docs](https://gtmetrix.com/api/docs/2.0/) -- locations endpoint, test parameters, JSON:API format, error codes
- [GTMetrix test server locations page](https://gtmetrix.com/locations.html) -- 25 global locations across 6 regions
- Phase 1 and Phase 2 codebase -- existing patterns, client structure, parser functions

### Secondary (MEDIUM confidence)
- [nodejs-gtmetrix library](https://github.com/fvdm/nodejs-gtmetrix) -- location response structure example (`id`, `name`, `default`, `browsers`)
- [python-gtmetrix2 docs](https://python-gtmetrix2.readthedocs.io/) -- confirms `location` parameter usage in test creation

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies; pure extension of existing code
- Architecture: HIGH -- follows established patterns from Phase 1/2; caching is trivial
- API endpoints: HIGH -- locations endpoint and test location parameter verified from official docs
- Location ID format: MEDIUM -- exact format not shown in docs sample, but implementation is format-agnostic
- Pitfalls: HIGH -- derived from code analysis and JSON:API spec understanding

**Research date:** 2026-03-04
**Valid until:** 2026-06-04 (stable API; locations endpoint unlikely to change)
