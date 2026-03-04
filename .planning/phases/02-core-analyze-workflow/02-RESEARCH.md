# Phase 2: Core Analyze Workflow - Research

**Researched:** 2026-03-04
**Domain:** GTMetrix API v2.0 test execution, polling, report parsing (Lighthouse + HAR)
**Confidence:** HIGH

## Summary

Phase 2 implements the `gtmetrix_analyze(url)` mega-tool: a single tool call that creates a GTMetrix test, polls until completion (or timeout), then fetches the report and two sub-resources (Lighthouse JSON and HAR), extracts the relevant data, and returns a single structured dict to Claude. The existing codebase from Phase 1 provides a solid foundation -- `GTMetrixClient` with async context manager, `unwrap_jsonapi()` parser, the lifespan pattern, and the tool registration pattern.

The GTMetrix API workflow is: POST /tests (returns 202 with test ID) -> poll GET /tests/{id} every 3s (returns 200 while running, 303 redirect to report when done) -> GET /reports/{id} for Core Web Vitals -> GET /reports/{id}/resources/lighthouse.json for audit details -> GET /reports/{id}/resources/net.har for resource waterfall. The 303 redirect is already handled by `follow_redirects=True` on the httpx client, so polling GET on the test endpoint will automatically follow to the report when complete.

The key challenge is filtering: the raw Lighthouse JSON can be 200KB+ and the HAR file 1-2MB. The tool must extract only failing audits (score < 1) and the top 10 slowest/largest resources, returning a context-friendly response that Claude can reason about without overwhelming the context window.

**Primary recommendation:** Build three layers: client methods (start_test, poll_test, get_report, get_lighthouse, get_har), parser functions (extract_vitals, filter_failing_audits, extract_top_resources), and a single tool function that orchestrates the flow. Keep parsing logic in `client/parsers.py` as pure functions for easy unit testing.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEST-01 | User can start a GTMetrix test for any URL via `gtmetrix_analyze(url)` | POST /tests with JSON:API body; tool wiring via FastMCP -- see API Flow and Code Examples |
| TEST-02 | Test polls automatically every 3 seconds until completion | `asyncio.sleep(3)` loop checking `state` field; API sends `Retry-After: 3` header -- see Polling Pattern |
| TEST-03 | Polling has a hard timeout (default 5 minutes) to prevent hangs | `asyncio.wait_for()` or manual elapsed-time check -- see Polling Pattern |
| REPT-01 | Report returns Core Web Vitals: LCP, TBT, CLS, performance score, structure score | Report attributes contain `largest_contentful_paint`, `total_blocking_time`, `cumulative_layout_shift`, `performance_score`, `structure_score` -- see Report Schema |
| REPT-02 | Report returns failing Lighthouse audits (score < 1) with title, description, displayValue | GET lighthouse.json, filter audits where `score < 1 and score is not None`, extract `title`, `description`, `displayValue` -- see Lighthouse Parsing |
| REPT-03 | Report returns top 10 slowest/largest resources from HAR waterfall | GET net.har, parse `entries[]`, sort by `time` (duration) and `response._transferSize`, take top 10 -- see HAR Parsing |
| REPT-04 | All report data returned in a single structured response from `gtmetrix_analyze` | Orchestrator function combines vitals + audits + resources into one dict -- see Architecture |
</phase_requirements>

---

## Standard Stack

### Core (already installed from Phase 1)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | 0.28.1 | Async HTTP for all API calls | Already configured with auth, JSON:API headers, redirect following |
| `mcp` | 1.26.0 | FastMCP tool registration | Already wired in main.py |
| `asyncio` | stdlib | `asyncio.sleep()` for polling, timeout control | Built-in; no additional deps needed |

### Supporting (no new dependencies)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `time` | stdlib | `time.monotonic()` for timeout tracking | Polling loop elapsed time |
| `logging` | stdlib | Debug logging during poll cycles | Already configured to stderr |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual poll loop with `time.monotonic()` | `asyncio.wait_for()` wrapping the poll loop | `wait_for` raises `TimeoutError` which requires extra exception handling; manual check is simpler and gives better error messages |
| Parsing full HAR in Python | Using `haralyzer` library | Unnecessary dependency for extracting 10 fields; direct dict access is cleaner |

**Installation:** No new packages needed. All Phase 2 work uses existing dependencies.

---

## Architecture Patterns

### Recommended Project Structure (Phase 2 additions)

```
gtmetrix-mcp-server/
├── main.py                  # Add: import tools.analyze, register
├── config.py                # No changes
├── client/
│   ├── gtmetrix.py          # Add: start_test(), get_test(), get_report(), get_resource()
│   └── parsers.py           # Add: extract_vitals(), filter_failing_audits(), extract_top_resources()
├── tools/
│   ├── account.py           # No changes
│   └── analyze.py           # NEW: gtmetrix_analyze tool + _analyze_impl()
└── tests/
    ├── conftest.py           # Add: mock fixtures for test/report/lighthouse/HAR responses
    ├── test_parsers.py       # Add: tests for new parser functions
    ├── test_client.py        # Add: tests for new client methods
    └── test_analyze.py       # NEW: integration tests for the full analyze flow
```

### Pattern 1: GTMetrix Test Lifecycle (API Flow)

**What:** The complete API flow from test creation to report data.

**Flow:**
1. `POST /api/2.0/tests` with `{"data": {"type": "test", "attributes": {"url": "..."}}}` -> 202 with test ID
2. `GET /api/2.0/tests/{test_id}` every 3s -> 200 with `state: "queued"|"started"` while running
3. When complete: response is 303 redirect to `/api/2.0/reports/{report_id}` (httpx follows automatically)
4. The followed response contains the report with Core Web Vitals in `data.attributes`
5. Report `data.links` contains paths to `lighthouse.json` and `net.har`
6. `GET /api/2.0/reports/{report_id}/resources/lighthouse.json` -> full Lighthouse JSON
7. `GET /api/2.0/reports/{report_id}/resources/net.har` -> full HAR file

**Key insight:** Because `follow_redirects=True` is already set, the final poll GET will automatically follow the 303 to the report endpoint. The response from `get_test()` when the test is complete IS the report response. This means we may not need a separate `get_report()` call -- the redirect handles it.

**However:** We need to detect whether the response we got back is a test object (`data.type == "test"`) or a report object (`data.type == "report"`). If redirected, we get the report directly. If we parse the response before the redirect (or if httpx gives us the final response), we need to handle both cases.

**Recommended approach:** Always poll the test endpoint. When state is `completed`, extract the report ID from `data.links.report` and explicitly GET the report. This is more explicit and avoids depending on redirect behavior subtleties.

### Pattern 2: Polling with Timeout

**What:** Poll loop with 3-second intervals and hard timeout.

```python
import asyncio
import time

async def poll_test(self, test_id: str, timeout: float = 300.0) -> dict:
    """Poll a test until completion or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = await self._get_test(test_id)
        state = result.get("state")
        if state == "completed":
            return result
        if state == "error":
            raise GTMetrixTestError(result.get("error", "Unknown test error"))
        await asyncio.sleep(3)
    raise GTMetrixTimeoutError(f"Test {test_id} did not complete within {timeout}s")
```

**Why `time.monotonic()` over `asyncio.wait_for()`:** Cleaner error messages, no need to catch `asyncio.TimeoutError` separately, and we can include the test ID and elapsed time in the timeout error.

### Pattern 3: Separate _impl Function for Testability

**What:** Same pattern as `_check_status_impl()` from Phase 1. The tool function is a thin wrapper that extracts the client from context and delegates to `_analyze_impl(client, url)`.

```python
async def _analyze_impl(client, url: str) -> dict:
    """Core logic for gtmetrix_analyze. Separated for testability."""
    try:
        # 1. Start test
        # 2. Poll to completion
        # 3. Fetch report + lighthouse + HAR
        # 4. Parse and combine
        return combined_result
    except GTMetrixTestError as exc:
        return {"error": str(exc), "hint": "..."}
    except GTMetrixTimeoutError as exc:
        return {"error": str(exc), "hint": "..."}
    except Exception as exc:
        return {"error": "Analysis failed", "hint": "...", "detail": str(exc)}
```

### Pattern 4: Resource URL Construction

**What:** Report responses include a `links` object with relative paths to sub-resources. Construct full resource URLs from the report ID.

```python
# Report links come as relative paths:
# "lighthouse": "/api/2.0/reports/{id}/resources/lighthouse"
# But we can construct them directly:
lighthouse_url = f"/reports/{report_id}/resources/lighthouse"
har_url = f"/reports/{report_id}/resources/har"
```

**Note:** The httpx client already has `base_url` set to `https://gtmetrix.com/api/2.0`, so relative paths work directly.

### Anti-Patterns to Avoid

- **Returning raw Lighthouse JSON:** 200KB+ destroys context. Filter to failing audits only.
- **Returning raw HAR:** 1-2MB is unusable. Extract top 10 resources only.
- **Polling without timeout:** Test hangs forever if GTMetrix has an issue.
- **Creating httpx.AsyncClient per request:** Use the shared client from lifespan.
- **Raising exceptions from tool handlers:** Always catch and return structured error dict.
- **Hardcoding poll interval:** Use a constant (default 3s) that matches the API's `Retry-After` header.

---

## GTMetrix API: Detailed Endpoint Reference

### POST /tests -- Create Test

**Request body (JSON:API):**
```json
{
  "data": {
    "type": "test",
    "attributes": {
      "url": "https://example.com"
    }
  }
}
```

Only `url` is required for Phase 2. Location/browser use account defaults when omitted.

**Response (202 Accepted):**
```json
{
  "data": {
    "type": "test",
    "id": "KtbMoPEq",
    "attributes": {
      "source": "api",
      "state": "queued",
      "created": 1617680457
    }
  },
  "meta": {
    "credits_left": 121.2,
    "credits_used": 2.8
  }
}
```

The `meta` block contains credit usage info. Worth including `credits_left` in the response to Claude.

### GET /tests/{id} -- Poll Status

**States:** `queued` -> `started` -> `completed` | `error`

**Completed test response includes `links.report`** pointing to the report resource.

### GET /reports/{id} -- Report Data

**Key attributes for REPT-01:**

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `performance_score` | int | 0-100 | Lighthouse performance score |
| `structure_score` | int | 0-100 | GTMetrix structure score |
| `largest_contentful_paint` | int | ms | LCP |
| `total_blocking_time` | int | ms | TBT |
| `cumulative_layout_shift` | float | unitless | CLS |

Additional metrics available but not required: `first_contentful_paint`, `time_to_interactive`, `speed_index`, `onload_time`, `fully_loaded_time`.

### GET /reports/{id}/resources/lighthouse.json -- Lighthouse Audits

Returns standard Lighthouse JSON format. Audit structure:

```json
{
  "audits": {
    "audit-id": {
      "id": "audit-id",
      "title": "Human-readable title",
      "description": "Why this matters. [Learn more](url)",
      "score": 0.45,
      "scoreDisplayMode": "numeric",
      "displayValue": "3,200 ms",
      "details": { ... }
    }
  }
}
```

**Filtering logic for REPT-02:**
- Include audits where `score is not None and score < 1`
- Skip audits with `scoreDisplayMode == "notApplicable"` or `scoreDisplayMode == "manual"`
- Extract only: `title`, `description`, `displayValue`, `score`
- Do NOT include `details` (can be huge: tables of resources, screenshots, etc.)

### GET /reports/{id}/resources/net.har -- HAR Waterfall

Standard HAR 1.2 format. Key fields per entry:

```json
{
  "log": {
    "entries": [
      {
        "request": {
          "url": "https://example.com/style.css",
          "method": "GET"
        },
        "response": {
          "status": 200,
          "_transferSize": 45678
        },
        "time": 234.5,
        "timings": {
          "blocked": 0.5,
          "dns": 10.2,
          "connect": 50.1,
          "ssl": 30.0,
          "send": 0.3,
          "wait": 120.4,
          "receive": 23.0
        }
      }
    ]
  }
}
```

**Extraction logic for REPT-03:**
- Sort entries by `time` (total duration in ms) descending
- Take top 10
- For each: extract `request.url`, `response._transferSize` (bytes), `time` (ms)
- Truncate long URLs to keep response readable

**Note:** The `_transferSize` field uses an underscore prefix because it is a HAR extension (not in the base HAR 1.2 spec). GTMetrix includes it. If missing, fall back to `response.bodySize + response.headersSize` or report `null`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Lighthouse JSON parsing library | Custom recursive JSON walker | Direct dict access to `audits` key | Lighthouse JSON is a well-defined format; audits are a flat dict keyed by audit ID |
| HAR parsing library | `haralyzer` or custom HAR parser | Direct dict access to `log.entries` | We only need 3 fields per entry; a library adds dependency for no benefit |
| HTTP polling framework | Custom retry/backoff library | Simple `while` loop with `asyncio.sleep(3)` | GTMetrix specifies exactly 3s polling interval; no exponential backoff needed |
| JSON:API request body builder | Generic JSON:API library | Inline dict construction | Only one POST endpoint needs a JSON:API body; a library is overkill |

**Key insight:** The data extraction here is straightforward dict traversal. No parsing libraries needed beyond Python's built-in `json` (which httpx handles via `.json()`).

---

## Common Pitfalls

### Pitfall 1: Lighthouse JSON Size Blows Context Window

**What goes wrong:** Returning full Lighthouse JSON (200KB+) in the tool response overwhelms Claude's context window. Claude loses track of the conversation.

**Why it happens:** The Lighthouse JSON includes `details` objects with tables of resources, screenshots as data URIs, and diagnostic data.

**How to avoid:** Extract only `title`, `description`, `displayValue`, and `score` from failing audits. Never include `details`. Filter to `score < 1` only.

**Warning signs:** Tool response is more than ~5KB of text.

### Pitfall 2: HAR File Size and Missing Fields

**What goes wrong:** HAR files are 1-2MB. Also, some entries may lack `_transferSize` or have `time: 0` for cached resources.

**Why it happens:** GTMetrix includes all sub-resource loads. `_transferSize` is a non-standard HAR extension that may not be present on every entry.

**How to avoid:** Extract top 10 only. Handle missing `_transferSize` by falling back to `response.bodySize` or reporting `null`. Filter out entries with `time <= 0`.

### Pitfall 3: Test Error State Not Handled

**What goes wrong:** If the URL returns a 404, DNS failure, or SSL error, GTMetrix sets `state: "error"` with an error message. If the polling loop only checks for `completed`, it loops until timeout.

**Why it happens:** Only checking `state == "completed"` without checking `state == "error"`.

**How to avoid:** Check for `error` state explicitly in the poll loop and return immediately with the error message.

### Pitfall 4: 303 Redirect Ambiguity

**What goes wrong:** When a test completes, GET /tests/{id} returns 303 redirecting to the report. With `follow_redirects=True`, httpx follows automatically and returns the report response. But the code might expect a test object and try to read `state`.

**Why it happens:** The response body changes from test type to report type after the redirect.

**How to avoid:** After polling, check `data.type` in the response. If it is `"report"`, the redirect was followed and we already have the report. If it is `"test"` with `state: "completed"`, extract the report URL from `links` and fetch separately. Handle both cases.

**Recommended approach:** Detect completion by checking if `data.type == "report"` (redirect was followed) OR `data.attributes.state == "completed"` (no redirect). This is the safest approach.

### Pitfall 5: Credits Exhaustion Mid-Request

**What goes wrong:** POST /tests returns an error when the account has no credits left. The error response differs from normal API errors.

**Why it happens:** GTMetrix API returns 402 Payment Required or a specific error body when credits are exhausted.

**How to avoid:** Handle this specific error case with a clear hint: "No API credits remaining. Credits refill on [date]. Check status with gtmetrix_check_status()."

### Pitfall 6: Rate Limiting (2 Concurrent Tests)

**What goes wrong:** Basic accounts can only run 2 tests simultaneously. Attempting a third returns an error.

**Why it happens:** GTMetrix enforces concurrent test limits per account tier.

**How to avoid:** Return a clear error: "Concurrent test limit reached. Wait for existing tests to complete." Not something we can prevent, but we should handle gracefully.

---

## Code Examples

### Client Methods (client/gtmetrix.py additions)

```python
# Source: GTMetrix REST API v2.0 docs
async def start_test(self, url: str) -> dict:
    """Start a new GTMetrix test for the given URL.

    Returns unwrapped test data including 'id' and 'state'.
    """
    assert self._client is not None
    payload = {
        "data": {
            "type": "test",
            "attributes": {"url": url}
        }
    }
    response = await self._client.post("/tests", json=payload)
    response.raise_for_status()
    return unwrap_jsonapi(response.json())

async def get_test(self, test_id: str) -> dict:
    """Get current test status. Returns unwrapped test or report data."""
    assert self._client is not None
    response = await self._client.get(f"/tests/{test_id}")
    response.raise_for_status()
    return unwrap_jsonapi(response.json())

async def get_report(self, report_id: str) -> dict:
    """Fetch a completed report's data."""
    assert self._client is not None
    response = await self._client.get(f"/reports/{report_id}")
    response.raise_for_status()
    return unwrap_jsonapi(response.json())

async def get_resource(self, report_id: str, resource_name: str) -> dict:
    """Fetch a report sub-resource (lighthouse.json, net.har, etc.).

    Returns the raw JSON response (not JSON:API wrapped).
    """
    assert self._client is not None
    response = await self._client.get(
        f"/reports/{report_id}/resources/{resource_name}"
    )
    response.raise_for_status()
    return response.json()
```

### Parser Functions (client/parsers.py additions)

```python
def extract_vitals(report: dict) -> dict:
    """Extract Core Web Vitals from a report dict."""
    return {
        "performance_score": report.get("performance_score"),
        "structure_score": report.get("structure_score"),
        "largest_contentful_paint_ms": report.get("largest_contentful_paint"),
        "total_blocking_time_ms": report.get("total_blocking_time"),
        "cumulative_layout_shift": report.get("cumulative_layout_shift"),
    }

def filter_failing_audits(lighthouse_json: dict) -> list[dict]:
    """Extract failing Lighthouse audits (score < 1).

    Returns a list of dicts with title, description, displayValue, score.
    Excludes notApplicable and manual audits.
    """
    audits = lighthouse_json.get("audits", {})
    failing = []
    for audit_id, audit in audits.items():
        score = audit.get("score")
        mode = audit.get("scoreDisplayMode", "")
        if score is None or mode in ("notApplicable", "manual", "informative"):
            continue
        if score < 1:
            failing.append({
                "id": audit_id,
                "title": audit.get("title", ""),
                "description": audit.get("description", ""),
                "displayValue": audit.get("displayValue", ""),
                "score": score,
            })
    # Sort by score ascending (worst first)
    failing.sort(key=lambda a: a["score"])
    return failing

def extract_top_resources(har_json: dict, limit: int = 10) -> list[dict]:
    """Extract the top N slowest resources from a HAR file.

    Returns a list of dicts with url, size_bytes, duration_ms.
    Sorted by duration descending.
    """
    entries = har_json.get("log", {}).get("entries", [])
    resources = []
    for entry in entries:
        duration = entry.get("time", 0)
        if duration <= 0:
            continue
        url = entry.get("request", {}).get("url", "")
        response = entry.get("response", {})
        size = response.get("_transferSize") or response.get("bodySize", 0)
        resources.append({
            "url": _truncate_url(url, 120),
            "size_bytes": size if size and size > 0 else None,
            "duration_ms": round(duration, 1),
        })
    resources.sort(key=lambda r: r["duration_ms"], reverse=True)
    return resources[:limit]

def _truncate_url(url: str, max_length: int = 120) -> str:
    """Truncate a URL for display, keeping domain and end of path."""
    if len(url) <= max_length:
        return url
    return url[:max_length - 3] + "..."
```

### Polling Orchestrator (tools/analyze.py)

```python
import asyncio
import logging
import time
import httpx

logger = logging.getLogger(__name__)

POLL_INTERVAL = 3       # seconds, matches API's Retry-After
DEFAULT_TIMEOUT = 300   # 5 minutes


async def _analyze_impl(client, url: str) -> dict:
    """Core analyze logic. Separated from MCP decorator for testability."""
    try:
        # 1. Start test
        test = await client.start_test(url)
        test_id = test.get("id")
        if not test_id:
            return {"error": "Failed to start test", "hint": "No test ID returned"}

        logger.info("Test %s started for %s", test_id, url)

        # 2. Poll until completion or timeout
        deadline = time.monotonic() + DEFAULT_TIMEOUT
        while time.monotonic() < deadline:
            result = await client.get_test(test_id)
            state = result.get("state")

            # Check if redirect gave us the report directly
            if result.get("type") == "report":
                report = result
                report_id = result.get("id")
                break

            if state == "completed":
                # Extract report ID from links or test data
                report_id = test_id  # Often same, but may differ
                report = await client.get_report(report_id)
                break

            if state == "error":
                return {
                    "error": f"GTMetrix test failed: {result.get('error', 'Unknown error')}",
                    "hint": "The target URL may be unreachable, returning an error, or blocked",
                    "url": url,
                }

            await asyncio.sleep(POLL_INTERVAL)
        else:
            return {
                "error": f"Test timed out after {DEFAULT_TIMEOUT}s",
                "hint": "The site may be very slow or GTMetrix is under heavy load. Try again later.",
                "url": url,
                "test_id": test_id,
            }

        # 3. Fetch sub-resources
        from client.parsers import extract_vitals, filter_failing_audits, extract_top_resources

        lighthouse_json = await client.get_resource(report_id, "lighthouse")
        har_json = await client.get_resource(report_id, "har")

        # 4. Parse and combine
        vitals = extract_vitals(report)
        failing_audits = filter_failing_audits(lighthouse_json)
        top_resources = extract_top_resources(har_json)

        return {
            "url": url,
            "test_id": test_id,
            "report_id": report_id,
            **vitals,
            "failing_audits": failing_audits,
            "top_resources": top_resources,
        }

    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 402:
            return {
                "error": "No API credits remaining",
                "hint": "Credits are exhausted. Use gtmetrix_check_status() to see refill date.",
            }
        if status == 429:
            return {
                "error": "Concurrent test limit reached",
                "hint": "Wait for existing tests to complete before starting new ones.",
            }
        logger.error("GTMetrix HTTP error: %s", exc)
        return {
            "error": f"GTMetrix API error (HTTP {status})",
            "hint": "Check API key and try again",
            "detail": str(exc),
        }
    except Exception as exc:
        logger.error("Analysis failed: %s", exc, exc_info=True)
        return {
            "error": "Analysis failed unexpectedly",
            "hint": "Check logs for details",
            "detail": str(exc),
        }
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PageSpeed/YSlow scores | Lighthouse performance + structure scores | GTMetrix v2.0 (2020) | Old scores deprecated; use `performance_score` and `structure_score` |
| Full JSON dumps to LLM | Filtered/summarized data | Current best practice | 200KB Lighthouse JSON is unusable in context; filter to failing audits |
| Sync HTTP polling | Async polling with `asyncio.sleep()` | Always for async MCP servers | Sync `time.sleep()` blocks the event loop and breaks MCP protocol |

**Deprecated/outdated:**
- `pagespeed_score` and `yslow_score`: Still returned by GTMetrix API but are legacy scores. Use `performance_score` and `structure_score` instead.
- `report: "legacy"` option: Returns PageSpeed/YSlow data only. Use `report: "lighthouse"` (default).

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
| TEST-01 | `start_test(url)` sends POST /tests with correct JSON:API body | unit | `uv run pytest tests/test_client.py::test_start_test -x` | No - Wave 0 |
| TEST-02 | Poll loop calls `get_test()` repeatedly with 3s sleep until completion | unit | `uv run pytest tests/test_analyze.py::test_poll_completes -x` | No - Wave 0 |
| TEST-03 | Poll loop returns timeout error after deadline | unit | `uv run pytest tests/test_analyze.py::test_poll_timeout -x` | No - Wave 0 |
| REPT-01 | `extract_vitals()` returns LCP, TBT, CLS, perf score, structure score | unit | `uv run pytest tests/test_parsers.py::test_extract_vitals -x` | No - Wave 0 |
| REPT-02 | `filter_failing_audits()` returns only audits with score < 1 | unit | `uv run pytest tests/test_parsers.py::test_filter_failing_audits -x` | No - Wave 0 |
| REPT-03 | `extract_top_resources()` returns top 10 sorted by duration | unit | `uv run pytest tests/test_parsers.py::test_extract_top_resources -x` | No - Wave 0 |
| REPT-04 | `_analyze_impl()` returns combined dict with all sections | unit | `uv run pytest tests/test_analyze.py::test_analyze_full_flow -x` | No - Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_analyze.py` -- covers TEST-02, TEST-03, REPT-04 (full flow)
- [ ] `tests/test_parsers.py` additions -- covers REPT-01, REPT-02, REPT-03
- [ ] `tests/test_client.py` additions -- covers TEST-01
- [ ] `tests/conftest.py` additions -- mock fixtures for test/report/lighthouse/HAR responses
- [ ] `tests/test_fixtures.py` additions -- sample response data for new endpoints

---

## Open Questions

1. **Report ID vs Test ID for resource URLs**
   - What we know: The 303 redirect goes to `/reports/{report_id}`. The report ID may differ from the test ID.
   - What's unclear: Whether the report ID is always derivable from the test response, or only from the redirect Location header.
   - Recommendation: After polling detects completion, check if `data.type == "report"` (redirect was followed). If so, use `data.id` as report ID. If `data.type == "test"`, parse `data.links.report` to extract the report ID. Handle both paths.

2. **HAR `_transferSize` field reliability**
   - What we know: `_transferSize` is a non-standard HAR extension. GTMetrix docs mention "resource usage data has been included."
   - What's unclear: Whether every entry has `_transferSize` or if some entries (e.g., cached resources) omit it.
   - Recommendation: Fall back to `response.bodySize` if `_transferSize` is absent. Report `null` if neither is available. Validate against a real HAR response.

3. **Lighthouse resource endpoint path**
   - What we know: GTMetrix docs reference `lighthouse.json` in the links object.
   - What's unclear: Whether the actual GET path is `/resources/lighthouse` or `/resources/lighthouse.json`.
   - Recommendation: Try `/resources/lighthouse` first (as referenced in links). If that fails, try with `.json` extension. Document whichever works.

---

## Sources

### Primary (HIGH confidence)
- GTMetrix REST API v2.0 docs (https://gtmetrix.com/api/docs/2.0/) -- test creation, polling, report schema, resource endpoints
- [Lighthouse understanding-results.md](https://github.com/GoogleChrome/lighthouse/blob/main/docs/understanding-results.md) -- audit JSON structure: score, title, description, displayValue, scoreDisplayMode
- [HAR 1.2 Spec](http://www.softwareishard.com/blog/har-12-spec/) -- entry structure: request.url, response._transferSize, time, timings

### Secondary (MEDIUM confidence)
- Phase 1 research and implementation -- existing codebase patterns, lifespan, parsers

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies; all verified from Phase 1
- Architecture: HIGH -- direct extension of Phase 1 patterns, API flow verified from official docs
- GTMetrix API schemas: HIGH -- verified from official API documentation
- Lighthouse audit format: HIGH -- verified from official Lighthouse docs on GitHub
- HAR format: MEDIUM -- standard spec is clear, but GTMetrix-specific extensions (_transferSize) need live validation
- Pitfalls: HIGH -- derived from API behavior documented in official docs

**Research date:** 2026-03-04
**Valid until:** 2026-06-04 (stable API; no breaking changes expected)
