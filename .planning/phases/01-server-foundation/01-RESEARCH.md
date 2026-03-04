# Phase 1: Server Foundation - Research

**Researched:** 2026-03-04
**Domain:** Python MCP server (stdio transport) + GTMetrix REST API v2.0 authentication and status
**Confidence:** HIGH

---

## Summary

Phase 1 builds the complete server skeleton: FastMCP instance over stdio transport, `pydantic-settings` config loading the API key from `.env`, a shared `httpx.AsyncClient` configured for GTMetrix HTTP Basic auth, the JSON:API envelope unwrapper, and one working tool — `gtmetrix_check_status()`. Nothing about polling or report parsing is required in this phase; those belong to Phase 2.

The starting codebase is a blank slate: `main.py` contains only a `print("Hello from gtmetrix-mcp-serer!")` placeholder, `pyproject.toml` has zero dependencies declared. Every library must be installed. The existing `print()` in `main.py` violates SERV-06 and must be removed in the first task.

**Primary recommendation:** Follow the build order config → parsers → client → tool → main.py. Do not write any tool code until the `httpx.AsyncClient` is proven to authenticate against the live GTMetrix `/status` endpoint.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SERV-01 | MCP server starts via stdio transport and registers tools with Claude Code | FastMCP `mcp.run(transport="stdio")` pattern — see Standard Stack and Code Examples |
| SERV-02 | API key loaded from .env file via pydantic-settings | `BaseSettings` with `SettingsConfigDict(env_file=".env")` — see Code Examples |
| SERV-03 | All HTTP calls use httpx.AsyncClient (no sync blocking) | Single shared `AsyncClient` with lifespan pattern — see Architecture Patterns |
| SERV-04 | JSON:API v1.1 responses parsed to flat dicts before returning to Claude | `unwrap_jsonapi()` pure function in `client/parsers.py` — see Code Examples |
| SERV-05 | Errors returned as structured tool results with hints (not raised as exceptions) | Tool-level try/except returning dict — see Code Examples |
| SERV-06 | No stdout output except MCP protocol (logging to stderr only) | `logging.basicConfig(stream=sys.stderr)` at entrypoint; ban `print()` — see Common Pitfalls |
| ACCT-01 | `gtmetrix_check_status()` returns API credits remaining, account type, refill date | GET /api/2.0/status returns JSON:API envelope with `api_credits`, `account_type`, `api_refill` — see GTMetrix API section |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` (with `[cli]` extra) | 1.26.0 | MCP protocol implementation, stdio transport, tool registration | Official Anthropic SDK. Handles all JSON-RPC framing — do not re-implement |
| `httpx` | 0.28.1 | Async HTTP client for GTMetrix API calls | Supports `AsyncClient` natively; fits MCP's async event loop. `requests` is sync-only and blocks |
| `pydantic-settings` | 2.x | Load `GTMETRIX_API_KEY` from `.env` with type validation | Already a transitive dep of `mcp`; `BaseSettings` is strictly better than bare `os.getenv()` |
| Python | 3.11 | Runtime | Already pinned in `.python-version`; `mcp` requires >=3.10 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asyncio` | stdlib | Event loop, `asyncio.sleep()` for polling | Built-in; use `asyncio.sleep(3)` in Phase 2 polling |
| `logging` | stdlib | Structured logging routed to stderr | Use everywhere instead of `print()` |
| `ruff` | latest | Linter + formatter | Dev dep; add a lint step that fails on `print(` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `mcp` SDK | Raw stdio JSON-RPC | Never — the SDK handles the initialization handshake, schema generation, and error codes correctly |
| `httpx.AsyncClient` | `requests` | Never — `requests` is sync; blocks the event loop inside async tools |
| `pydantic-settings` | bare `os.getenv()` | `os.getenv()` works but gives no type safety and no `.env` loading without extra code |

**Installation:**

```bash
uv add "mcp[cli]" httpx pydantic-settings
uv add --dev ruff
```

---

## Architecture Patterns

### Recommended Project Structure

```
gtmetrix-mcp-server/
├── main.py                  # FastMCP instance, tool imports, mcp.run()
├── config.py                # BaseSettings loading GTMETRIX_API_KEY from .env
├── pyproject.toml           # Dependencies (currently empty — add them)
├── .env                     # API key (never commit)
├── .env.example             # Committed example with placeholder key
├── client/
│   ├── __init__.py
│   ├── gtmetrix.py          # GTMetrixClient: shared AsyncClient, auth, HTTP calls
│   └── parsers.py           # JSON:API → flat dict transformations (pure functions)
├── tools/
│   ├── __init__.py
│   └── account.py           # gtmetrix_check_status tool
└── tests/
    ├── __init__.py
    ├── conftest.py           # Shared fixtures, mock client
    └── test_parsers.py       # Unit tests for parsers (no HTTP needed)
```

### Pattern 1: FastMCP with Lifespan for Client Management

**What:** The `httpx.AsyncClient` is created once at server startup via FastMCP's `lifespan` context manager and shared across all tool calls. Tools access it through `ctx.request_context.lifespan_context`.

**When to use:** Always — never instantiate `AsyncClient` inside a tool handler. Per-call instantiation destroys connection pooling and leaks resources.

**Example:**
```python
# main.py
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from client.gtmetrix import GTMetrixClient
from config import settings

@asynccontextmanager
async def lifespan(server):
    async with GTMetrixClient(api_key=settings.gtmetrix_api_key) as client:
        yield {"client": client}

mcp = FastMCP("gtmetrix", lifespan=lifespan)
```

### Pattern 2: Config via BaseSettings

**What:** A single `Settings` class reads all configuration from `.env` and environment variables. Other modules import the `settings` singleton — no `os.getenv()` calls scattered across files.

**Example:**
```python
# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    gtmetrix_api_key: str

settings = Settings()
```

### Pattern 3: GTMetrixClient as Async Context Manager

**What:** `GTMetrixClient` wraps `httpx.AsyncClient` and is used as an async context manager so the HTTP session is cleanly opened and closed.

**Example:**
```python
# client/gtmetrix.py
import httpx
from client.parsers import unwrap_jsonapi

GTMETRIX_BASE_URL = "https://gtmetrix.com/api/2.0"
JSONAPI_HEADERS = {
    "Content-Type": "application/vnd.api+json",
    "Accept": "application/vnd.api+json",
}

class GTMetrixClient:
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=GTMETRIX_BASE_URL,
            auth=(self._api_key, ""),   # HTTP Basic: key as username, blank password
            headers=JSONAPI_HEADERS,
            follow_redirects=True,
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def get_status(self) -> dict:
        response = await self._client.get("/status")
        response.raise_for_status()
        return unwrap_jsonapi(response.json())
```

### Pattern 4: JSON:API Envelope Unwrapper

**What:** A pure function in `client/parsers.py` strips the JSON:API wrapper from every API response. Tools never see `data.attributes` — they work with flat dicts.

**Example:**
```python
# client/parsers.py
def unwrap_jsonapi(response: dict) -> dict:
    """Extract attributes from a JSON:API data envelope."""
    data = response.get("data", {})
    return {
        "id": data.get("id"),
        "type": data.get("type"),
        **data.get("attributes", {}),
    }
```

### Pattern 5: Tool Error Handling (No Uncaught Exceptions)

**What:** Every tool wraps its client call in try/except and returns a structured dict with `error` and `hint` keys on failure. Exceptions are never allowed to propagate out of a tool handler — unhandled exceptions produce silent protocol errors in Claude Code.

**Example:**
```python
# tools/account.py
import logging
from mcp.server.fastmcp import FastMCP, Context

logger = logging.getLogger(__name__)

def register(mcp: FastMCP):
    @mcp.tool()
    async def gtmetrix_check_status(ctx: Context) -> dict:
        """Check GTMetrix account status: credits remaining, account type, and refill date."""
        client = ctx.request_context.lifespan_context["client"]
        try:
            status = await client.get_status()
            return {
                "api_credits": status.get("api_credits"),
                "account_type": status.get("account_type"),
                "api_refill": status.get("api_refill"),
                "api_refill_amount": status.get("api_refill_amount"),
            }
        except Exception as exc:
            logger.error("GTMetrix status check failed: %s", exc)
            return {
                "error": "Failed to fetch GTMetrix account status",
                "hint": "Verify GTMETRIX_API_KEY in .env is correct and the GTMetrix API is reachable",
                "detail": str(exc),
            }
```

### Pattern 6: Logging Setup (stderr only)

**What:** Configure logging at the top of `main.py` before any other imports that might emit output. Use `sys.stderr` as the stream. Never call `print()` anywhere.

**Example:**
```python
# main.py (top)
import logging
import sys

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
```

### Anti-Patterns to Avoid

- **`print()` anywhere in tool or client code:** Corrupts the stdio JSON-RPC stream. Claude Code shows parse errors. Use `logger.debug()` / `logger.info()`.
- **`httpx.AsyncClient()` instantiated inside a tool handler:** No connection pooling; resource leaks. Use the lifespan pattern.
- **`os.getenv("GTMETRIX_API_KEY")` directly in client code:** Couples the client to the environment. Use `config.settings`.
- **Returning `response.json()` directly from tools:** Returns the raw JSON:API envelope; Claude sees `data.attributes.xxx` noise. Always call `unwrap_jsonapi()` first.
- **Raising exceptions out of tool handlers:** Silent protocol failures in Claude Code. Always catch and return a structured error dict.

---

## GTMetrix API: Status Endpoint

This is the only GTMetrix endpoint needed for Phase 1.

**Endpoint:** `GET /api/2.0/status`

**Authentication:** HTTP Basic — API key as username, empty string as password.

**Response envelope (JSON:API v1.1):**
```json
{
  "data": {
    "type": "user",
    "id": "{api_key}",
    "attributes": {
      "api_credits": 1497,
      "api_refill": 1618437519,
      "api_refill_amount": 10,
      "account_type": "Basic",
      "account_pro_analysis_options_access": false,
      "account_pro_locations_access": false,
      "account_whitelabel_pdf_access": false
    }
  }
}
```

**After `unwrap_jsonapi()`:**
```python
{
    "id": "{api_key}",
    "type": "user",
    "api_credits": 1497,
    "api_refill": 1618437519,       # Unix timestamp
    "api_refill_amount": 10,
    "account_type": "Basic",
    "account_pro_analysis_options_access": False,
    ...
}
```

**Key fields for ACCT-01:**
| Field | Type | Meaning |
|-------|------|---------|
| `api_credits` | int | Credits remaining this period |
| `account_type` | str | Plan tier ("Basic", "Pro", etc.) |
| `api_refill` | int | Unix timestamp of next refill |
| `api_refill_amount` | int | Credits added at refill |

Source: GTMetrix REST API v2.0 docs (HIGH confidence, verified via official API docs fetch)

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP protocol (stdio framing, JSON-RPC, tool schemas) | Custom stdio reader/writer | `mcp` SDK with `FastMCP` | The protocol has an initialization handshake, capability negotiation, and schema format that the SDK handles correctly |
| `.env` loading with type validation | `os.getenv()` + manual type casting | `pydantic-settings` `BaseSettings` | Already a transitive dependency; gives free type validation, clear error on missing vars |
| HTTP connection pool management | Manual session lifecycle | `httpx.AsyncClient` as context manager via lifespan | httpx handles pooling, keep-alive, and cleanup; per-call instantiation leaks connections |
| JSON:API envelope parsing | Nested dict access scattered in tool code | `unwrap_jsonapi()` in `parsers.py` | One change point when GTMetrix changes envelope structure |

---

## Common Pitfalls

### Pitfall 1: stdout Pollution Breaks the stdio Protocol

**What goes wrong:** Any `print()` call, any logging handler pointing to stdout, any exception traceback on stdout — all corrupt the JSON-RPC stream. Claude Code receives malformed protocol frames and shows cryptic errors.

**Why it happens:** Python's `print()` and the default `logging.StreamHandler()` both write to stdout. The existing `main.py` has a `print()` that must be removed immediately.

**How to avoid:** Set `logging.basicConfig(stream=sys.stderr)` as the very first line of `main.py`. Never call `print()`. Use `logger.debug()` exclusively.

**Warning signs:** Claude Code JSON parse errors, MCP inspector showing malformed frames.

### Pitfall 2: Uncaught Exceptions in Tool Handlers

**What goes wrong:** If `gtmetrix_check_status()` raises an unhandled exception (e.g., network timeout, wrong API key), the MCP SDK may silently drop the tool response or return a generic protocol error. Claude sees no useful error message.

**How to avoid:** Wrap every tool's body in `try/except Exception`. Return `{"error": "...", "hint": "..."}` on failure. Never `raise` from a tool.

### Pitfall 3: Missing `Content-Type: application/vnd.api+json` on POST Requests

**What goes wrong:** GTMetrix returns `415 Unsupported Media Type` for POST requests without the JSON:API content-type header. The default `application/json` is rejected.

**How to avoid:** Set `JSONAPI_HEADERS` as a module constant on `GTMetrixClient` and pass it to the `AsyncClient` constructor. This phase only uses GET (status endpoint has no body), but establish the correct headers now for Phase 2.

### Pitfall 4: API Key Hardcoded or Logged

**What goes wrong:** API key exposed in version control or in log output.

**How to avoid:** Only read from `settings.gtmetrix_api_key`. Never log HTTP request headers. Add `.env` to `.gitignore`. Provide `.env.example` with a placeholder.

### Pitfall 5: httpx Does Not Follow Redirects by Default

**What goes wrong:** Phase 2 relies on 303 redirects from GTMetrix when a test completes. If `follow_redirects=False` (the httpx default), 303 responses are returned as-is and the polling logic fails.

**How to avoid:** Set `follow_redirects=True` on the `AsyncClient` constructor in Phase 1. This is the correct default for the GTMetrix client and avoids a Phase 2 debugging trap.

---

## Code Examples

### Complete `config.py`
```python
# Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    gtmetrix_api_key: str

settings = Settings()
```

### Complete `client/parsers.py`
```python
def unwrap_jsonapi(response: dict) -> dict:
    """Strip the JSON:API envelope and return a flat dict of attributes."""
    data = response.get("data", {})
    return {
        "id": data.get("id"),
        "type": data.get("type"),
        **data.get("attributes", {}),
    }
```

### `GTMetrixClient.get_status()` (Phase 1 portion of `client/gtmetrix.py`)
```python
import httpx
from client.parsers import unwrap_jsonapi

GTMETRIX_BASE_URL = "https://gtmetrix.com/api/2.0"
JSONAPI_HEADERS = {
    "Content-Type": "application/vnd.api+json",
    "Accept": "application/vnd.api+json",
}

class GTMetrixClient:
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "GTMetrixClient":
        self._client = httpx.AsyncClient(
            base_url=GTMETRIX_BASE_URL,
            auth=(self._api_key, ""),
            headers=JSONAPI_HEADERS,
            follow_redirects=True,
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()

    async def get_status(self) -> dict:
        response = await self._client.get("/status")
        response.raise_for_status()
        return unwrap_jsonapi(response.json())
```

### `tools/account.py`
```python
import logging
from mcp.server.fastmcp import Context

logger = logging.getLogger(__name__)

def register(mcp):
    @mcp.tool()
    async def gtmetrix_check_status(ctx: Context) -> dict:
        """Check GTMetrix account status.

        Returns API credits remaining, account type, and next credit refill date.
        """
        client = ctx.request_context.lifespan_context["client"]
        try:
            status = await client.get_status()
            return {
                "api_credits": status.get("api_credits"),
                "account_type": status.get("account_type"),
                "api_refill_timestamp": status.get("api_refill"),
                "api_refill_amount": status.get("api_refill_amount"),
            }
        except Exception as exc:
            logger.error("GTMetrix status check failed: %s", exc, exc_info=True)
            return {
                "error": "Failed to fetch GTMetrix account status",
                "hint": "Verify GTMETRIX_API_KEY in your .env file is valid",
                "detail": str(exc),
            }
```

### `main.py` (final for Phase 1)
```python
import logging
import sys

# Configure logging to stderr BEFORE any other imports
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from client.gtmetrix import GTMetrixClient
from config import settings
import tools.account as account_tools

@asynccontextmanager
async def lifespan(server):
    async with GTMetrixClient(api_key=settings.gtmetrix_api_key) as client:
        yield {"client": client}

mcp = FastMCP("gtmetrix", lifespan=lifespan)
account_tools.register(mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (not yet installed — Wave 0 gap) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` section |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SERV-01 | Server registers tools and starts without error | smoke | `uv run python -c "from main import mcp; assert mcp"` | ❌ Wave 0 |
| SERV-02 | API key loaded from .env via pydantic-settings | unit | `uv run pytest tests/test_config.py -x` | ❌ Wave 0 |
| SERV-03 | HTTP calls use AsyncClient (no sync blocking) | unit | `uv run pytest tests/test_client.py::test_uses_async_client -x` | ❌ Wave 0 |
| SERV-04 | JSON:API responses parsed to flat dicts | unit | `uv run pytest tests/test_parsers.py -x` | ❌ Wave 0 |
| SERV-05 | Errors returned as structured results, not exceptions | unit | `uv run pytest tests/test_tools.py::test_status_error_handling -x` | ❌ Wave 0 |
| SERV-06 | No stdout output except MCP protocol | lint | `python -c "import ast, sys; [sys.exit(1) for n in ast.walk(ast.parse(open(f).read())) if isinstance(n, ast.Call) and getattr(getattr(n,'func',None),'id',None)=='print']" main.py` | ❌ Wave 0 |
| ACCT-01 | gtmetrix_check_status returns credits, type, refill | unit+integration | `uv run pytest tests/test_tools.py::test_check_status -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/__init__.py` — package marker
- [ ] `tests/conftest.py` — shared fixtures (mock GTMetrixClient, mock httpx responses)
- [ ] `tests/test_parsers.py` — covers SERV-04
- [ ] `tests/test_config.py` — covers SERV-02
- [ ] `tests/test_client.py` — covers SERV-03
- [ ] `tests/test_tools.py` — covers SERV-05, ACCT-01
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` section
- [ ] Framework install: `uv add --dev pytest pytest-asyncio`

---

## Open Questions

1. **FastMCP `Context` and lifespan access API in mcp 1.26.0**
   - What we know: The lifespan pattern with `yield {"client": client}` is documented in the MCP Python SDK
   - What's unclear: Exact import path and attribute name for accessing lifespan context from a tool (`ctx.request_context.lifespan_context` vs another attribute) may differ by SDK version
   - Recommendation: Verify against `mcp` 1.26.0 source or docs when implementing; adjust access pattern if needed

2. **`api_refill` field format**
   - What we know: The field is a Unix timestamp (integer)
   - What's unclear: Whether the tool should convert to a human-readable ISO date string or return the raw timestamp
   - Recommendation: Return the raw Unix timestamp and let Claude format it; simpler and avoids timezone assumptions

3. **`.gitignore` and `.env.example` present?**
   - What we know: Neither file exists in the repo yet (only `main.py`, `pyproject.toml`, `README.md`)
   - What's unclear: Nothing — they just need to be created
   - Recommendation: Create both in the first wave of tasks

---

## Sources

### Primary (HIGH confidence)
- `mcp` 1.26.0 on PyPI / GitHub python-sdk — stdio transport, FastMCP, lifespan pattern
- GTMetrix REST API v2.0 official docs (https://gtmetrix.com/api/docs/2.0/) — `/status` endpoint response schema verified
- httpx official docs (https://www.python-httpx.org/async/) — `AsyncClient` usage, `follow_redirects`
- pydantic-settings docs (https://docs.pydantic.dev/latest/concepts/pydantic_settings/) — `BaseSettings`, `SettingsConfigDict`

### Secondary (MEDIUM confidence)
- MCP Build Server guide (https://modelcontextprotocol.io/docs/develop/build-server) — lifespan, tool registration patterns

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified on PyPI/official docs
- Architecture: HIGH — patterns derived from official MCP SDK docs and GTMetrix API docs
- GTMetrix status endpoint schema: HIGH — verified live via official API documentation
- Pitfalls: HIGH — cross-referenced with official MCP docs and known issues

**Research date:** 2026-03-04
**Valid until:** 2026-06-04 (stable ecosystem; `mcp` SDK changes are the main risk)
