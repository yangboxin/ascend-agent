import sys
from unittest.mock import MagicMock

# Mock mcp module before any ascend_agent imports to avoid Python 3.10+ match syntax errors
# mcp (version 1.27.1) uses `match` statements which are SyntaxError on Python 3.9
class _MockContext:
    """Mock Context type for mcp.server.fastmcp."""
    pass


class _MockFastMCP:
    """Mock FastMCP type for mcp.server.fastmcp."""
    def __init__(self, *args, **kwargs):
        pass

    def tool(self, *args, **kwargs):
        return lambda f: f


_MCP_MOCK = MagicMock()
_MCP_SERVER_MOCK = MagicMock()
_MCP_FASTMCP_MOCK = MagicMock()
_MCP_FASTMCP_MOCK.Context = _MockContext
_MCP_FASTMCP_MOCK.FastMCP = _MockFastMCP
sys.modules['mcp'] = _MCP_MOCK
sys.modules['mcp.server'] = _MCP_SERVER_MOCK
sys.modules['mcp.server.fastmcp'] = _MCP_FASTMCP_MOCK

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
    monkeypatch.setattr("ascend_agent.diagnosis.router.ModelRouter.__init__", lambda self, **kwargs: None)

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
    monkeypatch.setattr("ascend_agent.diagnosis.router.ModelRouter.__init__", lambda self, **kwargs: None)

    result = runner.invoke(app, [
        "diagnose", "run", str(tmp_path),
        "--trace-text", "ValueError: mock error",
    ])
    assert result.exit_code == 0
    assert "Diagnosis Results" in result.stdout
    assert "Mock root cause" in result.stdout
    assert "Confidence: 85%" in result.stdout
    assert "iterations used: 2" in result.stdout


# ---------------------------------------------------------------------------
# Fix CLI tests
# ---------------------------------------------------------------------------


def _write_diagnosis_json(tmp_path) -> str:
    """Write a minimal valid DiagnosisOutput JSON and return the file path."""
    import json

    data = {
        "context_doc": {
            "repo": {"path": str(tmp_path), "language": "python", "file_count": 0, "structure": []},
            "trace": None,
            "config_env": {"python_version": "3.10", "platform": "linux", "env_vars": {}},
        },
        "diagnosis_result": {"hypotheses": [], "errors": [], "iterations_used": 0},
    }
    path = tmp_path / "diagnosis.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_fix_run_reads_diagnosis_json(tmp_path, monkeypatch):
    """Fix run reads diagnosis JSON from file and displays summary."""
    from unittest.mock import Mock

    diagnosis_path = _write_diagnosis_json(tmp_path)

    mock_engine = Mock()
    mock_engine.generate_fixes.return_value = Mock(
        suggestions=[], errors=[], total_hypotheses=0
    )
    import ascend_agent.cli.fix as fix_mod
    monkeypatch.setattr(fix_mod, "FixEngine", lambda *args, **kwargs: mock_engine)
    monkeypatch.setattr("ascend_agent.diagnosis.router.ModelRouter.__init__", lambda self, **kwargs: None)

    result = runner.invoke(app, ["fix", "run", diagnosis_path])
    assert result.exit_code == 0
    assert "Fix Generation Complete" in result.stdout
    assert "No fix suggestions" in result.stdout


def test_fix_run_generates_suggestions(tmp_path, monkeypatch):
    """Fix run generates suggestions and displays them."""
    from unittest.mock import Mock
    import ascend_agent.cli.fix as fix_mod
    from ascend_agent.diagnosis.models import FixSuggestion, FixGenerationResult, Replacement

    diagnosis_path = _write_diagnosis_json(tmp_path)
    # Create the target file so batch apply can succeed
    (tmp_path / "test.py").write_text("x = 1\n")

    mock_result = FixGenerationResult(
        suggestions=[
            FixSuggestion(
                file_path="test.py",
                diff_patch="--- test.py\n+++ test.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
                explanation="Fix the value",
                hypothesis_id=0,
                replacements=[
                    Replacement(file_path="test.py", old_text="x = 1\n", new_text="x = 2\n")
                ],
            )
        ],
        errors=[],
        total_hypotheses=1,
    )

    mock_engine = Mock()
    mock_engine.generate_fixes.return_value = mock_result

    monkeypatch.setattr(fix_mod, "FixEngine", lambda *args, **kwargs: mock_engine)
    monkeypatch.setattr("ascend_agent.diagnosis.router.ModelRouter.__init__", lambda self, **kwargs: None)
    monkeypatch.setattr(fix_mod, "_run_review_workflow", lambda *args, **kwargs: list(args[0]) if args else [])

    result = runner.invoke(app, ["fix", "run", diagnosis_path])
    assert result.exit_code == 0
    assert "test.py" in result.stdout
    assert "1 fix suggestions" in result.stdout
    assert "Applied 1 file(s)" in result.stdout


def test_fix_run_stdin_input(tmp_path, monkeypatch):
    """Fix run reads diagnosis JSON from stdin when no file arg provided."""
    import json
    from unittest.mock import Mock

    data = {
        "context_doc": {
            "repo": {"path": str(tmp_path), "language": "python", "file_count": 0, "structure": []},
            "trace": None,
            "config_env": {"python_version": "3.10", "platform": "linux", "env_vars": {}},
        },
        "diagnosis_result": {"hypotheses": [], "errors": [], "iterations_used": 0},
    }

    mock_engine = Mock()
    mock_engine.generate_fixes.return_value = Mock(
        suggestions=[], errors=[], total_hypotheses=0
    )
    import ascend_agent.cli.fix as fix_mod
    monkeypatch.setattr(fix_mod, "FixEngine", lambda *args, **kwargs: mock_engine)
    monkeypatch.setattr("ascend_agent.diagnosis.router.ModelRouter.__init__", lambda self, **kwargs: None)

    result = runner.invoke(app, ["fix", "run"], input=json.dumps(data))
    assert result.exit_code == 0
    assert "Fix Generation Complete" in result.stdout


def test_fix_run_missing_api_key(tmp_path, monkeypatch):
    """Fix run exits with code 1 when API key is missing."""
    diagnosis_path = _write_diagnosis_json(tmp_path)

    # Remove API key so ModelRouter raises ValueError
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = runner.invoke(app, ["fix", "run", diagnosis_path])
    assert result.exit_code == 1
    assert "OPENAI_API_KEY" in result.stdout


# ---------------------------------------------------------------------------
# Reproduction CLI tests
# ---------------------------------------------------------------------------


def _write_repro_diagnosis_json(tmp_path) -> str:
    """Write a minimal valid DiagnosisOutput JSON for reproduce testing."""
    import json

    data = {
        "context_doc": {
            "repo": {"path": str(tmp_path), "language": "python", "file_count": 0, "structure": []},
            "trace": None,
            "config_env": {"python_version": "3.10", "platform": "linux", "env_vars": {}},
        },
        "diagnosis_result": {"hypotheses": [], "errors": [], "iterations_used": 0},
    }
    path = tmp_path / "diagnosis.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_reproduce_run_command(tmp_path, monkeypatch):
    """reproduce run loads diagnosis JSON and displays results."""
    from unittest.mock import AsyncMock, Mock
    from ascend_agent.diagnosis.models import ReproductionResult

    diagnosis_path = _write_repro_diagnosis_json(tmp_path)

    mock_result = ReproductionResult(
        status="success",
        command="echo test",
        stdout="hello",
        stderr="",
        exit_code=0,
        duration_seconds=0.1,
        hypothesis_id_tested=-1,
        files_changed=[],
    )
    mock_engine = Mock()
    mock_engine.reproduce = AsyncMock(return_value=mock_result)

    monkeypatch.setattr(
        "ascend_agent.cli.reproduce.ReproductionEngine",
        lambda *args, **kwargs: mock_engine,
    )
    monkeypatch.setattr(
        "ascend_agent.diagnosis.router.ModelRouter.__init__",
        lambda self, **kwargs: None,
    )

    result = runner.invoke(app, ["reproduce", "run", diagnosis_path])
    assert result.exit_code == 0
    assert "Reproduction Result" in result.stdout
    assert "success" in result.stdout


def test_reproduce_run_missing_file():
    """reproduce run exits with code 1 when file does not exist."""
    result = runner.invoke(app, ["reproduce", "run", "nonexistent.json"])
    assert result.exit_code == 1
    assert "Error" in result.stdout


def test_reproduce_run_missing_api_key(tmp_path, monkeypatch):
    """reproduce run exits with code 1 when API key is missing."""
    diagnosis_path = _write_repro_diagnosis_json(tmp_path)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = runner.invoke(app, ["reproduce", "run", diagnosis_path])
    assert result.exit_code == 1
    assert "OPENAI_API_KEY" in result.stdout


# ---------------------------------------------------------------------------
# --provider flag tests
# ---------------------------------------------------------------------------


def test_cli_diagnose_root_provider_flag(tmp_path, monkeypatch):
    """--provider flag at root level is passed to create_router."""
    from unittest.mock import Mock

    (tmp_path / "test.py").write_text("x = 1\n")

    mock_engine = Mock()
    mock_engine.diagnose.return_value = Mock(hypotheses=[], errors=[], iterations_used=0)
    import ascend_agent.cli.diagnose as diag_mod
    monkeypatch.setattr(diag_mod, "Engine", lambda router, repo_path: mock_engine)
    monkeypatch.setattr("ascend_agent.diagnosis.router.ModelRouter.__init__", lambda self, **kwargs: None)

    result = runner.invoke(app, [
        "--provider", "deepseek",
        "diagnose", "run", str(tmp_path),
        "--trace-text", "Error: test",
    ])
    assert result.exit_code == 0
    assert "Repository Info" in result.stdout


def test_cli_diagnose_per_command_provider_override(tmp_path, monkeypatch):
    """Per-command --provider overrides root --provider."""
    from unittest.mock import Mock

    (tmp_path / "test.py").write_text("x = 1\n")

    mock_engine = Mock()
    mock_engine.diagnose.return_value = Mock(hypotheses=[], errors=[], iterations_used=0)
    import ascend_agent.cli.diagnose as diag_mod
    monkeypatch.setattr(diag_mod, "Engine", lambda router, repo_path: mock_engine)
    monkeypatch.setattr("ascend_agent.diagnosis.router.ModelRouter.__init__", lambda self, **kwargs: None)

    result = runner.invoke(app, [
        "--provider", "openai",
        "diagnose", "run", "--provider", "deepseek",
        str(tmp_path), "--trace-text", "Error: test",
    ])
    assert result.exit_code == 0
    assert "Repository Info" in result.stdout


def test_cli_provider_flag_help():
    """--provider flag appears in help output."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--provider" in result.stdout

    result = runner.invoke(app, ["diagnose", "run", "--help"])
    assert result.exit_code == 0
    assert "--provider" in result.stdout
