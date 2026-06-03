import pytest
from pydantic import ValidationError


def test_reproduction_result_valid():
    from ascend_agent.diagnosis.models import ReproductionResult

    r = ReproductionResult(
        status="success",
        command="python -m pytest tests/",
        stdout="2 passed",
        stderr="",
        exit_code=0,
        duration_seconds=1.5,
        hypothesis_id_tested=0,
        files_changed=[],
    )
    assert r.status == "success"
    assert r.exit_code == 0
    assert r.duration_seconds == 1.5


def test_reproduction_result_invalid_status():
    from ascend_agent.diagnosis.models import ReproductionResult

    with pytest.raises(ValidationError):
        ReproductionResult(
            status="invalid_status",
            command="echo test",
            stdout="",
            stderr="",
            exit_code=0,
            duration_seconds=0.0,
            hypothesis_id_tested=0,
        )


def test_reproduction_result_forbids_extra():
    from ascend_agent.diagnosis.models import ReproductionResult

    with pytest.raises(ValidationError):
        ReproductionResult(
            status="success",
            command="echo test",
            stdout="",
            stderr="",
            exit_code=0,
            duration_seconds=0.0,
            hypothesis_id_tested=0,
            extra_field="should fail",
        )


def test_reproduction_result_defaults():
    from ascend_agent.diagnosis.models import ReproductionResult

    r = ReproductionResult(
        status="success",
        command="echo test",
        duration_seconds=0.0,
        hypothesis_id_tested=0,
    )
    assert r.stdout == ""
    assert r.stderr == ""
    assert r.exit_code == -1
    assert r.files_changed == []
    assert r.reproduced is False
    assert r.repro_file == ""
    assert r.matched_error is False
    assert r.matched_error_signal == ""
    assert r.attempts == []


def test_reproduction_attempt_valid():
    from ascend_agent.diagnosis.models import ReproductionAttempt

    attempt = ReproductionAttempt(
        kind="generated_bad_case",
        command="python -m pytest .ascend-agent/repros/test_repro_h0.py",
        repro_file=".ascend-agent/repros/test_repro_h0.py",
        status="success",
        exit_code=0,
        matched_error=True,
        matched_signal="ValueError: boom",
        summary="Generated bad case verified the reproduction",
    )
    assert attempt.matched_error is True
    assert attempt.repro_file.endswith(".py")


def test_reproduction_result_duration_negative_rejected():
    from ascend_agent.diagnosis.models import ReproductionResult

    with pytest.raises(ValidationError):
        ReproductionResult(
            status="success",
            command="echo test",
            duration_seconds=-0.1,
            hypothesis_id_tested=0,
        )


def test_reproduction_result_hypothesis_id_negative_one():
    from ascend_agent.diagnosis.models import ReproductionResult

    r = ReproductionResult(
        status="success",
        command="echo test",
        duration_seconds=0.0,
        hypothesis_id_tested=-1,
    )
    assert r.hypothesis_id_tested == -1
