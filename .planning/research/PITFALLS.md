# Pitfalls Research

**Domain:** MCP Server wrapping REST API (GTMetrix API v2.0 / Python / stdio)
**Researched:** 2026-03-04
**Confidence:** HIGH (MCP stdio pitfalls), HIGH (GTMetrix API specifics), MEDIUM (response size impacts)

---

## Critical Pitfalls

### Pitfall 1: Stdout Pollution Corrupts the stdio Protocol Stream

**What goes wrong:**
Any write to stdout — from `print()`, a logging handler, an exception traceback, or a third-party library — is interpreted as a JSON-RPC message by the MCP client. The protocol breaks silently or produces cryptic parse errors on the Claude Code side.

**Why it happens:**
Python's default `print()` and `logging.StreamHandler()` both write to stdout. Developers add debug prints during development, forget to remove them, or a dependency (e.g., `httpx` tracing) emits output on import. In stdio transport mode there is no separate channel for diagnostics — stdout is the wire.

**How to avoid:**
- Configure logging to stderr from day one: `logging.basicConfig(stream=sys.stderr)`
- Ban `print()` in all tool code; use `logger.debug()` exclusively
- Set `follow_redirects=True` on the httpx client and suppress its event hooks to stderr
- Use the MCP SDK's built-in `get_logger()` (FastMCP) or equivalent which routes to stderr automatically
- Add a CI lint rule: `grep -r "print(" src/` fails the build

**Warning signs:**
- Claude Code shows JSON parse errors or "unexpected token" in MCP output
- MCP inspector shows malformed protocol frames
- Works in isolation but breaks when connected to Claude Code

**Phase to address:** Phase 1 (core server scaffold) — before any tool code is written

---

### Pitfall 2: Returning Raw JSON:API Envelopes to Claude

**What goes wrong:**
The GTMetrix API wraps every response in a JSON:API v1.1 envelope: `{ "data": { "type": "...", "id": "...", "attributes": { ... }, "links": { ... } } }`. If tools return this structure verbatim, Claude receives noisy wrapper fields alongside the actual data. It burns tokens on irrelevant metadata, produces worse reasoning, and may miss nested attributes.

**Why it happens:**
Developers pass `response.json()` directly as the tool return value. It's the path of least resistance, and the output looks "complete." The semantic mismatch between JSON:API resource documents and LLM-consumable payloads is not obvious until reasoning quality degrades.

**How to avoid:**
- Parse and flatten all responses before returning: extract `data.attributes` and the fields Claude needs
- Return typed dicts or dataclasses, not raw API responses
- For Lighthouse audits, return only failed/warning audits with `score`, `title`, `description`, `displayValue` — not the full 16MB report
- For HAR waterfall, return only the top-N slowest requests, not every entry
- Include a `_meta` block with key stats (total resources, total size, test duration) for context without bulk

**Warning signs:**
- Tool responses contain `type`, `id`, `links`, `relationships` keys
- Claude starts reasoning about "resource object structure" instead of performance data
- Tool responses approach or exceed 10KB

**Phase to address:** Phase 1 (define response shapes before implementing tools)

---

### Pitfall 3: Lighthouse JSON and HAR Files Exceed Claude's Tool Response Limit

**What goes wrong:**
A full Lighthouse JSON report can exceed 16MB. HAR files for content-heavy pages are several MB. Claude Code truncates MCP tool responses at approximately 25,000 tokens (~100KB of JSON). Returning unsized payloads causes silent truncation — Claude receives partial data without knowing it's partial.

**Why it happens:**
The GTMetrix API stores Lighthouse JSON as a separate downloadable resource (`lighthouse.json`). Developers fetch it and return it whole because it's "the complete data." The size problem only appears on real-world pages, not minimal test URLs.

**How to avoid:**
- Never return the full Lighthouse JSON. Extract and return only audits with `score < 1` (failing/warning), with fields: `id`, `title`, `description`, `score`, `displayValue`, `details.items` (top 3)
- Never return the full HAR. Return a summary: total requests, total transfer size, top 10 slowest requests with URL, duration, size, and type
- Add a `truncated: true` flag when filtering, with a count of omitted items
- Test response sizes against real-world URLs, not localhost or minimal pages
- Set a hard cap (e.g., 50KB) on any single tool response — log a warning if filtering still produces > 50KB

**Warning signs:**
- Responses from `get_lighthouse_audits` or `get_har_data` take > 2 seconds to serialize
- Any tool response is > 500 lines of JSON
- Claude reasoning references "partial data" or seems to miss obvious issues

**Phase to address:** Phase 1 (design response shapes), Phase 2 (validation against real URLs)

---

### Pitfall 4: Polling Without a Timeout Hangs the MCP Tool Indefinitely

**What goes wrong:**
The GTMetrix test lifecycle is: `queued → started → finished` (or `error`). Tests are retained for only 24 hours, and a test can legitimately take 30–90 seconds on congested servers. If the polling loop has no maximum duration, the MCP tool call blocks Claude Code's tool executor forever, producing a hung session.

**Why it happens:**
Developers implement `while state != "finished": sleep(3)` which works 95% of the time. Edge cases — GTMetrix server error, network blip during poll, test stuck in `started` — are not handled in early prototypes.

**How to avoid:**
- Implement a polling loop with a hard timeout (e.g., 120 seconds, 40 × 3s intervals)
- Distinguish terminal states: `finished` (success), `error` (GTMetrix-side failure), `timeout` (our limit)
- On timeout, return a structured error with the test ID so the user can re-query later
- The 303 redirect on completion: set `follow_redirects=False` on status polls and handle 303 manually, or set `follow_redirects=True` and detect the final URL — do not assume the redirect lands on a parseable endpoint without testing

**Warning signs:**
- The `get_test_status` or `run_test` tool never returns during development
- Test IDs from failed runs are reused without checking state
- No timeout constant defined in the codebase

**Phase to address:** Phase 1 (core polling implementation)

---

### Pitfall 5: Credits Consumed by Failed or Redundant Tests

**What goes wrong:**
GTMetrix charges credits at test submission time. A test submitted to a URL returning 403 (GTMetrix blocked by firewall), SSL error, or DNS failure still consumes credits and returns a `state: error` report. Submitting the same URL repeatedly during development burns a PRO account's daily credit budget faster than expected.

**Why it happens:**
Developers treat the API like a free sandbox during development. GTMetrix's error page (`/blog/general-gtmetrix-test-errors/`) lists common failure modes that deduct credits: blocked IPs, SSL errors, DNS failures, 2-minute timeout exceeded. None of these are obvious until credits run low.

**How to avoid:**
- Always call `GET /status` before submitting tests during development to verify credit balance
- Use a well-known fast URL (e.g., `https://example.com`) during tool integration testing — not actual client URLs
- Cache test results for development: serialize the API response to a JSON fixture on disk, use the fixture in unit tests
- Expose credit balance in the `check_account_status` tool so Claude can warn when balance is low
- Document the credit cost per test type: Lighthouse = 1 credit, metrics-only = 0.6

**Warning signs:**
- Credit balance unexpectedly drops during development sprints
- `E40201` (insufficient credits) errors appear during testing
- No fixture-based test coverage

**Phase to address:** Phase 1 (add fixture loading for dev), Phase 2 (add credit check tooling)

---

### Pitfall 6: Using Synchronous httpx Inside Async Tool Handlers Blocks the Event Loop

**What goes wrong:**
The MCP Python SDK runs tools in an async context. Calling `httpx.get()` (the synchronous client) inside an async tool handler blocks the entire asyncio event loop. While the HTTP request is in-flight, no other MCP protocol messages can be processed. With polling loops that issue many requests, the server becomes unresponsive.

**Why it happens:**
`httpx` provides both sync and async APIs with identical surface area. Copy-pasting examples from the GTMetrix docs (which show `requests.get()`) into async tool handlers introduces blocking without any immediate error — it works, but blocks.

**How to avoid:**
- Use `httpx.AsyncClient` exclusively; make all HTTP calls `await client.get(...)`
- Share a single `AsyncClient` instance across tool calls (connection pooling) — do not instantiate per-call
- Manage client lifecycle at server startup/shutdown, not inside tool handlers
- Never use `requests` library; `httpx.AsyncClient` is the only HTTP client in the codebase

**Warning signs:**
- `import requests` appears anywhere in the codebase
- `httpx.Client` (sync) used inside `async def` tool handlers
- MCP inspector shows the server stops responding during long polls

**Phase to address:** Phase 1 (establish httpx client pattern before writing any tools)

---

### Pitfall 7: Missing Content-Type Header Causes Silent 415 Errors

**What goes wrong:**
GTMetrix API v2.0 requires `Content-Type: application/vnd.api+json` on POST requests. Omitting it returns a `415 Unsupported Media Type` error. The standard `application/json` header is rejected. This is non-obvious and causes every test submission to fail until discovered.

**Why it happens:**
Python HTTP clients default to `application/json` or omit content-type for JSON bodies. The JSON:API content-type requirement is buried in the API documentation and not enforced at the SDK level.

**How to avoid:**
- Set `headers={"Content-Type": "application/vnd.api+json", "Accept": "application/vnd.api+json"}` on the shared `AsyncClient`
- Define these as module-level constants, not inline strings
- Add a test that submits a POST without the content-type and asserts `415`

**Warning signs:**
- All POST requests return 415 with `E41500` error code
- Test submission works via curl but fails from Python

**Phase to address:** Phase 1 (HTTP client setup)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Return raw `response.json()` from tools | Zero parsing code | Claude reasons poorly, burns context tokens, truncation risk | Never — always parse to domain model |
| Inline `httpx.AsyncClient()` per tool call | Simpler code | No connection pooling, slower tests, potential resource leaks | Never — use shared client |
| `print()` for debugging | Fast debugging | Corrupts stdio protocol | Never in production; only with stderr redirect |
| `while True: poll()` without timeout | Simpler loop | Infinite hangs on error states | Never — always timeout |
| Skip credit check before tests | Faster dev loop | Credits exhausted unexpectedly | Only with fixture-based test mode |
| Return full Lighthouse JSON | "Complete" data | Exceeds token limit, truncated silently | Never — always filter to failing audits |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| GTMetrix API auth | Passing API key as Bearer token or query param | HTTP Basic auth with API key as username, empty password |
| GTMetrix POST body | Sending flat JSON `{"url": "..."}` | JSON:API document: `{"data": {"type": "test", "attributes": {"url": "..."}}}` |
| GTMetrix test polling | Treating 303 as an error | 303 is success — follow Location header to the report resource |
| GTMetrix error codes | Only checking HTTP status | Parse `errors[0].code` (E-prefixed) for actionable error type |
| GTMetrix report expiry | Fetching report data immediately | Reports expire after 1 month; optimized files after 24 hours |
| httpx redirect | `httpx.AsyncClient` follows redirects by default | For status polling, set `follow_redirects=True` and check final URL to detect completion |
| MCP tool return | Returning Python exceptions as strings | Use MCP SDK error response types; unhandled exceptions crash the tool silently |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Per-request `AsyncClient` instantiation | Slow test submissions, connection overhead | Single shared client with connection pooling | Every tool call (immediately) |
| Full Lighthouse JSON in tool response | 2-3s serialization, Claude truncation | Filter to failing audits only | Any real-world URL |
| Polling with 1s interval | 429 rate limit errors (960 req/60s PRO) | Use 3s interval as documented | >5 concurrent polls |
| Full HAR waterfall return | Response exceeds 25K token limit | Return top-10 slowest only | Pages with >50 resources |
| Blocking sync HTTP in async handler | MCP server freezes during tool execution | Use `httpx.AsyncClient` exclusively | Every long poll |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Hardcoding API key in source code | Key leaked to version control | Always read from `.env` / environment variables |
| Logging full HTTP request/response | API key exposed in logs | Log only method, URL, status code — never headers or auth |
| Passing user-supplied URLs without validation | Prompting the API to scan internal/localhost addresses | Validate URL format and reject `localhost`, `127.*`, `10.*`, `192.168.*` if unintended |
| Exposing full API error details to Claude | Internal account information in Claude context | Normalize errors to user-facing messages; strip account IDs |
| Storing test results with API key in fixture files | API key in repo history | Strip auth headers from fixtures; use placeholder keys in test data |

---

## UX Pitfalls (Claude Interaction Quality)

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Tool returns only a score number | Claude cannot give actionable advice | Return score + top failing audits with descriptions |
| Tool returns all 60+ Lighthouse audits | Claude buries key issues in noise | Return only `score < 0.9` audits, sorted by impact |
| No test status in polling tool | User cannot tell if scan is running | Return `state`, `started_at`, `elapsed_seconds` during polling |
| Credit balance not surfaced | User submits tests until credits run out | Include `api_credits_available` in `check_account_status` tool |
| Generic error message on test failure | Claude cannot help troubleshoot | Map GTMetrix error types to actionable messages (SSL, DNS, blocked, timeout) |
| HAR data without summary stats | Claude has to count/sum manually | Prepend summary: total requests, total bytes, load time, slowest resource |

---

## "Looks Done But Isn't" Checklist

- [ ] **Test submission:** Returns a test ID, but does it handle the `E40201` insufficient credits case with a clear error?
- [ ] **Polling loop:** Completes on `finished` state, but does it handle `error` state and `timeout` separately?
- [ ] **303 redirect handling:** The poll detects completion, but is the redirect Location header actually parsed to extract the report URL?
- [ ] **Lighthouse tool:** Returns audit data, but is the full JSON filtered — or is the raw 16MB object being serialized?
- [ ] **HAR tool:** Returns waterfall data, but is it the top-N filtered list or all entries?
- [ ] **Error handling:** HTTP errors are caught, but are GTMetrix E-code errors parsed and surfaced distinctly?
- [ ] **stdout clean:** Tools work locally, but does `grep -r "print(" src/` return zero results?
- [ ] **Content-Type header:** POST requests work, but is `application/vnd.api+json` set — not `application/json`?
- [ ] **Async client:** HTTP calls await properly, but is a single shared `AsyncClient` used — not one instantiated per call?
- [ ] **Credit guard:** Tests run, but does the server surface remaining credit balance so Claude can warn before exhaustion?

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| stdout corruption discovered late | LOW | Add `logging.basicConfig(stream=sys.stderr)` at entrypoint; grep and remove all `print()` |
| Raw JSON:API responses returned | MEDIUM | Add a parsing layer between API client and tool return; update all tool return values |
| Polling timeout missing | LOW | Add timeout constant and counter to polling loop; add `state: timeout` to tool response contract |
| Full Lighthouse JSON returned | MEDIUM | Implement audit filter function; update `get_lighthouse_audits` tool to use it |
| Credits exhausted during dev | LOW | Load fixtures from disk; create `GTMETRIX_USE_FIXTURES=true` env flag |
| Sync httpx in async handler | LOW | Replace `httpx.Client` with `httpx.AsyncClient`; add `await` to all HTTP calls |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Stdout corruption | Phase 1: Server scaffold | `grep -r "print(" src/` returns zero; MCP inspector shows clean protocol frames |
| Raw JSON:API responses | Phase 1: Define response schemas before tools | All tool returns are typed dicts, not raw `response.json()` |
| Lighthouse/HAR size overflow | Phase 1: Design, Phase 2: Real URL testing | Tool responses tested against `https://bbc.co.uk` or similar large page |
| Polling without timeout | Phase 1: Core polling loop | Unit test: mock `state: started` forever, assert `TimeoutError` raised |
| Credit consumption during dev | Phase 1: Fixture loading | Tests pass with `GTMETRIX_USE_FIXTURES=true`; no live API calls in unit tests |
| Sync httpx blocking | Phase 1: HTTP client pattern | No `import requests` or `httpx.Client` in codebase |
| Missing Content-Type header | Phase 1: HTTP client setup | POST to GTMetrix returns 200 (not 415) in integration test |

---

## Sources

- GTMetrix REST API v2.0 official docs: https://gtmetrix.com/api/docs/2.0/ (HIGH confidence)
- GTMetrix general test errors: https://gtmetrix.com/blog/general-gtmetrix-test-errors/ (HIGH confidence)
- Nearform: MCP implementation pitfalls: https://nearform.com/digital-community/implementing-model-context-protocol-mcp-tips-tricks-and-pitfalls/ (HIGH confidence)
- MCP is not REST API (Lee Han Chung): https://leehanchung.github.io/blogs/2025/05/17/mcp-is-not-rest-api/ (MEDIUM confidence)
- Claude Code MCP tool response truncation issue: https://github.com/anthropics/claude-code/issues/2638 (HIGH confidence)
- MCP stdio stdout corruption (claude-flow): https://github.com/ruvnet/claude-flow/issues/835 (HIGH confidence)
- httpx AsyncClient event loop issues: https://github.com/encode/httpx/discussions/2959 (HIGH confidence)
- Lighthouse JSON report size (>16MB concern): https://github.com/GoogleChrome/lighthouse/issues/5490 (MEDIUM confidence)
- MCP context token consumption patterns: https://scottspence.com/posts/optimising-mcp-server-context-usage-in-claude-code (MEDIUM confidence)

---
*Pitfalls research for: GTMetrix MCP Server (Python, stdio, JSON:API)*
*Researched: 2026-03-04*
