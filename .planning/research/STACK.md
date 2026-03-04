# Stack Research

**Domain:** Python MCP server wrapping a REST API (GTMetrix v2.0)
**Researched:** 2026-03-04
**Confidence:** HIGH (core MCP SDK, httpx, pydantic-settings verified via PyPI/official docs; python-gtmetrix2 assessed as LOW — see notes)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11 | Runtime | Already configured in project; `mcp` SDK supports 3.10+; 3.11 gives perf gains over 3.10 with no upgrade risk |
| `mcp` | 1.26.0 | MCP protocol implementation | Official Anthropic SDK. Handles stdio transport, protocol compliance, tool registration, message routing — do not re-implement this manually |
| `httpx` | 0.28.1 | HTTP client for GTMetrix API calls | Supports both sync and async in one library. The MCP SDK runs an async event loop; `httpx.AsyncClient` fits naturally. `requests` is sync-only — using it inside async tool handlers requires `asyncio.run_in_executor` workarounds that add complexity with no benefit |
| `uv` | latest | Package manager / virtualenv | Official MCP docs show `uv add "mcp[cli]"` as the primary install method. Faster than pip, `.python-version` file already in project, lock file ensures reproducible builds |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pydantic-settings` | 2.x | Config/env management | Load `GTMETRIX_API_KEY` from `.env` with type validation. Already a transitive dep of `mcp` (which depends on Pydantic v2), so no extra install weight. Use `BaseSettings` with `model_config = SettingsConfigDict(env_file=".env")` |
| `python-dotenv` | 1.x | `.env` file loading | Bundled inside `pydantic-settings`; no separate install needed unless you want `load_dotenv()` standalone. Included here for awareness only |
| `asyncio` | stdlib | Async polling loop | Built-in. Use `asyncio.sleep(3)` for GTMetrix test polling at the recommended 3-second interval. No external library needed |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` | Dependency management, virtualenv, script runner | Use `uv add` to install deps; `uv run main.py` to run. Replaces pip + venv workflow |
| `mcp[cli]` extra | `mcp dev` inspector for testing tools interactively | Install with `uv add "mcp[cli]"`. Run `mcp dev main.py` to inspect tools before connecting to Claude Code |
| `ruff` | Linter + formatter | Fast, zero-config. Add as dev dep: `uv add --dev ruff` |

## Installation

```bash
# Core MCP SDK (with CLI tools for development)
uv add "mcp[cli]"

# HTTP client for GTMetrix API
uv add httpx

# Config/env management
uv add pydantic-settings

# Dev tools
uv add --dev ruff
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `mcp` (official SDK) | Raw stdio protocol + JSON-RPC | Never for this project. Raw implementation means manually handling initialization handshake, tool schemas, error codes. The SDK does all of this correctly |
| `httpx` | `requests` | Use `requests` only if the entire codebase is synchronous. The MCP SDK's async runtime makes `httpx.AsyncClient` the natural fit |
| `httpx` | `aiohttp` | `aiohttp` is async-only. `httpx` is async + sync in one, has a near-identical API to `requests` (easier to read), and is already in the MCP SDK's dependency tree indirectly |
| `pydantic-settings` | `python-dotenv` standalone | Use `python-dotenv` alone only if you don't want type validation on env vars. For a project with an API key and future config flags, `BaseSettings` is strictly better |
| `python-gtmetrix2` | Direct `httpx` calls | See "What NOT to Use" — avoid the third-party wrapper |
| `uv` | `pip` + `venv` | Use `pip` only in CI environments where `uv` isn't available. For local development, `uv` is faster and more correct |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `python-gtmetrix2` | Last release was 2021 (version 0.3.0/0.3.1). The library is effectively unmaintained. GTMetrix API v2.0 uses JSON:API v1.1 format — the response parsing is simple enough that rolling a thin client with `httpx` is ~50 lines and gives full control. A dead third-party wrapper introduces risk with zero benefit for this scope | Direct `httpx.AsyncClient` calls to the GTMetrix API |
| `requests` | Sync-only. The `mcp` SDK runs an asyncio event loop; calling `requests.get()` from inside an `async def` tool blocks the event loop and prevents other operations from running | `httpx.AsyncClient` |
| `FastAPI` / `uvicorn` | The project uses stdio transport (local Claude Code connection), not HTTP. Adding a web server framework is dead weight | `mcp.run()` with default stdio transport |
| `aiohttp` | More complex API than `httpx`, async-only (no sync fallback), higher conceptual overhead. No advantage over `httpx` for a simple REST wrapper | `httpx.AsyncClient` |
| `anyio` (directly) | The MCP SDK handles the async runtime internally. Don't create your own `anyio` event loops; let `mcp.run()` manage this | `mcp.run()` — it handles the event loop |
| `poetry` | Works, but the MCP official docs, tutorials, and tooling all use `uv`. Mixing package managers adds friction when following MCP examples | `uv` |

## Stack Patterns by Variant

**For stdio transport (this project):**
- `mcp.run()` with no transport argument defaults to stdio — correct for Claude Code
- No web server, no port binding, no HTTP server needed

**If adding HTTP/SSE transport later:**
- Add `uvicorn` as a dep and change `mcp.run(transport="sse")` or `transport="streamable-http"`
- This project does not need this now

**For async polling (GTMetrix test completion):**
- Use `asyncio.sleep(3)` inside an `async def` tool, loop until `test.state == "completed"`
- Do NOT use `time.sleep()` — blocks the async event loop

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `mcp` 1.26.0 | Python >=3.10, Pydantic v2 | Pydantic v1 not supported |
| `httpx` 0.28.1 | Python >=3.8 | No issues with Python 3.11 |
| `pydantic-settings` 2.x | Pydantic v2 only | Don't mix with pydantic v1 projects |

## Sources

- https://pypi.org/project/mcp/ — version 1.26.0 confirmed, Python >=3.10 requirement (HIGH confidence)
- https://github.com/modelcontextprotocol/python-sdk — FastMCP pattern, stdio transport, tool decorator API (HIGH confidence)
- https://modelcontextprotocol.io/docs/develop/build-server — official build guide, `httpx.AsyncClient` usage in examples (HIGH confidence)
- https://pypi.org/project/httpx/ — version 0.28.1 confirmed (HIGH confidence)
- https://python-gtmetrix2.readthedocs.io/en/latest/changelog.html — last release 2021, confirmed unmaintained (HIGH confidence for "avoid" recommendation)
- https://docs.pydantic.dev/latest/concepts/pydantic_settings/ — BaseSettings pattern, .env integration (HIGH confidence)
- https://docs.astral.sh/uv/guides/projects/ — uv as standard for MCP projects (MEDIUM confidence — community pattern, not officially mandated)

---
*Stack research for: Python MCP server wrapping GTMetrix API v2.0*
*Researched: 2026-03-04*
