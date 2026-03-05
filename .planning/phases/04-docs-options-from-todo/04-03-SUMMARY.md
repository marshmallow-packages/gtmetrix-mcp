---
phase: 04-docs-options-from-todo
plan: 03
subsystem: api
tags: [config, pydantic-settings, env-vars, location]

requires:
  - phase: 04-01
    provides: config default resolution pattern for browser/device/adblock
  - phase: 04-02
    provides: .env.example and README documenting GTMETRIX_DEFAULT_LOCATION
provides:
  - Working GTMETRIX_DEFAULT_LOCATION env var with config field and default resolution
affects: []

tech-stack:
  added: []
  patterns: [env-var-backed config default with explicit-param override]

key-files:
  created: []
  modified: [config.py, tools/analyze.py, tests/test_analyze.py]

key-decisions:
  - "Moved config resolution before location validation so default location also gets validated"
  - "Used valid mock location IDs in tests to avoid false validation errors"

patterns-established:
  - "Default resolution pattern: effective_X = param if param is not None else cfg.gtmetrix_default_X"

requirements-completed: [TODO-DEFAULTS, TODO-ENVEXAMPLE]

duration: 2min
completed: 2026-03-05
---

# Phase 04 Plan 03: Default Location Gap Closure Summary

**GTMETRIX_DEFAULT_LOCATION env var backed by config field with fallback resolution in _analyze_impl**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-05T11:42:08Z
- **Completed:** 2026-03-05T11:44:20Z
- **Tasks:** 1 (TDD: 2 commits)
- **Files modified:** 3

## Accomplishments
- Added `gtmetrix_default_location` field to Settings class in config.py
- Added `effective_location` default resolution in _analyze_impl matching existing browser/device/adblock pattern
- Moved config resolution before location validation so env-var defaults also get validated
- Added 3 tests: default from config, explicit override, and no-default-no-param

## Task Commits

Each task was committed atomically:

1. **Task 1: Add gtmetrix_default_location to config and _analyze_impl** (TDD)
   - `ef5751e` (test: add failing tests for default location)
   - `9ad32d6` (feat: implement GTMETRIX_DEFAULT_LOCATION env var support)

## Files Created/Modified
- `config.py` - Added gtmetrix_default_location: str | None = None field
- `tools/analyze.py` - Added effective_location resolution, moved config import before validation, use effective_location in validation and start_test
- `tests/test_analyze.py` - Added gtmetrix_default_location to _mock_config defaults, added 3 location default tests

## Decisions Made
- Moved config resolution block before location validation so that default locations from config also get validated against available locations (prevents invalid defaults from silently failing)
- Used valid mock location IDs ("2" and "1") in tests instead of non-existent IDs to test the default resolution path without triggering validation errors

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test location IDs to use valid mock data**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** Plan specified location="7" in tests, but mock locations only have IDs "1", "2", "5". Tests failed with validation error instead of testing default resolution.
- **Fix:** Changed test default location from "7" to "2" and explicit override from "3" to "1" (both valid mock location IDs)
- **Files modified:** tests/test_analyze.py
- **Verification:** All 8 location tests pass
- **Committed in:** 9ad32d6

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary correction. Plan's test data was incompatible with existing mock fixtures. No scope creep.

## Issues Encountered
None beyond the test data fix documented above.

## User Setup Required
None - no external service configuration required. Users who already have GTMETRIX_DEFAULT_LOCATION in their .env (as documented in 04-02) will now have it work automatically.

## Next Phase Readiness
- Gap 1 from 04-VERIFICATION.md is now closed
- All documented env vars have backing implementation
- Ready for 04-04 (todo file cleanup) or further gap closure

---
*Phase: 04-docs-options-from-todo*
*Completed: 2026-03-05*

## Self-Check: PASSED
