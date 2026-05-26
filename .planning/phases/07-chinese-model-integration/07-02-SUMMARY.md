---
phase: 07-chinese-model-integration
plan: 02
subsystem: provider-routing
tags: structured-output, parse-fallback, json-loads, modelrouter

# Dependency graph
requires:
  - phase: 07-chinese-model-integration
    provides: PROVIDER_DEFAULTS dict, DeepSeek/Qwen provider configs
provides:
  - ModelRouter.completion() transparent fallback from .parse() to json.loads on 400 errors
  - Non-400 error propagation (auth, rate-limit, server errors pass through)
  - Empty content handling (raises ValueError with clear message)
affects: [all provider phases — the fallback is provider-agnostic]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Try .parse() first → catch 400 → fall back to .create() + model_validate_json()"
    - "Non-400 errors propagate unchanged (don't mask auth/rate-limit issues)"

key-files:
  created: []
  modified:
    - src/ascend_agent/diagnosis/router.py
    - tests/test_diagnosis/test_router.py

key-decisions:
  - "Only 400 errors trigger fallback — non-400 errors propagate"
  - "Empty content after fallback raises ValueError with model name in message"
  - "Fallback uses model_validate_json() for Pydantic validation of raw JSON content"

requirements-completed: [CHN-04]

# Metrics
duration: 8 min
completed: 2026-05-26
---

# Phase 7 Plan 02: Structured Output Fallback Summary

**ModelRouter.completion() transparent fallback from .parse() to json.loads when provider returns 400, with 3 new tests**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-26T08:04:11Z
- **Completed:** 2026-05-26T08:12:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- ModelRouter.completion() catches APIStatusError and BadRequestError with status 400
- Falls back to chat.completions.create() + model_validate_json() for manual JSON parsing
- Non-400 errors (401, 429, 500) propagate unchanged — no silent swallowing
- Empty response content raises ValueError with model name for debugging
- 3 new tests: fallback success path, non-400 passthrough, empty content handling

## Task Commits

Each task was committed atomically:

1. **Task 1: Add structured output fallback to ModelRouter.completion()** - `875b1df` (feat)

**Plan metadata:**

## Files Created/Modified
- `src/ascend_agent/diagnosis/router.py` - Added APIStatusError/BadRequestError imports, try/except fallback in completion(), empty content ValueError
- `tests/test_diagnosis/test_router.py` - Added 3 tests: fallback on 400, non-400 passthrough, empty content error

## Decisions Made
- Only 400 errors trigger fallback — other errors propagate naturally
- Fallback path uses model_validate_json() for Pydantic validation (not raw json.loads)
- Logging at WARNING level for audibility when fallback triggers

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None.

## Next Phase Readiness
- Chinese model integration complete — both DeepSeek and Qwen fully supported
- All providers with partial .parse() support now work transparently via fallback
- Phase 8 (Multi-Repo Support) can proceed, or Phase 9 (Testing) for full test coverage

---
*Phase: 07-chinese-model-integration*
*Completed: 2026-05-26*
