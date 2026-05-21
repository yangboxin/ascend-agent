---
phase: 02-diagnosis-engine
plan: 02
subsystem: diagnosis
tags: ["engine", "llm", "ast", "search-loop", "structured-output", "openai"]

# Dependency graph
requires:
  - phase: 02-diagnosis-engine
    plan: 01
    provides: Diagnosis models (Hypothesis, Evidence, DiagnosisResult, SearchDecision),
              ModelRouter abstraction for LLM calls
provides:
  - Engine class with LLM-driven search loop (max 3 iterations)
  - _read_function_body utility (AST-based function boundary detection)
  - Module-level prompt builders for system and user messages
  - Search history formatter for LLM context
  - 11 unit tests for engine and function body extraction
affects:
  - Phase 3 (Fix Generation) — consumes DiagnosisResult from Engine.diagnose()
  - Phase 2 Plan 03 — wires Engine into CLI diagnose command

# Tech tracking
tech-stack:
  added: []
  patterns:
    - LLM-driven search loop with SearchDecision structured output routing
    - AST-based function boundary detection with line-based fallback
    - Engine catches all exceptions from search_code — never crashes on search failure
    - _read_function_body returns None for non-existent files, never raises
    - Prompts built at module level, not as Engine methods

key-files:
  created:
    - src/ascend_agent/diagnosis/engine.py
    - tests/test_diagnosis/test_engine.py
  modified:
    - src/ascend_agent/diagnosis/__init__.py
    - tests/test_diagnosis/conftest.py

key-decisions:
  - "search_code imported locally inside _execute_search to avoid circular dependency"
  - "Engine._execute_search runs asyncio.run(search_code(...)) — synchronous call to async tool"
  - "System prompt explicitly states 'Do not ask clarifying questions' to enforce D-03"
  - "_read_function_body handles SyntaxError via fallback to line window"
  - "Test patches ascend_agent.tools.code_search.search_code directly (local import)"

requirements-completed:
  - DIAG-01
  - DIAG-02

# Metrics
duration: 30min
completed: 2026-05-21
---

# Phase 2 Plan 2: Engine & Search Loop Summary

**Engine class with 3-iteration LLM-driven diagnosis search loop, AST-based function body extraction utility, and 11 unit tests with mock-based coverage**

## Performance

- **Duration:** 30 min
- **Started:** 2026-05-21T03:52:49Z
- **Completed:** 2026-05-21T04:23:48Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `Engine` class with `diagnose()` method implementing up to 3 LLM-driven search iterations using `SearchDecision` structured output routing
- `_read_function_body()` utility using Python AST for precise function boundary detection with ±5 line context, line-based fallback, and None return for missing files
- Module-level prompt builders (`_build_system_prompt`, `_build_user_prompt`) with D-03 constraint "Do not ask clarifying questions"
- `_format_search_history()` helper formats accumulated search results for LLM context, truncates long results
- Engine silently handles search failures via `_execute_search` raising exceptions into error dict, never crashing
- 11 unit tests covering: function body AST extraction, fallback for non-function lines, non-existent file handling, constructor, search loop, partial failure, budget exhaustion, and silent mode

## Task Commits

Each task in the TDD cycle was committed atomically:

1. **RED: Test files** — `a250975` (test)
   - Created `test_engine.py` with 11 tests
   - Updated `conftest.py` with `sample_context_doc` and `mock_router` fixtures

2. **GREEN: Implementation** — `95f9b5c` (feat)
   - Implemented `engine.py` with `Engine` class and `_read_function_body` utility
   - Updated `__init__.py` to export `Engine` and `_read_function_body`

## Files Created/Modified

- `src/ascend_agent/diagnosis/engine.py` — **Created.** Engine class (diagnose, _generate_hypotheses, _execute_search, _enrich_with_function_bodies) and _read_function_body utility + module-level prompt builders
- `src/ascend_agent/diagnosis/__init__.py` — **Modified.** Added Engine and _read_function_body exports
- `tests/test_diagnosis/conftest.py` — **Modified.** Added sample_context_doc and mock_router fixtures
- `tests/test_diagnosis/test_engine.py` — **Created.** 11 tests covering engine search loop, partial failure, budget exhaustion, silent mode, and function body extraction edge cases

## Decisions Made

- **Local import for search_code:** `search_code` is imported locally inside `_execute_search()` to avoid circular dependencies between the diagnosis engine and tools layer
- **asyncio.run for async tool call:** Engine uses `asyncio.run(search_code(...))` to call the async `search_code` tool synchronously — avoids the complexity of making the entire Engine async
- **System prompt design:** The system prompt explicitly tells the LLM it has up to 3 searches, cannot ask clarifying questions, and must output "search" or "hypothesize" via structured output
- **Patch target for tests:** Tests patch `ascend_agent.tools.code_search.search_code` directly since it's imported locally in the engine module
- **Enrichment via parsed results:** `_enrich_with_function_bodies` parses `file:line:code` format from search results and appends AST-context snippets

## Deviations from Plan

None — plan executed exactly as written.

Total deviations: 0 auto-fixed
Impact on plan: None

## Issues Encountered

- Test patching required `ascend_agent.tools.code_search.search_code` as target instead of `ascend_agent.diagnosis.engine.search_code` due to local imports — fixed by updating patch targets in tests

## User Setup Required

None — no external service configuration required. OPENAI_API_KEY is validated by ModelRouter at runtime, not during Engine construction.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes at trust boundaries beyond what the plan defined. The threat model's mitigations are implemented:
- T-2-02: SearchDecision action field constrained to `r'^(search|hypothesize)$'` via Pydantic pattern
- T-2-03: All exceptions from search_code are caught and converted to error dicts — engine never crashes
- T-2-04: _read_function_body validates file existence via FileNotFoundError catch, returns None

## Next Phase Readiness

- Engine core is complete: `Engine.diagnose(context_doc)` takes ContextDocument, returns DiagnosisResult
- Ready for next plan (02-03): Wire Engine into the CLI `diagnose run` command for end-to-end diagnosis flow
- Test infrastructure is in place with mock router for unit tests — integration tests with real LLM will need OPENAI_API_KEY

---

*Phase: 02-diagnosis-engine*
*Completed: 2026-05-21*
