---
phase: 02-diagnosis-engine
plan: 01
subsystem: diagnosis
tags:
  - openai
  - pydantic
  - llm-router
  - structured-outputs

# Dependency graph
requires:
  - phase: 01-architecture-foundation
    provides: ContextDocument, ConfigDict(extra="forbid") pattern, pytest conventions
provides:
  - Pydantic v2 models: Hypothesis, Evidence, SearchAction, SearchDecision, PartialFailure, DiagnosisResult
  - ModelRouter — thin OpenAI client wrapper with completion() using .parse()
  - Wave 0 test infrastructure — 10 passing tests
affects:
  - 02-02-engine-core
  - 02-03-cli-integration

# Tech tracking
tech-stack:
  added:
    - openai>=2.37.0
  patterns:
    - ConfigDict(extra="forbid") on all Pydantic v2 models
    - ModelRouter as thin wrapper around OpenAI client
    - structured outputs via client.chat.completions.parse()

key-files:
  created:
    - src/ascend_agent/diagnosis/__init__.py
    - src/ascend_agent/diagnosis/models.py
    - src/ascend_agent/diagnosis/router.py
    - tests/test_diagnosis/__init__.py
    - tests/test_diagnosis/conftest.py
    - tests/test_diagnosis/test_models.py
    - tests/test_diagnosis/test_router.py
  modified:
    - pyproject.toml

key-decisions:
  - "All Pydantic models use ConfigDict(extra='forbid') to prevent schema drift from LLM output"
  - "ModelRouter is a concrete class, not Protocol-based — Protocol layer deferred to future multi-provider need"
  - "openai .parse() with response_format used for structured outputs (not manual JSON parsing)"
  - "GitHub git 0 files — all tests use inline imports (monkeypatch, no conftest needed for router tests)"

requirements-completed:
  - DIAG-01

# Metrics
duration: 6 min
completed: 2026-05-21
---

# Phase 2 Plan 1: Diagnosis Foundation Summary

**Pydantic v2 data contracts (Hypothesis, Evidence, SearchDecision, DiagnosisResult) and ModelRouter LLM wrapper with Wave 0 test infrastructure — all with ConfigDict(extra="forbid") enforcement**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-21T03:43:03Z
- **Completed:** 2026-05-21T03:49:09Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- 6 Pydantic v2 models created: Evidence, Hypothesis, SearchAction, SearchDecision, PartialFailure, DiagnosisResult — all with `ConfigDict(extra="forbid")` and precise field constraints (confidence 0-1, iterations 0-3, line_number ≥1, action regex validation)
- ModelRouter class with API key validation on construction (raises `ValueError` with clear message if `OPENAI_API_KEY` is missing), model config via env var `ASCEND_DIAGNOSIS_MODEL` (default `gpt-4o`), and `completion()` method using OpenAI `.parse()` for structured outputs
- `openai>=2.37.0` dependency added to `pyproject.toml` and installed
- All 10 Wave 0 tests passing — schema validation boundaries for models, initialization/validation for router

## Task Commits

Each task was committed atomically:

1. **Task 1: Create diagnosis package and Pydantic models** - `7e64d89` (feat)
2. **Task 2: Create ModelRouter abstraction** - `233ce75` (feat)
3. **Task 3: Create Wave 0 test infrastructure** - `1045ea6` (test)
4. **Export all models from diagnosis package** - `06b8832` (feat — Rule 2 fix)

**Plan metadata:** *(committed below)*

## Files Created/Modified

- `pyproject.toml` - Added `openai>=2.37.0` dependency
- `src/ascend_agent/diagnosis/__init__.py` - Package init, exports all 6 model classes and ModelRouter
- `src/ascend_agent/diagnosis/models.py` - 6 Pydantic v2 models with ConfigDict(extra="forbid")
- `src/ascend_agent/diagnosis/router.py` - ModelRouter wrapping OpenAI client with completion().parse()
- `tests/test_diagnosis/__init__.py` - Package init for diagnosis test discovery
- `tests/test_diagnosis/conftest.py` - Shared fixtures: sample_trace, sample_repo_dir, mock_openai_response
- `tests/test_diagnosis/test_models.py` - 6 schema validation tests
- `tests/test_diagnosis/test_router.py` - 4 ModelRouter initialization/validation tests

## Decisions Made

- All Pydantic models use `ConfigDict(extra="forbid")` — critical for LLM output validation, prevents unexpected fields from flowing into the system
- ModelRouter is a concrete class (not Protocol-based) — Protocol abstraction deferred to future multi-provider need per PLAN.md direction
- `openai .parse()` with Pydantic `response_format` used for structured outputs — pattern established in RESEARCH.md
- Uses `api_key` from constructor param or `OPENAI_API_KEY` env var, never logs the key — only logs model name per T-2-01 threat mitigation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `default=0` to DiagnosisResult.iterations_used**
- **Found during:** Task 1 (acceptance criteria verification)
- **Issue:** `iterations_used` field had no default value, making `DiagnosisResult()` fail with "Field required" — but the test in Task 3 expects `DiagnosisResult()` to initialize with `iterations_used=0`
- **Fix:** Added `default=0` to the Field definition
- **Files modified:** `src/ascend_agent/diagnosis/models.py`
- **Verification:** `DiagnosisResult().iterations_used == 0` now works
- **Committed in:** `7e64d89` (in Task 1 commit)

**2. [Rule 2 - Missing Critical] Exported all model classes from `__init__.py`**
- **Found during:** Plan-level verification (`from ascend_agent.diagnosis import Hypothesis, Evidence`)
- **Issue:** Only `ModelRouter` was exported per PLAN.md instruction, but plan-level verification test expects all models to be importable from the package
- **Fix:** Added imports and `__all__` entries for all 6 model classes
- **Files modified:** `src/ascend_agent/diagnosis/__init__.py`
- **Verification:** `python -c "from ascend_agent.diagnosis import ModelRouter, Hypothesis, Evidence; print('Foundation OK')"` exits 0
- **Committed in:** `06b8832`

---

**Total deviations:** 2 auto-fixed (both Rule 2 — missing critical functionality)
**Impact on plan:** Both fixes essential for correctness (default value) and planned verification (package exports). No scope creep.

## Issues Encountered

None — all tasks executed cleanly.

## User Setup Required

None — no external service configuration required. Set `OPENAI_API_KEY` environment variable when running the diagnosis engine.

## Next Phase Readiness

- Foundation data models and LLM abstraction complete
- Ready for Plan 02-02 (Engine Core) — the Engine class will depend on these types and the ModelRouter
- 10 passing tests validate the schema contracts

---

## Self-Check: PASSED

- All created files confirmed on disk (7/7)
- All 4 commits found in git log
- `pytest tests/test_diagnosis/ -x -q` — 10 passed

---

*Phase: 02-diagnosis-engine*
*Completed: 2026-05-21*
