import asyncio
from unittest.mock import AsyncMock, patch

import pytest

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
