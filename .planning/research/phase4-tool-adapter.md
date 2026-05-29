# Phase 4 Tool Adapter

Date: 2026-05-29

## Scope

Phase 4 introduces a tool adapter seam in the diagnosis engine so MCP tool
integration can be added without rewriting diagnosis control flow.

## Implemented

- Added `search_tool` dependency injection to `Engine`.
- Added `SearchTool` callable type for async search tool contracts.
- Kept backward compatibility: when no `search_tool` is passed, `Engine`
  still uses `ascend_agent.tools.code_search.search_code`.
- Routed `_execute_search()` through `self._search_tool` instead of directly
  importing and calling `search_code`.

## Why This Matters

- Decouples diagnosis orchestration from a hardcoded local search function.
- Allows a future MCP client-backed search tool to be passed in directly.
- Keeps existing CLI behavior stable while enabling incremental migration.

## Verification

Phase 4 target tests:

```text
python -m pytest tests/test_diagnosis/test_engine.py \
  tests/test_diagnosis/test_evidence_validation_baseline.py \
  tests/test_tools/test_code_search.py \
  tests/test_context_trace_regressions.py -q

24 passed
```

Phase 0-4 target suite:

```text
python -m pytest tests/test_context.py tests/test_context_trace_regressions.py \
  tests/test_diagnosis/test_engine.py \
  tests/test_diagnosis/test_evidence_validation_baseline.py \
  tests/test_diagnosis/test_router.py tests/test_tools/test_code_search.py -q

51 passed
```
