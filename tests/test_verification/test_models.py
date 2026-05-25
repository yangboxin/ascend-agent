import pytest
from pydantic import ValidationError


def test_verification_result_valid():
    from ascend_agent.diagnosis.models import VerificationResult, TestDetail

    r = VerificationResult(
        status="pass",
        hypothesis_id_verified=0,
        command="pytest",
        summary="passed",
        duration_seconds=1.0,
        tests=[
            TestDetail(nodeid="tests/test_core.py::test_add", outcome="passed", duration=0.01),
        ],
    )
    assert r.status == "pass"
    assert r.passed == 1


def test_verification_result_invalid_status():
    from ascend_agent.diagnosis.models import VerificationResult

    with pytest.raises(ValidationError):
        VerificationResult(
            status="invalid_status",
            hypothesis_id_verified=0,
            command="pytest",
            summary="test",
            duration_seconds=0.0,
        )


def test_verification_result_forbids_extra():
    from ascend_agent.diagnosis.models import VerificationResult

    with pytest.raises(ValidationError):
        VerificationResult(
            status="pass",
            hypothesis_id_verified=0,
            command="pytest",
            summary="test",
            duration_seconds=0.0,
            extra_field="should fail",
        )


def test_verification_result_defaults():
    from ascend_agent.diagnosis.models import VerificationResult

    r = VerificationResult(
        status="no_tests",
        hypothesis_id_verified=0,
        command="",
        summary="No tests",
        duration_seconds=0.0,
    )
    assert r.tests_found == 0
    assert r.tests_run == 0
    assert r.passed == 0
    assert r.failed == 0
    assert r.errors == 0
    assert r.exit_code == -1
    assert r.files_tested == []
    assert r.stdout == ""


def test_verification_result_duration_negative_rejected():
    from ascend_agent.diagnosis.models import VerificationResult

    with pytest.raises(ValidationError):
        VerificationResult(
            status="pass",
            hypothesis_id_verified=0,
            command="pytest",
            summary="test",
            duration_seconds=-0.1,
        )


def test_test_detail_valid():
    from ascend_agent.diagnosis.models import TestDetail

    td = TestDetail(
        nodeid="tests/test_core.py::test_add",
        outcome="passed",
        duration=0.01,
        message=None,
    )
    assert td.nodeid == "tests/test_core.py::test_add"
    assert td.outcome == "passed"
    assert td.duration == 0.01
    assert td.message is None


def test_test_detail_forbids_extra():
    from ascend_agent.diagnosis.models import TestDetail

    with pytest.raises(ValidationError):
        TestDetail(
            nodeid="test",
            outcome="passed",
            extra_field="should fail",
        )
