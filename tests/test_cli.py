from typer.testing import CliRunner

from ascend_agent.cli.app import app

runner = CliRunner()


def test_cli_no_args_shows_help():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Ascend Diagnostic Agent" in result.stdout


def test_cli_diagnose_subcommand():
    result = runner.invoke(app, ["diagnose", "run", "--help"])
    assert result.exit_code == 0
    assert "REPO" in result.stdout
    assert "--trace-text" in result.stdout


def test_cli_diagnose_run_basic(tmp_path, monkeypatch):
    from unittest.mock import Mock

    (tmp_path / "test.py").write_text("x = 1\n")
    mock_engine = Mock()
    mock_engine.diagnose.return_value = Mock(hypotheses=[], errors=[], iterations_used=0)
    import ascend_agent.cli.diagnose as diag_mod
    monkeypatch.setattr(diag_mod, "Engine", lambda router, repo_path: mock_engine)
    monkeypatch.setattr("ascend_agent.diagnosis.router.ModelRouter.__init__", lambda self: None)

    result = runner.invoke(app, [
        "diagnose", "run", str(tmp_path),
        "--trace-text", "ValueError: test",
    ])
    assert result.exit_code == 0
    assert "Repository Info" in result.stdout


def test_cli_diagnose_integration(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from ascend_agent.diagnosis.models import DiagnosisResult, Hypothesis, Evidence

    (tmp_path / "main.py").write_text("def test():\n    return 1\n")

    mock_result = DiagnosisResult(
        hypotheses=[
            Hypothesis(
                root_cause="Mock root cause",
                evidence=[
                    Evidence(
                        file_path="main.py",
                        line_number=10,
                        code_snippet="def test():\n    return 1",
                        relevance="mock relevance",
                    )
                ],
                confidence=0.85,
            )
        ],
        errors=[],
        iterations_used=2,
    )
    mock_engine = Mock()
    mock_engine.diagnose.return_value = mock_result

    import ascend_agent.cli.diagnose as diag_mod
    monkeypatch.setattr(diag_mod, "Engine", lambda router, repo_path: mock_engine)
    monkeypatch.setattr("ascend_agent.diagnosis.router.ModelRouter.__init__", lambda self: None)

    result = runner.invoke(app, [
        "diagnose", "run", str(tmp_path),
        "--trace-text", "ValueError: mock error",
    ])
    assert result.exit_code == 0
    assert "Diagnosis Results" in result.stdout
    assert "Mock root cause" in result.stdout
    assert "Confidence: 85%" in result.stdout
    assert "iterations used: 2" in result.stdout
