---
phase: 03-fix-generation
plan: 01
subsystem: diagnosis
tags: pydantic, fix-generation, models, engine, unittest

requires: []
provides:
  - FixSuggestion, FixGenerationResult, FixResponse, Replacement, DiagnosisOutput models
  - FixEngine class for generating diffs from diagnosis hypotheses
  - Updated __init__.py exports for new models and FixEngine
  - Updated diagnose.py --output wrapper for DiagnosisOutput
  - 15 unit tests for models and FixEngine

affects:
  - 03-02 (fix CLI)
  - 03-03 (file_edit tool)
  - Phase 4 (verification)

tech-stack:
  added: []
  patterns:
    - FixEngine follows Engine pattern from Phase 2 (router + repo_path constructor, try/except error handling with PartialFailure)
    - LLM outputs search-and-replace operations, FixEngine computes unified diff via difflib.unified_diff()
    - Forward reference for ContextDocument resolved via model_rebuild() with deferred import

key-files:
  created:
    - src/ascend_agent/diagnosis/fix_engine.py
    - tests/test_diagnosis/test_fix_engine.py
  modified:
    - src/ascend_agent/diagnosis/models.py
    - src/ascend_agent/diagnosis/__init__.py
    - src/ascend_agent/cli/diagnose.py

key-decisions:
  - "DiagnosisOutput uses forward reference string for ContextDocument with model_rebuild() to avoid circular imports"
  - "LLM exceptions in _generate_for_hypothesis propagate to generate_fixes which records PartialFailure (matching engine.py pattern)"

requirements-completed: [FIX-01]

duration: 12 min
completed: 2026-05-21
---

# Phase 3 Fix Generation Plan 01: Fix Generation Models & Engine

**Pydantic foundation models (FixSuggestion, FixGenerationResult, FixResponse, Replacement, DiagnosisOutput) and FixEngine class with 15 passing unit tests**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-21T15:32:00Z
- **Completed:** 2026-05-21T15:44:00Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- **5 Pydantic models** added to `diagnosis/models.py`: Replacement, FixResponse, FixSuggestion, FixGenerationResult, and DiagnosisOutput — all using `ConfigDict(extra="forbid")` pattern
- **FixEngine class** in `diagnosis/fix_engine.py` — iterates all hypotheses (D-05), re-reads code via `_read_function_body` (D-06), single-shot per hypothesis (D-08), validates LLM output, computes unified diffs via `difflib.unified_diff()`, handles errors with PartialFailure
- **Path traversal protection** in both `_read_code_context` and `_generate_for_hypothesis` — resolves paths and verifies they stay within repo boundary
- **diagnose.py --output** now wraps output in `DiagnosisOutput(context_doc=doc, diagnosis_result=result)`
- **15 unit tests** (7 model tests + 8 FixEngine class tests) covering constructors, iteration, error handling, malformed output, diff computation, code re-reading, and path traversal blocking

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Pydantic models, update __init__.py, update diagnose.py --output** - `f7219d0` (feat)
2. **Task 2: Implement FixEngine class** - `abcd04f` (feat)
3. **Task 3: Create FixEngine unit tests** - `3714238` (test)

**Plan metadata:** Will be committed in final step.

## Files Created/Modified

- `src/ascend_agent/diagnosis/models.py` - Added `from __future__ import annotations`, 5 new Pydantic models, `_rebuild_diagnosis_output()` for forward reference resolution
- `src/ascend_agent/diagnosis/__init__.py` - Added FixEngine, FixSuggestion, FixGenerationResult, FixResponse, Replacement, DiagnosisOutput to imports and `__all__`
- `src/ascend_agent/diagnosis/fix_engine.py` - New file: FixEngine class (308 lines) with `_FIX_SYSTEM_PROMPT`, `generate_fixes`, `_generate_for_hypothesis`, `_read_code_context`, and `_build_fix_user_prompt` helper
- `src/ascend_agent/cli/diagnose.py` - Wrapped --output in DiagnosisOutput(context_doc=doc, diagnosis_result=result)
- `tests/test_diagnosis/test_fix_engine.py` - New file: 15 tests across TestFixEngineModels and TestFixEngine classes

## Decisions Made

- **Forward reference strategy for DiagnosisOutput**: Used `from __future__ import annotations` with a string annotation `"ContextDocument"` and deferred `model_rebuild()` to resolve the reference at runtime — avoids circular imports between diagnosis and context modules.
- **LLM exception propagation**: `_generate_for_hypothesis` lets LLM exceptions propagate to `generate_fixes()` which wraps each hypothesis iteration in try/except and records PartialFailure — consistent with the engine.py error handling pattern.
- **Call site of `_read_function_body`**: Imported locally inside `_read_code_context` method (not at module level) to avoid circular imports with `ascend_agent.diagnosis.engine`.

## Deviations from Plan

**1. [Rule 3 - Blocking] Forward reference required model_rebuild()**
- **Found during:** Task 3 (test execution)
- **Issue:** `DiagnosisOutput.context_doc` uses `"ContextDocument"` forward reference with `from __future__ import annotations`. Pydantic v2 requires `model_rebuild()` to resolve the forward reference properly — without it, validation fails with `class-not-fully-defined`.
- **Fix:** Added `_rebuild_diagnosis_output()` function at bottom of models.py that imports ContextDocument and calls `DiagnosisOutput.model_rebuild()`. Deferred import avoids circular dependency.
- **Files modified:** `src/ascend_agent/diagnosis/models.py`
- **Verification:** All model imports succeed, all tests pass
- **Committed in:** `f7219d0` (Task 1 commit — models were part of that commit)

**2. [Rule 3 - Blocking] LLM exception handling in generate_fixes**
- **Found during:** Task 3 (test execution)
- **Issue:** `_generate_for_hypothesis` was catching LLM exceptions internally and returning None. The `generate_fixes()` method's try/except wraps `_generate_for_hypothesis`, so the PartialFailure was never recorded.
- **Fix:** Removed the try/except from `_generate_for_hypothesis` for the LLM call — exceptions propagate to `generate_fixes()` which handles them correctly.
- **Files modified:** `src/ascend_agent/diagnosis/fix_engine.py`
- **Verification:** `test_generate_fixes_handles_llm_failure` passes, errors list populated
- **Committed in:** `3714238` (Task 3 commit — fix was applied to source code during testing)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

- `pytest` required explicit patch target `ascend_agent.diagnosis.engine._read_function_body` instead of `ascend_agent.diagnosis.fix_engine._read_function_body` due to local import inside `_read_code_context` method
- Initial attempt to verify `from ascend_agent.diagnosis import FixEngine` during Task 1 failed because fix_engine.py didn't exist yet — resolved by creating a minimal stub, then replacing it in Task 2

## Next Phase Readiness

- Ready for Plan 03-02 (Fix CLI with review workflow)
- FixEngine is importable and generates FixGenerationResult
- diagnose.py --output now emits DiagnosisOutput wrapper consumed by fix CLI
- All 15 new tests + 6 existing model tests pass

---

*Phase: 03-fix-generation*
*Completed: 2026-05-21*
