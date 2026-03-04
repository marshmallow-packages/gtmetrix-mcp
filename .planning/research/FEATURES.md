# Feature Research

**Domain:** MCP server wrapping a web performance testing API (GTMetrix v2.0)
**Researched:** 2026-03-04
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = server feels incomplete or unusable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `gtmetrix_run_test(url)` tool | Core value — without this nothing works | LOW | POST /api/2.0/tests with sensible defaults; returns test_id |
| Automatic polling until completion | Users expect a single tool call to yield a result | MEDIUM | Poll /tests/{id} at 3s intervals, follow 303 redirect to report |
| Return Core Web Vitals (LCP, TBT, CLS, performance score) | Every performance tool surfaces these; they're the headline metrics | LOW | Parse from report attributes; format as flat key-value pairs, not nested JSON:API |
| Return Lighthouse audit list (failing audits only) | Actionable recommendations are the entire point for code-level fixes | MEDIUM | Fetch Lighthouse JSON resource from report; filter to audits with score < 1; truncate raw JSON to title, description, displayValue, score |
| Return HAR waterfall summary | Slow resources cause LCP/TBT failures; identifying them closes the loop | MEDIUM | Fetch HAR resource; extract entries sorted by duration; surface top N slow or large requests |
| `gtmetrix_check_status` tool | Users need to know if API credits remain before running expensive tests | LOW | GET /api/2.0/status; return credits_left, account_type, refill date |
| Structured flat output (not raw JSON:API) | LLMs reason poorly on deeply nested responses; flat is faster and cheaper | LOW | Strip JSON:API envelope; reshape to readable dicts before returning |
| Meaningful error messages returned (not raised) | MCP protocol: errors in tool result, not protocol layer | LOW | Return `{"error": "...", "hint": "..."}` strings so Claude can self-correct |

### Differentiators (Competitive Advantage)

Features that set this server apart from generic PageSpeed/PSI wrappers.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `gtmetrix_run_test` with test location parameter | GTMetrix tests from real CDN nodes globally; PSI wrappers test from Google infra only | LOW | Expose location_id; default to closest/fastest; fetch /api/2.0/locations to validate |
| Connection throttle preset support | Simulates real mobile users on 3G/4G — PSI only does mobile emulation, not network throttling | LOW | Accept enum: "broadband", "4G", "3G"; map to GTMetrix connection profiles |
| Simulated device support (PRO) | Test on actual iPhone/Samsung specs, not just viewport resize | LOW | Accept device name; resolve to simulated_device_id via /api/2.0/simulated-devices |
| Outcome-oriented `gtmetrix_analyze(url)` mega-tool | Single tool call that runs test + polls + fetches CWV + fetches top Lighthouse failures + fetches slow resources | MEDIUM | Follows MCP best practice: outcomes over operations; reduces Claude round-trips from 4 to 1 |
| Lighthouse audit filtering by category | Surface only render-blocking, image, JS, or CSS issues depending on what's in the codebase | LOW | Accept optional category filter: "performance", "network", "images", "scripts" |
| Prioritized slow-resource list from HAR | Tell Claude exactly which files to fix and why (size, TTFB, duration) | MEDIUM | Sort HAR entries by: (1) render-blocking + large, (2) large, (3) slow TTFB; surface top 10 with URL, size, duration |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems for this use case.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Expose all raw GTMetrix API endpoints as 1:1 tools | Feels complete; API-parity is familiar | Bloats context window; forces Claude to orchestrate multi-step flows itself; violates MCP design principle of "outcomes over operations" | Expose 2-3 outcome-focused tools that internally call multiple endpoints |
| Return full Lighthouse JSON | Developers want all the data | 200KB+ JSON destroys context; Claude wastes tokens on passing audits | Filter to failing audits only; truncate descriptions to 200 chars; strip rawValue/numericValue |
| Return full HAR file | Network waterfall is useful | HAR for a typical page is 1-2MB; completely unusable in context | Extract and reshape top 10-20 entries with only URL, initiatorType, duration, transferSize, status |
| Screenshot/filmstrip retrieval | Seems useful for visual analysis | Claude Code has no vision in tool output flow; binary data adds zero value; costs extra | Skip entirely — out of scope per PROJECT.md |
| Caching of test results | Avoids re-running expensive tests | GTMetrix tests cost credits not time; results are fresh/point-in-time; caching stale data misleads diagnosis | Let users explicitly retest; don't cache silently |
| Scheduled/monitoring tools | GTMetrix supports this via pages/monitoring | Completely different workflow; adds auth state, page management complexity | Out of scope — on-demand only |
| Exposing account management (delete reports, manage pages) | Full API coverage | Destructive operations via LLM are risky; Claude could delete report history | Never expose DELETE endpoints as tools |

## Feature Dependencies

```
gtmetrix_check_status
    (independent — check before expensive operations)

gtmetrix_run_test(url, ...)
    └──polls──> test completion (303 redirect to report_id)
                    ├──requires──> fetch_report_metrics (CWV, scores)
                    ├──requires──> fetch_lighthouse_json (Lighthouse resource URL from report)
                    └──requires──> fetch_har_data (HAR resource URL from report)

gtmetrix_analyze(url, ...) [mega-tool]
    └──wraps──> gtmetrix_run_test
                    └──wraps──> fetch_report_metrics
                    └──wraps──> fetch_lighthouse_json + filter
                    └──wraps──> fetch_har_data + reshape

Location/Device support
    └──requires──> /api/2.0/locations (fetch valid IDs at startup or lazily)
    └──requires──> /api/2.0/simulated-devices (fetch valid IDs at startup or lazily)
```

### Dependency Notes

- **Polling requires test_id from run_test:** The GTMetrix test is async; polling is not optional. The 303 redirect on completion gives the report URL.
- **Lighthouse and HAR require report resource URLs:** The report response contains `links` to Lighthouse JSON and HAR as separate fetchable resources. These are not inline in the report response.
- **gtmetrix_analyze wraps everything:** This is the primary tool Claude should call. The lower-level tools (run_test, fetch metrics individually) are internal implementation details, not separate exposed tools.
- **Location/device ID validation requires API calls:** IDs are not guessable. Either cache at startup (slows boot) or fetch lazily on first use and cache in memory.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the core loop: scan URL → get actionable data → guide code fix.

- [ ] `gtmetrix_analyze(url)` — runs test, polls to completion, returns CWV + failing Lighthouse audits + top slow resources in one structured response
- [ ] `gtmetrix_check_status()` — returns credits and account info so Claude can warn before running out
- [ ] Flat, LLM-readable output format — no raw JSON:API envelopes, no multi-MB dumps
- [ ] Errors returned as tool results with hints — not raised as exceptions

### Add After Validation (v1.x)

Features to add once core workflow is proven useful.

- [ ] Location parameter on `gtmetrix_analyze` — add once there's demand for non-default geography testing
- [ ] Connection throttle preset — add when mobile testing becomes the primary use case
- [ ] Simulated device support — add when testing specific device profiles is needed
- [ ] Lighthouse category filter — add if output is too noisy; may not be needed if default filtering is good

### Future Consideration (v2+)

Features to defer until the tool is actually in regular use.

- [ ] Separate granular tools (`gtmetrix_get_lighthouse`, `gtmetrix_get_har`) — only if the mega-tool proves too coarse; most scenarios want everything
- [ ] Retest a previous report — useful for regression testing; deferred because MVP is on-demand scanning

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `gtmetrix_analyze` mega-tool | HIGH | MEDIUM | P1 |
| Automatic polling to completion | HIGH | MEDIUM | P1 |
| Failing Lighthouse audits (filtered) | HIGH | LOW | P1 |
| HAR slow-resource summary (top 10) | HIGH | MEDIUM | P1 |
| Core Web Vitals (CWV) output | HIGH | LOW | P1 |
| `gtmetrix_check_status` | MEDIUM | LOW | P1 |
| Flat output formatting (not raw JSON:API) | HIGH | LOW | P1 |
| Error results (not exceptions) | HIGH | LOW | P1 |
| Location parameter | MEDIUM | LOW | P2 |
| Connection throttle presets | MEDIUM | LOW | P2 |
| Simulated device support | LOW | LOW | P2 |
| Lighthouse category filter | MEDIUM | LOW | P2 |
| Full HAR exposure | LOW | LOW | P3 (anti-feature) |
| Raw Lighthouse JSON | LOW | LOW | P3 (anti-feature) |
| DELETE/management tools | LOW | LOW | never |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | PageSpeed Insights MCP servers | Chrome DevTools MCP | This Server (GTMetrix) |
|---------|-------------------------------|--------------------|-----------------------|
| Core Web Vitals | Yes | Yes | Yes |
| Lighthouse audits | Yes (all or filtered) | Yes | Yes (failing only) |
| HAR/waterfall | Yes | Yes (trace-based) | Yes (real HAR from GTMetrix) |
| Real network throttling | No (emulation only) | Partial (DevTools network) | Yes (3G/4G/LTE presets) |
| Multiple test locations | No (Google infra only) | No | Yes (GTMetrix CDN nodes) |
| Real device simulation | No | No | Yes (40+ device profiles) |
| Field data (CrUX) | Yes (PSI includes CrUX) | No | No — lab data only |
| Free to use | Yes (Google API key) | Yes (Chrome required) | No (costs GTMetrix credits) |
| On-demand for any URL | Yes | Yes | Yes |
| Structured LLM output | Varies by impl | Varies | Designed-in from start |

**Key insight:** GTMetrix's differentiator is real network throttling and geographic diversity. PSI/Lighthouse wrappers are free but test from Google infrastructure with emulated networks. GTMetrix costs credits but models real-world conditions better — which matters when debugging issues that only appear on slow mobile connections or specific CDN edge locations.

## Sources

- [GTMetrix REST API v2.0 Documentation](https://gtmetrix.com/api/docs/2.0/) — HIGH confidence, official docs
- [MCP Best Practices — Phil Schmid](https://www.philschmid.de/mcp-best-practices) — MEDIUM confidence, authoritative practitioner
- [PageSpeed Insights MCP (ruslanlap)](https://github.com/ruslanlap/pagespeed-insights-mcp) — MEDIUM confidence, reference implementation
- [AI Core Web Vitals Debugging](https://www.corewebvitals.io/pagespeed/ai-core-web-vitals-debugging) — MEDIUM confidence, domain expertise
- [Should you wrap MCP around your existing API? — Scalekit](https://www.scalekit.com/blog/wrap-mcp-around-existing-api) — MEDIUM confidence, design guidance
- [PageSpeed MCP Server — Glama](https://glama.ai/mcp/servers/@PhialsBasement/Pagespeed-MCP-Server) — MEDIUM confidence, competitor analysis

---
*Feature research for: GTMetrix MCP Server (Python, stdio, Claude Code)*
*Researched: 2026-03-04*
