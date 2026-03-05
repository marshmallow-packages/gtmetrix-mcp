---
phase: 03-location-and-test-parameters
plan: 01
subsystem: api
tags: [jsonapi, parser, caching, gtmetrix, locations]

# Dependency graph
requires:
  - phase: 01-server-foundation
    provides: GTMetrixClient base class and unwrap_jsonapi parser
  - phase: 02-core-analyze-workflow
    provides: start_test method and test lifecycle
provides:
  - unwrap_jsonapi_list parser for JSON:API list responses
  - list_locations() client method with in-memory cache
  - start_test() location parameter support
  - MOCK_LOCATIONS_RESPONSE test fixture
affects: [03-02-location-validation-and-tool-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns: [in-memory-cache-with-none-sentinel]

key-files:
  created: []
  modified:
    - client/parsers.py
    - client/gtmetrix.py
    - tests/conftest.py
    - tests/test_parsers.py
    - tests/test_client.py

key-decisions:
  - "Cache uses None sentinel (not empty list) to distinguish uncached from empty"

patterns-established:
  - "In-memory cache pattern: None sentinel, check before HTTP call, store on first fetch"

requirements-completed: [TEST-05]

# Metrics
duration: 2min
completed: 2026-03-05
---

# Phase 3 Plan 1: Locations Parser and Client Cache Summary

**JSON:API list parser with list_locations() in-memory caching and optional location parameter on start_test()**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-05T10:07:30Z
- **Completed:** 2026-03-05T10:09:25Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 5

## Accomplishments
- unwrap_jsonapi_list() flattens JSON:API list responses into flat dicts with id, type, and attributes
- list_locations() fetches GET /locations and returns cached data on subsequent calls (single HTTP request)
- start_test() extended with optional location keyword parameter
- Full test coverage: 7 new tests, 52 total passing with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `4c380b1` (test)
2. **Task 1 GREEN: Implementation** - `15be4e8` (feat)

## Files Created/Modified
- `client/parsers.py` - Added unwrap_jsonapi_list() for JSON:API list responses
- `client/gtmetrix.py` - Added list_locations() with cache, extended start_test() with location param
- `tests/conftest.py` - Added MOCK_LOCATIONS_RESPONSE fixture (3 locations including inaccessible Mumbai)
- `tests/test_parsers.py` - Added TestUnwrapJsonapiList class with 3 tests
- `tests/test_client.py` - Added 4 tests for list_locations and start_test location param

## Decisions Made
- Cache uses None sentinel (not empty list) to distinguish "not yet fetched" from "API returned no locations"

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- unwrap_jsonapi_list and list_locations ready for Plan 02's location validation
- MOCK_LOCATIONS_RESPONSE includes inaccessible location (Mumbai) for validation filtering tests
- start_test location param ready for tool wiring

---
*Phase: 03-location-and-test-parameters*
*Completed: 2026-03-05*
