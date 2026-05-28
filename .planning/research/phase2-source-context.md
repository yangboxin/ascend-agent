# Phase 2 Source Context

Date: 2026-05-28

## Scope

Phase 2 improves context collection before the first LLM call. The diagnosis
engine now reads source referenced by stack frames instead of asking the model
to infer all search terms from a bare trace.

## Implemented

- Added trace-frame source collection in `diagnosis.engine`.
- Added path remapping for traces captured from a different checkout or
  container path. If an absolute frame path does not exist locally, the engine
  tries path suffixes under the current repository root.
- Added source snippets to the initial LLM message list under
  `Source Context From Stack Trace`.
- Limited automatic frame snippets to five unique frame locations to keep token
  usage bounded.
- Expanded `code_search` beyond Python files to include common configuration,
  shell, C/C++, CMake, and markdown files.

## Verification

Trace/source/search target tests:

```text
python -m pytest tests/test_diagnosis/test_engine.py \
  tests/test_tools/test_code_search.py tests/test_context.py \
  tests/test_context_trace_regressions.py -q

27 passed
```

Phase 0-2 target suite:

```text
python -m pytest tests/test_context.py tests/test_context_trace_regressions.py \
  tests/test_diagnosis/test_engine.py \
  tests/test_diagnosis/test_evidence_validation_baseline.py \
  tests/test_diagnosis/test_router.py tests/test_tools/test_code_search.py -q

47 passed, 1 xfailed
```

The remaining `xfail` is evidence validation, which belongs to Phase 3.

Full suite baseline:

```text
python -m pytest -q

124 passed, 10 failed, 1 xfailed
```

The 10 failures are the same non-trace reproduction/verification/tooling
baseline issues recorded during Phase 0.
