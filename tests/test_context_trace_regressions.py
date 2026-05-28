from pathlib import Path

from ascend_agent.context.trace import parse_stack_trace


FIXTURES = Path(__file__).parent / "fixtures" / "traces"


def _trace(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_chained_exception_prefers_final_exception():
    result = parse_stack_trace(_trace("python_chained_exception.log"))

    assert result.error_type == "RuntimeError"
    assert result.error_message == "invalid worker count"
    assert result.frames[-1].file == "/repo/app.py"
    assert result.frames[-1].line == 12
    assert [cause.error_type for cause in result.causes] == ["ValueError"]


def test_pytest_failure_extracts_failed_test_metadata():
    result = parse_stack_trace(_trace("pytest_assertion_failure.log"))

    assert result.error_type == "AssertionError"
    assert result.error_message == "assert 1 == 2"
    assert result.frames
    assert result.frames[0].file == "tests/test_shapes.py"
    assert result.frames[0].function == "test_normalize_shape"


def test_ascend_acl_error_extracts_runtime_signals():
    result = parse_stack_trace(_trace("ascend_acl_error.log"))

    assert result.error_type == "RuntimeError"
    assert result.error_message == "call aclrtSynchronize failed, error code is 507011"
    assert result.runtime_signals["error_code"] == "507011"
    assert result.runtime_signals["rank_id"] == "7"
    assert result.runtime_signals["device_id"] == "3"


def test_exception_group_preserves_nested_causes():
    result = parse_stack_trace(_trace("exception_group.log"))

    assert result.error_type == "ExceptionGroup"
    assert result.error_message == "worker failures (2 sub-exceptions)"
    assert [cause.error_type for cause in result.causes] == ["ValueError", "RuntimeError"]
