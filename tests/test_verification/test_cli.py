"""Integration tests for the verify CLI command."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ascend_agent.cli.app import app
from ascend_agent.cli.verify import verify_app
from ascend_agent.diagnosis.models import VerificationResult

runner = CliRunner()


def _make_pass_result():
    return VerificationResult(
        status="pass",
        hypothesis_id_verified=0,
        framework="pytest",
        command="pytest tests/test_core.py --json-report --json-report-file=none",
        summary="All tests passed",
        tests_found=1,
        tests_run=1,
        passed=1,
        failed=0,
        errors=0,
        skipped=0,
        xfailed=0,
        xpassed=0,
        tests=[],
        exit_code=0,
        duration_seconds=0.5,
        files_tested=["tests/test_core.py"],
        stdout="",
    )


def test_verify_help():
    """CLI registers and shows help text for verify subcommand."""
    result = runner.invoke(app, ["verify", "--help"])
    assert result.exit_code == 0
    assert "verify" in result.stdout or "Verify" in result.stdout


def test_verify_run_with_fixture(tmp_path):
    """CLI loads fixture, runs engine (mocked), produces output."""
    src_path = "tests/fixtures/sample_reproduction.json"
    fixture_path = tmp_path / "sample_reproduction.json"
    fixture_path.write_text(open(src_path).read())

    pass_result = _make_pass_result()

    with patch("ascend_agent.cli.verify.VerificationEngine") as MockEngine:
        mock_engine = MagicMock()
        mock_engine.verify.return_value = pass_result
        MockEngine.return_value = mock_engine

        with patch("ascend_agent.cli.verify.ModelRouter.__init__", return_value=None):
            result = runner.invoke(verify_app, ["run", str(fixture_path)])

    assert result.exit_code == 0
    assert "Verification Result" in result.stdout
    assert "pass" in result.stdout


def test_verify_output_json(tmp_path):
    """--output flag writes VerificationResult JSON to file."""
    src_path = "tests/fixtures/sample_reproduction.json"
    fixture_path = tmp_path / "sample_reproduction.json"
    fixture_path.write_text(open(src_path).read())

    output_path = tmp_path / "verify_result.json"
    pass_result = _make_pass_result()

    with patch("ascend_agent.cli.verify.VerificationEngine") as MockEngine:
        mock_engine = MagicMock()
        mock_engine.verify.return_value = pass_result
        MockEngine.return_value = mock_engine

        with patch("ascend_agent.cli.verify.ModelRouter.__init__", return_value=None):
            result = runner.invoke(verify_app, [
                "run", str(fixture_path), "--output", str(output_path),
            ])

    assert result.exit_code == 0
    assert output_path.exists()
    data = json.loads(output_path.read_text())
    assert data["status"] == "pass"
    assert "hypothesis_id_verified" in data
    assert "passed" in data
    assert "failed" in data
    assert "tests" in data
