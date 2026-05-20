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


def test_cli_diagnose_run_basic(tmp_path):
    (tmp_path / "test.py").write_text("x = 1\n")
    result = runner.invoke(app, [
        "diagnose", "run", str(tmp_path),
        "--trace-text", "ValueError: test",
    ])
    assert result.exit_code == 0
    assert "Repository Info" in result.stdout
