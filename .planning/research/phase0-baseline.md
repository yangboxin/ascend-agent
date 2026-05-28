# Phase 0 Baseline

Date: 2026-05-28

## Scope

Phase 0 establishes regression coverage for known diagnosis weaknesses without
rewriting the diagnosis pipeline yet.

Covered areas:

- Trace parsing gaps for chained Python exceptions, pytest failures, Ascend
  runtime logs, and Python 3.11 `ExceptionGroup`.
- Evidence validation gap where LLM-produced evidence is accepted by schema
  shape only and is not checked against repository files.
- Provider routing test isolation so local `~/.config/ascend-agent/providers.json`
  does not make missing-key tests depend on a developer machine.

## Added Regression Fixtures

- `tests/fixtures/traces/python_chained_exception.log`
- `tests/fixtures/traces/pytest_assertion_failure.log`
- `tests/fixtures/traces/ascend_acl_error.log`
- `tests/fixtures/traces/exception_group.log`

## Added Baseline Tests

- `tests/test_context_trace_regressions.py`
- `tests/test_diagnosis/test_evidence_validation_baseline.py`

The new diagnosis-quality tests are marked `xfail(strict=True)` because they
document target behavior for later phases. They keep CI stable while making the
current limitations explicit.

## Verification

Targeted Phase 0 suite:

```text
python -m pytest tests/test_context.py tests/test_context_trace_regressions.py \
  tests/test_diagnosis/test_engine.py \
  tests/test_diagnosis/test_evidence_validation_baseline.py \
  tests/test_diagnosis/test_router.py -q

38 passed, 5 xfailed
```

Full suite baseline:

```text
python -m pytest -q

118 passed, 10 failed, 5 xfailed
```

Full-suite failures observed outside the new Phase 0 tests:

- `tests/test_reproduction/test_engine.py::TestReproductionEngine::test_engine_handles_exec_shell_failure`
  patches `ascend_agent.reproduction.engine.exec_shell`, but the implementation
  imports `exec_shell` inside the method, so the module attribute does not exist.
- `tests/test_reproduction/test_engine.py::TestReproductionEngine::test_detect_venv_conda`
  is sensitive to the active `VIRTUAL_ENV` from the developer shell.
- `tests/test_tools/test_server.py::test_mcp_server_lists_tools` expects
  `_tool_manager`, but the test environment uses a `_MockFastMCP` without that
  attribute.
- `tests/test_tools/test_shell_exec.py::test_exec_invalid_command` expects an
  invalid shell command to be `error`, while the shell path returns `fail`.
- `tests/test_verification/test_cli.py::{test_verify_run_with_fixture,test_verify_output_json}`
  exits with Typer code 2 in the current CLI invocation path.
- `tests/test_verification/test_engine.py::TestVerificationEngine::test_map_test_files_returns_empty`
  returns a candidate test path that does not exist.
- `tests/test_verification/test_engine.py::{test_verify_executes_via_exec_shell,test_verify_handles_exec_shell_exception}`
  have the same local-import patchability issue as reproduction.
- `tests/test_verification/test_models.py::test_verification_result_valid`
  expects `passed` to be derived from `tests`, but the model default remains `0`.

## Next Phase Inputs

Phase 1 should make the four trace `xfail` tests pass by introducing structured
trace/log parsing. Phase 3 should make the evidence-validation `xfail` pass by
validating LLM evidence against repository files before returning hypotheses.
