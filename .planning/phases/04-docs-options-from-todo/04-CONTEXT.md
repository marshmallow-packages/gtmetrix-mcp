# Phase 4: Docs & options from todo - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Commit the existing README, create a CHANGELOG.md backfilling v1.0, add test parameter options (adblock, browser, device) to `gtmetrix_analyze` with configurable defaults via env vars, and update README with reference tables and new parameter documentation.

</domain>

<decisions>
## Implementation Decisions

### Device naming
- Three simple category names: phone, tablet, desktop
- These map to specific GTMetrix device IDs internally
- If value doesn't match phone/tablet/desktop, pass it through as a raw GTMetrix device ID (power user escape hatch)
- Configurable default via `GTMETRIX_DEFAULT_DEVICE` env var; if unset, don't send device param

### Default strategy
- All params (location, adblock, browser, device) follow the same pattern: optional `GTMETRIX_DEFAULT_X` env var
- If env var is unset, don't send the param (let GTMetrix use its own defaults)
- Explicit tool param overrides env default (tool param > env var > no value)
- PRO requirements documented in tool description/docstring only — no runtime PRO checks, let API enforce
- Adblock: configurable only, no implicit default either way

### Changelog format
- Keep a Changelog format (keepachangelog.com)
- Backfill all 3 completed phases as a single v1.0 entry
- Tool-level detail per entry (e.g. "Added gtmetrix_analyze tool")

### README updates
- Reference tables (locations, browsers, devices) inline in README under a Reference section
- PRO features marked with inline (PRO) tag in tables
- Tool table updated to show new params in signature
- .env.example updated with new default env vars as commented-out lines

### Claude's Discretion
- Whether device mapping is hardcoded or fetched from API (depends on GTMetrix API structure)
- Exact device ID mappings for phone/tablet/desktop categories
- Changelog entry wording and grouping within the v1.0 section
- Reference table format details (column widths, sorting)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config.py`: pydantic-settings BaseSettings with `extra="ignore"` — add new Optional[str] fields for defaults
- `client/gtmetrix.py`: `start_test()` already accepts `location` kwarg — extend with `browser`, `device`, `adblock` kwargs
- `tools/analyze.py`: `_analyze_impl()` already handles location param — extend signature and pass through
- `client/parsers.py`: `unwrap_jsonapi_list()` available if browser/device lists need API fetching
- Location validation pattern in `_analyze_impl()` — reusable for device/browser validation

### Established Patterns
- Optional params use `str | None = None` type hints with keyword-only args
- Config fields are simple types loaded from `.env` via pydantic-settings
- Tool registration via `register(mcp)` function with `_impl()` for testability
- Structured error dicts with `error` + `hint` keys
- `_locations_cache` pattern for in-memory caching of API data

### Integration Points
- `config.py` Settings class — new fields for GTMETRIX_DEFAULT_LOCATION, _DEVICE, _BROWSER, _ADBLOCK
- `client/gtmetrix.py` start_test() — new kwargs added to attributes dict
- `tools/analyze.py` _analyze_impl() — new params, default resolution from config
- `tools/analyze.py` register() — update MCP tool signatures and docstrings
- `.env.example` — new commented-out lines
- `README.md` — tools table, reference section, env var docs

</code_context>

<specifics>
## Specific Ideas

- Device names should be dead simple: "phone", "tablet", "desktop" — not brand names
- Reference tables should use the same format: ID | Name columns (as described in the todo)
- The README already exists with tools table, install instructions, example response — extend it, don't rewrite
- Overlaps with deferred v2 requirements OPTS-01 (throttle), OPTS-02 (device), OPTS-03 (audit filter) — this phase covers device/browser/adblock but NOT throttle or audit filter

</specifics>

<deferred>
## Deferred Ideas

- Connection throttle presets (3G, 4G, broadband) — OPTS-01, keep for v2
- Lighthouse audit category filter — OPTS-03, keep for v2
- Granular tools (separate lighthouse/HAR endpoints) — GRAN-01, GRAN-02, keep for v2

</deferred>

---

*Phase: 04-docs-options-from-todo*
*Context gathered: 2026-03-05*
