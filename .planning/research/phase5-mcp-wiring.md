# Phase 5 MCP Wiring

Date: 2026-05-29

## Scope

Phase 5 wires diagnosis runtime through a tool-client seam so the search tool
can be swapped from local implementation to MCP-backed implementation without
changing diagnosis orchestration.

## Implemented

- Added `diagnosis.tool_client`:
  - `DiagnosisToolClient` protocol
  - `LocalToolClient` implementation
  - `create_tool_client()` factory
- Updated diagnose CLI flow to:
  - create tool client,
  - pass `tool_client.search_code` into `Engine(search_tool=...)`.
- Updated diagnose CLI tests to keep monkeypatched `Engine` constructors
  compatible with the new keyword argument.

## Why This Matters

- Diagnosis engine is now runtime-injected with search behavior end-to-end from
  CLI entrypoint.
- Existing behavior stays unchanged (local search), while MCP client wiring can
  be introduced in the factory next.

## Verification

Target tests:

```text
python -m pytest tests/test_cli.py \
  tests/test_diagnosis/test_engine.py \
  tests/test_diagnosis/test_evidence_validation_baseline.py \
  tests/test_tools/test_code_search.py -q

34 passed
```

Phase 0-5 target suite:

```text
python -m pytest tests/test_context.py tests/test_context_trace_regressions.py \
  tests/test_diagnosis/test_engine.py \
  tests/test_diagnosis/test_evidence_validation_baseline.py \
  tests/test_diagnosis/test_router.py tests/test_tools/test_code_search.py \
  tests/test_cli.py -q

65 passed
```
