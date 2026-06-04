import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from ascend_agent.context.models import TraceInfo
from ascend_agent.diagnosis.models import DiagnosisResult
from ascend_agent.reproduction.engine import ReproductionEngine


class TestReproductionEngine:
    def test_constructor_stores_dependencies(self, mock_router, mock_settings, tmp_path):
        engine = ReproductionEngine(mock_router, str(tmp_path), mock_settings)
        assert engine._router is mock_router
        assert engine._repo_path == tmp_path.resolve()
        assert engine._settings is mock_settings

    @pytest.mark.asyncio
    async def test_reproduce_returns_result(
        self, mock_router, mock_settings, sample_diagnosis, tmp_path
    ):
        engine = ReproductionEngine(mock_router, str(tmp_path), mock_settings)
        result = await engine.reproduce(sample_diagnosis)
        assert result.status in ("success", "fail", "error")

    @pytest.mark.asyncio
    async def test_engine_handles_exec_shell_failure(
        self, mock_router, mock_settings, sample_diagnosis, tmp_path
    ):
        engine = ReproductionEngine(mock_router, str(tmp_path), mock_settings)
        with patch(
            "ascend_agent.reproduction.engine.exec_shell", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.side_effect = RuntimeError("execution failed")
            result = await engine.reproduce(sample_diagnosis)
            assert result.status == "error"
            assert "execution failed" in result.stderr

    @pytest.mark.asyncio
    async def test_reproduce_matches_original_error_from_existing_command(
        self, mock_router, mock_settings, sample_diagnosis, tmp_path
    ):
        test_file = tmp_path / "tests" / "test_dim.py"
        test_file.parent.mkdir()
        test_file.write_text("def test_dimensions():\n    raise ValueError('boom')\n")
        trace = TraceInfo(
            raw_text="ValueError: boom",
            error_type="ValueError",
            error_message="boom",
        )
        engine = ReproductionEngine(mock_router, str(tmp_path), mock_settings)
        with patch(
            "ascend_agent.reproduction.engine.exec_shell", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.side_effect = [
                json.dumps(
                    {
                        "status": "fail",
                        "stdout": "",
                        "stderr": "ValueError: boom",
                        "exit_code": 1,
                    }
                ),
                json.dumps(
                    {
                        "status": "success",
                        "stdout": "1 passed",
                        "stderr": "",
                        "exit_code": 0,
                    }
                ),
            ]

            result = await engine.reproduce(sample_diagnosis, trace=trace)

        assert result.status == "success"
        assert result.reproduced is True
        assert result.repro_file == ".ascend-agent/repros/test_repro_h0.py"
        assert result.files_changed == [result.repro_file]
        assert (tmp_path / result.repro_file).exists()
        assert result.matched_error_signal == "ValueError"
        assert result.attempts[0].kind == "existing_command"
        assert result.attempts[1].kind == "generated_bad_case"
        assert mock_exec.await_count == 2

    @pytest.mark.asyncio
    async def test_reproduce_generates_bad_case_when_existing_command_does_not_match(
        self, mock_router, mock_settings, sample_diagnosis, tmp_path
    ):
        test_file = tmp_path / "tests" / "test_dim.py"
        test_file.parent.mkdir()
        test_file.write_text("def test_dimensions():\n    assert True\n")
        trace = TraceInfo(
            raw_text="RuntimeError: target failure",
            error_type="RuntimeError",
            error_message="target failure",
        )
        engine = ReproductionEngine(mock_router, str(tmp_path), mock_settings)
        with patch(
            "ascend_agent.reproduction.engine.exec_shell", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.side_effect = [
                json.dumps(
                    {
                        "status": "success",
                        "stdout": "1 passed",
                        "stderr": "",
                        "exit_code": 0,
                    }
                ),
                json.dumps(
                    {
                        "status": "success",
                        "stdout": "1 passed",
                        "stderr": "",
                        "exit_code": 0,
                    }
                ),
            ]

            result = await engine.reproduce(sample_diagnosis, trace=trace)

        assert result.status == "success"
        assert result.reproduced is True
        assert result.repro_file == ".ascend-agent/repros/test_repro_h0.py"
        assert result.files_changed == [result.repro_file]
        assert (tmp_path / result.repro_file).exists()
        assert result.attempts[0].kind == "existing_command"
        assert result.attempts[1].kind == "generated_bad_case"
        assert mock_exec.await_count == 2

    def test_detect_venv_virtualenv(
        self, mock_router, mock_settings, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("VIRTUAL_ENV", "/fake/venv")
        engine = ReproductionEngine(mock_router, str(tmp_path), mock_settings)
        assert engine._detect_venv() == {"VIRTUAL_ENV": "/fake/venv"}

    def test_detect_venv_conda(
        self, mock_router, mock_settings, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("CONDA_PREFIX", "/opt/conda/envs/test")
        engine = ReproductionEngine(mock_router, str(tmp_path), mock_settings)
        assert engine._detect_venv() == {"CONDA_PREFIX": "/opt/conda/envs/test"}

    def test_detect_venv_none(
        self, mock_router, mock_settings, tmp_path, monkeypatch
    ):
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.delenv("CONDA_PREFIX", raising=False)
        engine = ReproductionEngine(mock_router, str(tmp_path), mock_settings)
        assert engine._detect_venv() == {}

    def test_path_traversal_blocked(self, mock_router, mock_settings, tmp_path):
        engine = ReproductionEngine(mock_router, str(tmp_path), mock_settings)
        assert engine._validate_path("/etc/passwd") is False
        legit_path = tmp_path / "legit.py"
        legit_path.write_text("print('ok')")
        assert engine._validate_path(str(legit_path)) is True

    def test_reproduce_no_hypotheses(self, mock_router, mock_settings, tmp_path):
        empty_diagnosis = DiagnosisResult(hypotheses=[], errors=[], iterations_used=0)
        engine = ReproductionEngine(mock_router, str(tmp_path), mock_settings)
        import asyncio

        async def run():
            return await engine.reproduce(empty_diagnosis)

        result = asyncio.run(run())
        assert result.status == "error"
        assert "No hypotheses" in result.stderr
