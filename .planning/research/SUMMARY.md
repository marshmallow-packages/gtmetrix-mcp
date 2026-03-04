# Project Research Summary

**Project:** GTMetrix MCP Server
**Domain:** Python MCP server wrapping a REST API (GTMetrix v2.0)
**Researched:** 2026-03-04
**Confidence:** HIGH

## Executive Summary

This is a Python MCP server that wraps the GTMetrix REST API v2.0, enabling Claude Code to run web performance tests and surface actionable results. The server uses stdio transport (no HTTP server needed) and must handle GTMetrix's async test lifecycle: submit a test, poll until completion (30-120 seconds), then fetch and parse multiple data resources (Core Web Vitals, Lighthouse audits, HAR waterfall). The recommended approach is a layered architecture with a thin MCP tool layer, a GTMetrix HTTP client, and a dedicated response transformation layer — never passing raw API responses to Claude.

The key design decision is to expose outcome-focused tools, not API-mirroring tools. A single `gtmetrix_analyze(url)` mega-tool that runs the test, polls to completion, filters Lighthouse to failing audits only, and extracts the top slow resources is strictly more useful than five granular tools that force Claude to orchestrate multi-step flows. GTMetrix's competitive advantage over free PageSpeed/PSI wrappers is real network throttling and geographic testing diversity — these should be exposed as parameters once the core workflow is stable.

The critical risks are protocol-level: stdout pollution will silently corrupt the stdio transport (never use `print()`), oversized Lighthouse/HAR payloads will cause silent context truncation, and a polling loop without a timeout will hang the server indefinitely. All three are Phase 1 concerns that must be designed in from the start, not retrofitted. GTMetrix tests cost real credits, so fixture-based development is essential from day one.

## Key Findings

### Recommended Stack

The official Anthropic MCP Python SDK (`mcp` 1.26.0) handles all protocol concerns — stdio transport, tool registration, JSON-RPC message routing. Do not implement these manually. The MCP SDK runs an async event loop, so `httpx.AsyncClient` is the natural HTTP client; the synchronous `requests` library must never be used inside async tool handlers. Configuration is managed via `pydantic-settings` `BaseSettings`, which loads `.env` files with type validation. The `python-gtmetrix2` third-party wrapper is unmaintained (last release 2021) and should be avoided — a direct `httpx` client is approximately 50 lines and gives full control.

**Core technologies:**
- `mcp` 1.26.0: MCP protocol implementation — official SDK, handles stdio transport and tool registration
- `httpx` 0.28.1: Async HTTP client — fits the async event loop natively; `requests` is forbidden
- `pydantic-settings` 2.x: Config/env management — type-validated API key loading from `.env`
- Python 3.11: Runtime — already configured in project, supported by all dependencies
- `uv`: Package manager — official MCP tooling standard, reproducible builds

### Expected Features

**Must have (table stakes):**
- `gtmetrix_analyze(url)` mega-tool — runs test, polls to completion, returns CWV + failing Lighthouse audits + slow resource summary in one call
- Automatic async polling until completion — users expect a single tool call to yield a result; poll at 3s intervals
- Core Web Vitals output (LCP, TBT, CLS, performance score) — headline metrics every performance tool exposes
- Filtered Lighthouse audits (failing only, score < 1) — actionable recommendations are the entire purpose
- HAR slow-resource summary (top 10 by duration/size) — identifies which files cause LCP/TBT failures
- `gtmetrix_check_status()` — surfaces credit balance before expensive operations
- Flat, LLM-readable output — no raw JSON:API envelopes; structured dicts Claude can reason on directly
- Errors returned as tool results with hints — not raised as exceptions that crash the tool

**Should have (competitive):**
- Test location parameter — GTMetrix tests from real CDN nodes, not just Google infrastructure
- Connection throttle presets (broadband/4G/3G) — models real mobile users; PSI wrappers only emulate
- Simulated device support — test on actual device profiles (PRO feature)
- Lighthouse category filter — reduce output noise for targeted audits

**Defer (v2+):**
- Separate granular tools (get_lighthouse, get_har) — only if mega-tool proves too coarse
- Retest a previous report — useful for regression testing; not needed for MVP
- Scheduled/monitoring tools — completely different workflow, out of scope

### Architecture Approach

The architecture separates into three layers: MCP tool functions (thin — validate inputs, call client, format output), a GTMetrix HTTP client (owns auth, polling state machine, error normalization), and response parsers (pure functions that strip JSON:API envelopes and reshape data for LLM consumption). Tools never construct HTTP requests directly. This separation makes each layer independently testable and isolates GTMetrix API changes to a single module.

**Major components:**
1. `main.py` — FastMCP instance creation, tool registration, `mcp.run()` stdio startup
2. `client/gtmetrix.py` — `httpx.AsyncClient` wrapper; auth, polling loop with timeout, error normalization
3. `client/parsers.py` — JSON:API unwrapping, Lighthouse audit filtering, HAR reshaping; pure functions
4. `tools/` — thin async tool functions decorated with `@mcp.tool()`; no HTTP logic
5. `config.py` — `pydantic-settings` BaseSettings; single source of truth for API key and settings

**Build order (dependency-driven):** config.py → parsers.py → gtmetrix.py → tools/account.py → tools/testing.py → tools/reports.py → main.py wiring

### Critical Pitfalls

1. **Stdout pollution corrupts stdio protocol** — configure `logging.basicConfig(stream=sys.stderr)` on day one; ban `print()` in all tool code; stdout is the wire, not a debug channel
2. **Raw JSON:API responses overflow Claude's context** — Lighthouse JSON can be 16MB+ and HAR files several MB; always filter to failing audits and top-N slow requests before returning; set a 50KB hard cap on tool responses
3. **Polling without a timeout hangs the server indefinitely** — implement a 120-second hard timeout (40 x 3s intervals); distinguish `finished`, `error`, and `timeout` states; return structured error with test ID on timeout
4. **Synchronous httpx blocks the async event loop** — use `httpx.AsyncClient` exclusively; share a single instance across tool calls; never use `requests` or `httpx.Client` (sync) in async handlers
5. **Missing JSON:API Content-Type causes all POST requests to fail** — GTMetrix requires `Content-Type: application/vnd.api+json` (not `application/json`) on all POST requests; define as a module-level constant on the shared client

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Core Server Scaffold and HTTP Client

**Rationale:** All other work depends on a working MCP server with correct stdio behavior and a proven GTMetrix HTTP client. The pitfalls that require Phase 1 prevention far outnumber those in later phases — stdout, async client, Content-Type, polling timeout, and response schema design must all be established before writing any tool logic.

**Delivers:** A running MCP server that Claude Code can connect to, plus a GTMetrix client that can authenticate and submit/poll a test against real API. No tools exposed yet beyond `check_status`.

**Addresses:** `gtmetrix_check_status` tool (table stakes); `config.py` with API key loading

**Avoids:** Stdout corruption, sync httpx blocking, missing Content-Type header, credit exhaustion during development (fixture loading)

### Phase 2: Core Test Workflow (gtmetrix_analyze)

**Rationale:** This is the single most valuable deliverable. Everything else in the feature set is additive. Once the analyze mega-tool works end-to-end, the MCP server has its core value proposition.

**Delivers:** `gtmetrix_analyze(url)` — runs test, polls to completion, returns CWV + filtered Lighthouse audits + HAR slow-resource summary in one tool call

**Implements:** Polling state machine, JSON:API parser, Lighthouse audit filter (score < 1), HAR top-10 extractor, flat output formatting

**Avoids:** Lighthouse/HAR size overflow (critical), polling timeout (critical)

### Phase 3: Location and Throttle Parameters

**Rationale:** GTMetrix's geographic and network testing capabilities are the primary differentiator over free PSI wrappers. These are low-implementation-cost features that significantly expand utility.

**Delivers:** Location parameter on `gtmetrix_analyze`, connection throttle presets (broadband/4G/3G), simulated device support; lazy-loaded location/device ID validation

**Uses:** Existing GTMetrix client — adds parameters to test submission; fetches `/locations` and `/simulated-devices` on first use

### Phase 4: Output Refinement and Polish

**Rationale:** After the core workflow is validated against real URLs, output quality issues become apparent. Lighthouse category filtering, HAR summary statistics, and actionable error messages are discovered needs, not guessed ones.

**Delivers:** Lighthouse category filter, prioritized slow-resource list (render-blocking first), structured error messages mapping GTMetrix E-codes to actionable hints, credit warning integration

**Avoids:** UX pitfalls (generic errors, noisy output, no credit warning)

### Phase Ordering Rationale

- **Config and HTTP client before tools:** Every tool depends on the client; the client depends on config. The build order from ARCHITECTURE.md makes this explicit.
- **Mega-tool before granular tools:** FEATURES.md is clear that `gtmetrix_analyze` is the primary tool and granular tools (get_lighthouse, get_har) are deferred to v2. Phase 2 implements the full mega-tool, not intermediate primitives.
- **Location/throttle in Phase 3, not Phase 2:** These are parameters to an already-working tool, not architectural additions. Deferring reduces Phase 2 complexity and allows validation of core workflow first.
- **Output refinement last:** Phase 4 issues (noisy output, poor error messages) are only discoverable after running against real URLs in Phase 2/3.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** HAR parsing logic is non-trivial — the specific fields to extract and the "slow resource" ranking algorithm need validation against real GTMetrix HAR output. The 303 redirect handling behavior also needs verification against live API.
- **Phase 3:** Device and location ID resolution (lazy vs. startup caching tradeoffs); GTMetrix PRO vs. free account feature gates for device simulation.

Phases with standard patterns (skip research-phase):
- **Phase 1:** MCP stdio server scaffold is well-documented in official SDK. httpx AsyncClient pattern is established. Config via pydantic-settings is straightforward.
- **Phase 4:** Output formatting is pure implementation — no external unknowns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core libraries verified via PyPI and official MCP docs; only uv-as-standard is MEDIUM (community pattern) |
| Features | HIGH | Based on official GTMetrix API docs and MCP best practices; competitor analysis confirms differentiators |
| Architecture | HIGH | Official MCP SDK patterns, clear build order with no ambiguities |
| Pitfalls | HIGH | Critical pitfalls verified via official issue trackers and GTMetrix error documentation |

**Overall confidence:** HIGH

### Gaps to Address

- **HAR field schema:** The exact structure of GTMetrix's HAR response fields (vs. standard HAR 1.2 spec) is not fully documented in the API docs. Validate against a real test response before writing the parser.
- **303 redirect behavior:** PITFALLS.md notes two valid approaches (follow_redirects=True vs. manual Location header extraction). The correct behavior when `follow_redirects=True` hits the report URL needs to be confirmed against live API in Phase 1 integration testing.
- **Credit cost per test type:** PITFALLS.md notes 1 credit for Lighthouse, 0.6 for metrics-only. Confirm this against current GTMetrix pricing to avoid surprises during development.
- **PRO vs. free account feature gates:** Simulated device support is flagged as PRO. The available features on the target account type should be confirmed before planning Phase 3 scope.

## Sources

### Primary (HIGH confidence)
- https://gtmetrix.com/api/docs/2.0/ — GTMetrix REST API v2.0 official documentation
- https://pypi.org/project/mcp/ — mcp SDK version and Python requirements
- https://github.com/modelcontextprotocol/python-sdk — FastMCP patterns, stdio transport
- https://modelcontextprotocol.io/docs/develop/build-server — official MCP build guide
- https://www.python-httpx.org/async/ — httpx AsyncClient patterns
- https://docs.pydantic.dev/latest/concepts/pydantic_settings/ — BaseSettings pattern
- https://gtmetrix.com/blog/general-gtmetrix-test-errors/ — GTMetrix error types and credit behavior
- https://github.com/anthropics/claude-code/issues/2638 — MCP tool response truncation limits

### Secondary (MEDIUM confidence)
- https://www.philschmid.de/mcp-best-practices — MCP design principles (outcomes over operations)
- https://nearform.com/digital-community/implementing-model-context-protocol-mcp-tips-tricks-and-pitfalls/ — MCP implementation pitfalls
- https://www.scalekit.com/blog/wrap-mcp-around-existing-api — API wrapping design guidance
- https://docs.astral.sh/uv/guides/projects/ — uv as standard for MCP projects
- https://github.com/ruvnet/claude-flow/issues/835 — stdio stdout corruption real-world case
- https://scottspence.com/posts/optimising-mcp-server-context-usage-in-claude-code — token consumption patterns

### Tertiary (LOW confidence)
- https://python-gtmetrix2.readthedocs.io/en/latest/changelog.html — reference for GTMetrix API patterns (library itself is abandoned)
- https://github.com/GoogleChrome/lighthouse/issues/5490 — Lighthouse JSON size context

---
*Research completed: 2026-03-04*
*Ready for roadmap: yes*
