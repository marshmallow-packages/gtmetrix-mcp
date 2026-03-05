# Requirements: GTMetrix MCP Server

**Defined:** 2026-03-04
**Core Value:** Scan a URL and get back structured performance data that Claude can reason about and use to guide code-level fixes.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Server Foundation

- [x] **SERV-01**: MCP server starts via stdio transport and registers tools with Claude Code
- [x] **SERV-02**: API key loaded from .env file via pydantic-settings
- [x] **SERV-03**: All HTTP calls use httpx.AsyncClient (no sync blocking)
- [x] **SERV-04**: JSON:API v1.1 responses parsed to flat dicts before returning to Claude
- [x] **SERV-05**: Errors returned as structured tool results with hints (not raised as exceptions)
- [x] **SERV-06**: No stdout output except MCP protocol (logging to stderr only)

### Test Execution

- [x] **TEST-01**: User can start a GTMetrix test for any URL via `gtmetrix_analyze(url)`
- [x] **TEST-02**: Test polls automatically every 3 seconds until completion
- [x] **TEST-03**: Polling has a hard timeout (default 5 minutes) to prevent hangs
- [x] **TEST-04**: User can specify test location via location parameter
- [x] **TEST-05**: Location IDs fetched from API and cached in memory

### Report Data

- [x] **REPT-01**: Report returns Core Web Vitals: LCP, TBT, CLS, performance score, structure score
- [x] **REPT-02**: Report returns failing Lighthouse audits (score < 1) with title, description, displayValue
- [x] **REPT-03**: Report returns top 10 slowest/largest resources from HAR waterfall with URL, size, duration
- [x] **REPT-04**: All report data returned in a single structured response from `gtmetrix_analyze`

### Account

- [x] **ACCT-01**: `gtmetrix_check_status()` returns API credits remaining, account type, refill date

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Test Options

- **OPTS-01**: Connection throttle presets (3G, 4G, broadband)
- **OPTS-02**: Simulated device support (iPhone, Samsung profiles)
- **OPTS-03**: Lighthouse audit category filter (performance, network, images, scripts)

### Granular Tools

- **GRAN-01**: Separate `gtmetrix_get_lighthouse(report_id)` tool for detailed audit data
- **GRAN-02**: Separate `gtmetrix_get_har(report_id)` tool for detailed waterfall data

## Out of Scope

| Feature | Reason |
|---------|--------|
| Screenshots/video filmstrip | Claude Code has no vision in tool output; binary data adds zero value |
| Scheduled/recurring scans | Different workflow entirely; on-demand only |
| Report deletion/management | Destructive operations via LLM are risky |
| Full raw Lighthouse JSON | 200KB+ destroys context window; filtered output only |
| Full raw HAR file | 1-2MB unusable in context; top-N summary only |
| Caching test results | Results are point-in-time; caching misleads diagnosis |
| PDF report generation | Scanning own projects, not client reporting |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SERV-01 | Phase 1 | Complete |
| SERV-02 | Phase 1 | In Progress |
| SERV-03 | Phase 1 | Complete |
| SERV-04 | Phase 1 | Complete |
| SERV-05 | Phase 1 | Complete |
| SERV-06 | Phase 1 | In Progress |
| ACCT-01 | Phase 1 | Complete |
| TEST-01 | Phase 2 | Complete |
| TEST-02 | Phase 2 | Complete |
| TEST-03 | Phase 2 | Complete |
| REPT-01 | Phase 2 | Complete |
| REPT-02 | Phase 2 | Complete |
| REPT-03 | Phase 2 | Complete |
| REPT-04 | Phase 2 | Complete |
| TEST-04 | Phase 3 | Complete |
| TEST-05 | Phase 3 | Complete |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-04*
*Last updated: 2026-03-04 after roadmap creation*
