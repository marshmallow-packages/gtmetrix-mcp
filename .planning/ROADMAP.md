# Roadmap: GTMetrix MCP Server

## Overview

Build a Python MCP server in three phases: establish a working server scaffold with proven stdio safety and a functional GTMetrix HTTP client, then implement the core `gtmetrix_analyze` mega-tool that runs tests end-to-end and returns structured performance data Claude can reason about, then add geographic and network test parameters that make GTMetrix meaningfully better than free PageSpeed wrappers.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Server Foundation** - Working MCP server connected to Claude Code with GTMetrix auth and account status tool (completed 2026-03-04)
- [ ] **Phase 2: Core Analyze Workflow** - `gtmetrix_analyze(url)` runs test, polls to completion, returns Core Web Vitals + Lighthouse + HAR summary
- [x] **Phase 3: Location and Test Parameters** - Location selection and in-memory location cache enable geographic test targeting (completed 2026-03-05)

## Phase Details

### Phase 1: Server Foundation
**Goal**: Claude Code can connect to the MCP server and check GTMetrix account status
**Depends on**: Nothing (first phase)
**Requirements**: SERV-01, SERV-02, SERV-03, SERV-04, SERV-05, SERV-06, ACCT-01
**Success Criteria** (what must be TRUE):
  1. Claude Code connects to the server via stdio transport and lists available tools
  2. `gtmetrix_check_status()` returns account credits, account type, and refill date from the live GTMetrix API
  3. API key is loaded from `.env` and never hardcoded anywhere
  4. All errors from the GTMetrix API surface as structured tool results with actionable hints, not uncaught exceptions
  5. No output appears on stdout except MCP protocol messages — all logging goes to stderr
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffold: install deps, .gitignore/.env.example, test infrastructure
- [x] 01-02-PLAN.md — Config + parsers: config.py (pydantic-settings) and client/parsers.py (unwrap_jsonapi)
- [ ] 01-03-PLAN.md — GTMetrixClient: shared httpx.AsyncClient with auth, headers, get_status()
- [ ] 01-04-PLAN.md — MCP wiring: gtmetrix_check_status tool, main.py FastMCP server, final validation

### Phase 2: Core Analyze Workflow
**Goal**: A single tool call scans a URL and returns all the performance data Claude needs to suggest code-level fixes
**Depends on**: Phase 1
**Requirements**: TEST-01, TEST-02, TEST-03, REPT-01, REPT-02, REPT-03, REPT-04
**Success Criteria** (what must be TRUE):
  1. `gtmetrix_analyze(url)` returns a single structured response without requiring multiple tool calls
  2. Response includes Core Web Vitals (LCP, TBT, CLS, performance score, structure score)
  3. Response includes only failing Lighthouse audits (score < 1) with title, description, and displayValue
  4. Response includes the 10 slowest/largest resources with URL, size, and duration
  5. Polling stops automatically at completion or after the hard timeout, and never hangs the server
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Client methods (start_test, get_test, get_report, get_resource) and parser functions (extract_vitals, filter_failing_audits, extract_top_resources)
- [ ] 02-02-PLAN.md — Analyze orchestrator (_analyze_impl with polling/timeout/error handling) and MCP wiring

### Phase 3: Location and Test Parameters
**Goal**: Tests can target specific geographic locations, making GTMetrix results reflect real-world CDN performance
**Depends on**: Phase 2
**Requirements**: TEST-04, TEST-05
**Success Criteria** (what must be TRUE):
  1. `gtmetrix_analyze(url, location=...)` accepts a location identifier and runs the test from that region
  2. Valid location IDs are fetched from the GTMetrix API and cached in memory so repeated calls do not re-fetch them
  3. Passing an invalid location returns a structured error listing available locations, not a crash
**Plans**: 2 plans

Plans:
- [ ] 03-01-PLAN.md — JSON:API list parser, list_locations() client method with cache, start_test location parameter
- [ ] 03-02-PLAN.md — Location validation in _analyze_impl, gtmetrix_list_locations tool, MCP wiring verification

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Server Foundation | 4/4 | Complete   | 2026-03-04 |
| 2. Core Analyze Workflow | 1/2 | In Progress|  |
| 3. Location and Test Parameters | 2/2 | Complete   | 2026-03-05 |
