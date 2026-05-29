# Phase 3 Evidence Validation

Date: 2026-05-28

## Scope

Phase 3 adds local validation for LLM-produced diagnosis evidence before a
`DiagnosisResult` is returned to callers.

## Implemented

- Validates every hypothesis evidence item against the repository.
- Rejects evidence when:
  - the file cannot be resolved inside the repository,
  - the line number is outside the file,
  - the cited snippet cannot be found in the file.
- Supports line-number-prefixed snippets such as `3:    raise ValueError(...)`
  when comparing against source.
- Drops hypotheses with no valid evidence.
- Records validation failures as `PartialFailure(stage="evidence_validation")`.

## Verification

Phase 3 target tests:

```text
python -m pytest tests/test_diagnosis/test_evidence_validation_baseline.py \
  tests/test_diagnosis/test_engine.py -q

15 passed
```

Phase 0-3 target suite:

```text
python -m pytest tests/test_context.py tests/test_context_trace_regressions.py \
  tests/test_diagnosis/test_engine.py \
  tests/test_diagnosis/test_evidence_validation_baseline.py \
  tests/test_diagnosis/test_router.py tests/test_tools/test_code_search.py -q

50 passed
```

Full suite baseline:

```text
python -m pytest -q

127 passed, 10 failed
```

The 10 failures are the same non-diagnosis reproduction/verification/tooling
baseline issues recorded during Phase 0.
