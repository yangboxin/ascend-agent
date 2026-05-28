# Phase 1 Trace Parser

Date: 2026-05-28

## Scope

Phase 1 upgrades trace/log parsing while preserving the existing `TraceInfo`
contract used by the CLI and diagnosis engine.

## Implemented

- Added compatible structured fields to `TraceInfo`:
  - `causes`
  - `runtime_signals`
  - `parse_warnings`
- Added `TraceCause` for nested/chained error summaries.
- Changed primary error selection:
  - Python chained exceptions now prefer the final raised exception.
  - Python 3.11 `ExceptionGroup` remains the primary error and nested errors
    are preserved in `causes`.
- Added pytest failure metadata extraction from `FAILED file.py::test_name`
  lines into `TraceEntry`.
- Added Ascend runtime signal extraction:
  - `error_code`
  - `rank_id`
  - `device_id`
- Tightened error-line parsing so source lines such as
  `raise RuntimeError(...)` are not treated as emitted errors.

## Verification

Trace and context tests:

```text
python -m pytest tests/test_context.py tests/test_context_trace_regressions.py -q

11 passed
```

Phase 0 target suite after Phase 1:

```text
python -m pytest tests/test_context.py tests/test_context_trace_regressions.py \
  tests/test_diagnosis/test_engine.py \
  tests/test_diagnosis/test_evidence_validation_baseline.py \
  tests/test_diagnosis/test_router.py -q

42 passed, 1 xfailed
```

The remaining `xfail` is evidence validation, which belongs to Phase 3.

Full suite baseline:

```text
python -m pytest -q

122 passed, 10 failed, 1 xfailed
```

The 10 failures are the same non-trace reproduction/verification/tooling
baseline issues recorded during Phase 0.
