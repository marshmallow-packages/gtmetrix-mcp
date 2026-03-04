# GTMetrix MCP Server

## What This Is

A local Claude Code MCP server (Python) that wraps the GTMetrix API v2.0, enabling Claude to scan websites for performance issues and surface actionable Lighthouse recommendations, Core Web Vitals, and network waterfall data — then help fix those issues directly in the codebase.

## Core Value

Scan a URL and get back structured performance data (scores, Lighthouse audit, HAR waterfall) that Claude can reason about and use to guide code-level fixes.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] MCP server that Claude Code can connect to via stdio transport
- [ ] Start a GTMetrix test for any URL
- [ ] Poll test status until completion
- [ ] Retrieve performance report with Core Web Vitals (LCP, TBT, CLS, performance score)
- [ ] Retrieve full Lighthouse audit JSON with specific recommendations
- [ ] Retrieve HAR waterfall data to identify slow resources
- [ ] Check API credit balance and account status
- [ ] Structured output that Claude can reason about for fix suggestions

### Out of Scope

- Screenshots/video filmstrip — not needed for code-level fixes
- Scheduled/recurring scans — on-demand only
- Client reporting/PDF generation — scanning own projects only
- Web UI or dashboard — MCP server consumed by Claude Code only
- Comparison/history tracking — single scan workflow

## Context

- GTMetrix API v2.0 with JSON:API format, HTTP Basic auth (API key as username)
- PRO account: 8 concurrent tests, higher rate limits (960 req/60s)
- Python 3.11 project, skeleton already exists with pyproject.toml
- .env file with API key already configured
- Server runs locally on macOS, stdio transport for Claude Code
- MCP Python SDK (`mcp`) available for building servers
- Test costs ~1 credit (Lighthouse), polling recommended at 3s intervals

## Constraints

- **Transport**: stdio (local MCP server, no HTTP needed)
- **Language**: Python 3.11 (already set up)
- **Auth**: API key from .env, HTTP Basic to GTMetrix
- **Rate limits**: 960 req/60s (PRO), 8 concurrent tests
- **API format**: JSON:API v1.1 — responses need parsing before returning to Claude

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python MCP SDK over raw stdio | Official SDK handles protocol, lets us focus on tools | — Pending |
| Lighthouse JSON over PageSpeed/YSlow | Most actionable recommendations, industry standard | — Pending |
| Polling over webhooks | Local server, simpler architecture, no public endpoint needed | — Pending |

---
*Last updated: 2026-03-04 after initialization*
