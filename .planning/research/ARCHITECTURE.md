# Architecture Research

**Domain:** Python MCP server wrapping a REST API (GTMetrix v2.0)
**Researched:** 2026-03-04
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code (MCP Host)                    │
│                  Calls tools, reads responses                │
└──────────────────────────┬──────────────────────────────────┘
                           │ stdio (JSON-RPC)
┌──────────────────────────▼──────────────────────────────────┐
│                    MCP Layer (FastMCP)                       │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ run_test     │  │ get_report   │  │ check_account│       │
│  │ tool         │  │ tool         │  │ tool         │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                │                  │               │
│         └────────────────┼──────────────────┘               │
│                          │                                  │
├──────────────────────────▼──────────────────────────────────┤
│                  GTMetrix Client Layer                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  GTMetrixClient (httpx.AsyncClient)                  │    │
│  │  - Authentication (HTTP Basic)                       │    │
│  │  - JSON:API response parsing                         │    │
│  │  - Polling loop (3s intervals)                       │    │
│  │  - Error normalization                               │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                  Data Transformation Layer                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Response parsers / Pydantic models                  │    │
│  │  JSON:API → flat dict suitable for Claude reasoning  │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS / HTTP Basic Auth
┌──────────────────────────▼──────────────────────────────────┐
│              GTMetrix REST API v2.0                          │
│  POST /tests  GET /tests/{id}  GET /reports/{id}             │
│  GET /reports/{id}/lighthouse  GET /reports/{id}/har        │
│  GET /status                                                 │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| MCP Entry Point | Initialize FastMCP, register tools, run stdio transport | `main.py` or `server.py` with `mcp.run(transport="stdio")` |
| MCP Tools | Validate inputs, call client, format output for Claude | Decorated `@mcp.tool()` async functions in `tools/` |
| GTMetrixClient | HTTP sessions, auth, retries, polling state machine | `client/gtmetrix.py` with `httpx.AsyncClient` |
| Response Parsers | Unwrap JSON:API envelope, extract attributes, flatten for readability | `client/parsers.py` with Pydantic models or dataclasses |
| Config / Settings | Load `.env`, expose typed settings | `config.py` using `python-dotenv` or `pydantic-settings` |

## Recommended Project Structure

```
gtmetrix-mcp-server/
├── main.py                  # Entry point: creates FastMCP instance, registers tools, runs server
├── config.py                # Reads .env, exposes GTMetrix API key and settings
├── pyproject.toml           # Dependencies: mcp, httpx, pydantic, python-dotenv
├── .env                     # API key (not committed)
├── client/
│   ├── __init__.py
│   ├── gtmetrix.py          # GTMetrixClient class: all HTTP calls, polling, auth
│   └── parsers.py           # JSON:API → clean dict transformations, Pydantic models
├── tools/
│   ├── __init__.py
│   ├── testing.py           # run_test tool: start + poll + return summary
│   ├── reports.py           # get_lighthouse, get_har, get_report tools
│   └── account.py           # check_account tool: credits, status
└── tests/
    ├── test_client.py       # Unit tests for GTMetrixClient (mock httpx)
    └── test_tools.py        # Unit tests for MCP tools (mock client)
```

### Structure Rationale

- **client/**: Encapsulates all GTMetrix API knowledge. The MCP tool layer never constructs HTTP requests directly. If the API changes, only this module needs updating.
- **tools/**: Each file groups tools by domain (testing vs. reporting vs. account). Tools are thin: validate input, call client, format output. No HTTP logic here.
- **parsers.py**: JSON:API responses are deeply nested. Centralizing the unwrapping keeps tools readable. Pydantic models also document the shape of API responses.
- **config.py**: Single source of truth for configuration. Avoids `os.getenv()` scattered across files.
- **main.py**: Stays minimal — creates the `FastMCP` instance, imports and registers tool modules, calls `mcp.run()`.

## Architectural Patterns

### Pattern 1: Thin Tools, Fat Client

**What:** MCP tool functions contain no HTTP logic. They receive validated inputs, call a method on `GTMetrixClient`, and return formatted text or structured data. All retry logic, auth, polling, and error normalization live in the client.

**When to use:** Always — this is the correct separation for any API-wrapping MCP server.

**Trade-offs:** Slightly more files than a single-file approach, but dramatically easier to test and maintain. The client can be unit-tested with mocked httpx responses without touching MCP protocol concerns.

**Example:**
```python
# tools/testing.py
@mcp.tool()
async def run_test(url: str, location: str = "Vancouver") -> str:
    """Run a GTMetrix performance test for the given URL.

    Starts the test, polls until complete, and returns Core Web Vitals
    plus an overall grade.
    """
    result = await client.run_test_and_wait(url=url, location=location)
    return format_test_summary(result)
```

```python
# client/gtmetrix.py
async def run_test_and_wait(self, url: str, location: str) -> dict:
    test_id = await self._start_test(url, location)
    return await self._poll_until_complete(test_id)
```

### Pattern 2: Async Polling State Machine in Client

**What:** The client implements polling as an `async` loop with `asyncio.sleep(3)` between status checks. It tracks test state transitions (queued → started → completed/error) and raises on terminal errors.

**When to use:** GTMetrix tests take 30-120 seconds. A blocking poll inside a tool call would freeze the MCP server. Async polling allows the event loop to remain responsive.

**Trade-offs:** Slightly more complex than synchronous polling. No real downside for this use case — the MCP SDK is already async.

**Example:**
```python
async def _poll_until_complete(self, test_id: str, timeout: int = 300) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        status = await self._get_test_status(test_id)
        if status["state"] == "completed":
            return await self._get_report(status["report_id"])
        if status["state"] == "error":
            raise GTMetrixTestError(status.get("error", "Unknown error"))
        await asyncio.sleep(3)
    raise GTMetrixTimeoutError(f"Test {test_id} did not complete within {timeout}s")
```

### Pattern 3: JSON:API Envelope Unwrapping

**What:** GTMetrix uses JSON:API v1.1. Every response is `{"data": {"type": "...", "id": "...", "attributes": {...}}}`. Parsers strip this envelope immediately after each HTTP response so that the rest of the codebase works with flat dicts.

**When to use:** Always, as the very first step after any API call returns.

**Trade-offs:** Adds a thin indirection layer. The benefit is that if GTMetrix changes their envelope structure, it's fixed in one place.

**Example:**
```python
# client/parsers.py
def unwrap_jsonapi(response: dict) -> dict:
    """Extract attributes from a JSON:API response data object."""
    data = response.get("data", {})
    return {
        "id": data.get("id"),
        "type": data.get("type"),
        **data.get("attributes", {}),
        "_links": data.get("links", {}),
    }
```

## Data Flow

### Test Execution Flow

```
Claude calls run_test(url="https://example.com")
    ↓
tools/testing.py: validates URL, calls client.run_test_and_wait()
    ↓
client/gtmetrix.py: POST /api/2.0/tests
    ↓ HTTP 202, test_id returned
client/gtmetrix.py: polling loop
    GET /api/2.0/tests/{test_id} every 3s
    ↓ JSON:API response
parsers.py: unwrap_jsonapi() → flat status dict
    ↓ state == "completed"
client/gtmetrix.py: GET /api/2.0/reports/{report_id}
    ↓ JSON:API response
parsers.py: parse_report() → flat metrics dict
    ↓
tools/testing.py: format_test_summary() → human-readable string
    ↓
Claude receives: "Grade: A (92%), LCP: 1.2s, TBT: 45ms, CLS: 0.02"
```

### Lighthouse Data Flow

```
Claude calls get_lighthouse(report_id="abc123")
    ↓
tools/reports.py: calls client.get_lighthouse_json(report_id)
    ↓
client/gtmetrix.py: GET /api/2.0/reports/{report_id}/lighthouse
    ↓ raw Lighthouse JSON (large, ~500KB)
parsers.py: extract_actionable_audits() → failed/warning audits only
    ↓
tools/reports.py: formats as structured list for Claude reasoning
    ↓
Claude receives: list of Lighthouse audit failures with scores and descriptions
```

### Key Data Flows

1. **Test initiation → polling → report:** The main workflow. Client owns the full lifecycle; tools just call `run_test_and_wait()`.
2. **Report resource fetching:** Separate tool calls for Lighthouse JSON, HAR data — these can be large so fetching is on-demand, not bundled automatically.
3. **Error propagation:** Client raises typed exceptions (`GTMetrixTestError`, `GTMetrixRateLimitError`). Tools catch them and return error strings to Claude rather than letting exceptions bubble up as protocol errors.

## Scaling Considerations

This is a local single-user tool. Scaling is not a concern. However:

| Concern | Approach |
|---------|----------|
| Long-running tests (30-120s) | Async polling — does not block event loop |
| API rate limits (960 req/60s) | Well within limits for single user, no rate limit logic needed initially |
| Large Lighthouse JSON (~500KB) | Parse server-side, return only failed audits to Claude to avoid context bloat |
| Multiple concurrent tests | GTMetrix PRO supports 8 concurrent — nothing special needed in client |

## Anti-Patterns

### Anti-Pattern 1: All logic in main.py

**What people do:** Write a single `main.py` with all tool definitions, HTTP calls, and parsing inline.

**Why it's wrong:** Untestable. HTTP calls cannot be mocked without restructuring. JSON:API parsing bugs get buried in tool functions. Adding new tools means touching one large file.

**Do this instead:** Separate client/, tools/, and parsers into distinct modules from the start. The overhead is 3-4 extra files, which is negligible.

### Anti-Pattern 2: Returning raw JSON:API responses to Claude

**What people do:** Pass `response.json()` directly as tool output.

**Why it's wrong:** JSON:API envelopes are verbose and nested. Claude wastes tokens parsing `data.attributes.xxx` instead of reasoning about performance data. Large Lighthouse JSON (~500KB) will overflow context windows.

**Do this instead:** Always transform responses. Strip the JSON:API envelope in parsers. For Lighthouse, filter to failed/warning audits only. Return human-readable summaries for the primary tool, offer raw data access as a separate tool.

### Anti-Pattern 3: Synchronous polling inside tool handlers

**What people do:** Use `time.sleep(3)` inside a tool function while waiting for a test to complete.

**Why it's wrong:** Blocks the entire MCP server process. No other tool calls can be processed. If the test times out after 120s, the server appears hung.

**Do this instead:** Use `await asyncio.sleep(3)` inside an `async` client method. FastMCP handles async tools natively.

### Anti-Pattern 4: Ignoring JSON:API 303 redirects

**What people do:** Manually follow the `GET /tests/{id}` → `GET /reports/{id}` redirect without configuring httpx correctly.

**Why it's wrong:** httpx does not follow redirects by default. The 303 response when a test completes will silently fail if `follow_redirects=True` is not set, or the redirect must be handled manually.

**Do this instead:** Configure `httpx.AsyncClient(follow_redirects=True)`, or explicitly check for 303 status and extract the `Location` header to fetch the report.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| GTMetrix API v2.0 | HTTP Basic Auth (API key as username, empty password) | JSON:API v1.1 format for all responses |
| Claude Code (MCP host) | stdio transport, JSON-RPC | FastMCP handles the protocol layer automatically |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| tools/ ↔ client/ | Direct async function calls | Tools import `GTMetrixClient` instance; client is initialized at server startup via lifespan |
| client/ ↔ parsers/ | Function calls, return dicts | Parsers are pure functions, no shared state |
| main.py ↔ tools/ | FastMCP tool registration | Tools are registered by importing tool modules after `mcp` instance is created |
| config.py ↔ all | Module-level import | `settings` object is imported wherever needed |

### GTMetrix API Endpoints Required

| Endpoint | Method | Purpose | Tool |
|----------|--------|---------|------|
| `/api/2.0/tests` | POST | Start a test | `run_test` |
| `/api/2.0/tests/{id}` | GET | Poll test status | internal polling |
| `/api/2.0/reports/{id}` | GET | Get report summary with Core Web Vitals | `run_test`, `get_report` |
| `/api/2.0/reports/{id}/lighthouse` | GET | Full Lighthouse audit JSON | `get_lighthouse` |
| `/api/2.0/reports/{id}/har` | GET | HAR waterfall data | `get_har` |
| `/api/2.0/status` | GET | Account status, credit balance | `check_account` |

## Build Order

The components have clear dependencies. Build in this order to be unblocked at each step:

1. **config.py** — No dependencies. Reads `.env`, exposes `GTMETRIX_API_KEY`. Everything else imports this.
2. **client/parsers.py** — No dependencies. Pure functions. Can be unit tested immediately.
3. **client/gtmetrix.py** — Depends on config and parsers. Implement and test against real API with a single test call. Validates auth, JSON:API parsing, and polling logic before any MCP work.
4. **tools/account.py** — First tool. Simplest: one API call, no polling. Validates the full MCP stack (FastMCP + client + stdio transport) with minimal complexity.
5. **tools/testing.py** — Depends on client polling being proven. The core tool.
6. **tools/reports.py** — Depends on having a real `report_id` from step 5. Implement Lighthouse and HAR fetching after the test workflow works end-to-end.
7. **main.py** (final wiring) — Register all tools, configure lifespan for client initialization, run server. This evolves incrementally as each tool module is added.

## Sources

- [MCP Python SDK — GitHub](https://github.com/modelcontextprotocol/python-sdk) — HIGH confidence (official)
- [Build an MCP server — modelcontextprotocol.io](https://modelcontextprotocol.io/docs/develop/build-server) — HIGH confidence (official)
- [GTMetrix REST API v2.0 documentation](https://gtmetrix.com/api/docs/2.0/) — HIGH confidence (official)
- [REST API to MCP Server — MCP Showcase](https://mcpshowcase.com/blog/rest-api-to-python-mcp-server) — MEDIUM confidence (community guide, verified against official patterns)
- [httpx Async Support](https://www.python-httpx.org/async/) — HIGH confidence (official)
- [python-gtmetrix2 on PyPI](https://pypi.org/project/python-gtmetrix2/) — MEDIUM confidence (reference for GTMetrix API patterns)

---
*Architecture research for: Python MCP server wrapping GTMetrix REST API v2.0*
*Researched: 2026-03-04*
