---
phase: 03-location-and-test-parameters
plan: 02
subsystem: api
tags: [location, validation, mcp-tool, gtmetrix]

# Dependency graph
requires:
  - phase: 03-location-and-test-parameters
    provides: list_locations() client method with cache, unwrap_jsonapi_list parser
  - phase: 02-core-analyze-workflow
    provides: _analyze_impl orchestrator, gtmetrix_analyze MCP tool
provides:
  - Location validation in _analyze_impl (validates against cached list)
  - _list_locations_impl helper returning accessible locations only
  - gtmetrix_list_locations MCP tool for location discovery
  - gtmetrix_analyze location parameter support
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [accessible-locations-filter]

key-files:
  created: []
  modified:
    - tools/analyze.py
    - tests/test_analyze.py

key-decisions:
  - "Location validation filters by account_has_access to show only usable locations in error messages"

patterns-established:
  - "Accessible-only filter pattern: filter locations by account_has_access before presenting to user"

requirements-completed: [TEST-04, TEST-05]

# Metrics
duration: 2min
completed: 2026-03-05
---

# Phase 3 Plan 2: Location Validation and Tool Wiring Summary

**Location parameter validation on analyze with accessible-only filtering and gtmetrix_list_locations discovery tool**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-05T10:11:28Z
- **Completed:** 2026-03-05T10:13:18Z
- **Tasks:** 2 (1 TDD + 1 verification)
- **Files modified:** 2

## Accomplishments
- _analyze_impl validates location against cached location list before starting test (no extra HTTP call)
- Invalid location returns structured error with only accessible locations (Mumbai filtered out)
- Integer location values coerced to string automatically
- gtmetrix_list_locations MCP tool returns accessible locations with id, name, region
- 57 total tests passing across all phases with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for location validation** - `c08bdd8` (test)
2. **Task 1 GREEN: Location validation and list_locations tool** - `d4fe139` (feat)

Task 2 required no code changes (main.py already wired from Phase 2).

## Files Created/Modified
- `tools/analyze.py` - Added location param to _analyze_impl, _list_locations_impl, gtmetrix_list_locations tool, location validation logic
- `tests/test_analyze.py` - Added 5 tests: location happy path, invalid location, string coercion, list_locations impl, list_locations error

## Decisions Made
- Location validation filters by account_has_access to show only usable locations in error messages

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 3 phases complete (8/8 plans executed)
- Full location support end-to-end: discover locations, validate, and target specific regions
- 57 tests passing across entire codebase

---
*Phase: 03-location-and-test-parameters*
*Completed: 2026-03-05*
