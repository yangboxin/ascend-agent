import json
from unittest.mock import AsyncMock, patch

import pytest

from ascend_agent.diagnosis.models import ReproductionResult
from ascend_agent.verification.engine import VerificationEngine


class TestVerificationEngine:
    def test_constructor_stores_dependencies(self, mock_router, mock_settings, tmp_path):
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        assert engine._router is mock_router
        assert engine._repo_path == tmp_path.resolve()
        assert engine._settings is mock_settings

    @pytest.mark.asyncio
    async def test_verify_no_files_changed(self, mock_router, mock_settings, tmp_path):
        reproduction = ReproductionResult(
            status="success",
            command="echo test",
            stdout="",
            stderr="",
            exit_code=0,
            duration_seconds=0.0,
            hypothesis_id_tested=0,
            files_changed=[],
        )
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        result = await engine.verify(reproduction)
        assert result.status == "no_tests"
        assert "No files were changed" in result.summary

    def test_detect_framework_finds_pyproject_toml(self, mock_router, mock_settings, sample_repo_dir):
        engine = VerificationEngine(mock_router, str(sample_repo_dir), mock_settings)
        assert engine._detect_framework() == "pytest"

    def test_detect_framework_finds_pytest_ini(self, mock_router, mock_settings, tmp_path):
        (tmp_path / "pytest.ini").write_text("[pytest]\n")
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        assert engine._detect_framework() == "pytest"

    def test_detect_framework_finds_setup_cfg(self, mock_router, mock_settings, tmp_path):
        (tmp_path / "setup.cfg").write_text("[tool:pytest]\n")
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        assert engine._detect_framework() == "pytest"

    def test_detect_framework_returns_none(self, mock_router, mock_settings, tmp_path):
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        assert engine._detect_framework() is None

    def test_map_test_files_maps_src_to_test(self, mock_router, mock_settings, sample_repo_dir):
        engine = VerificationEngine(mock_router, str(sample_repo_dir), mock_settings)
        result = engine._map_test_files(["src/mypkg/core.py"])
        assert any("test_core" in f for f in result)

    def test_map_test_files_returns_empty(self, mock_router, mock_settings, tmp_path):
        (tmp_path / "tests").mkdir()
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        result = engine._map_test_files(["src/mypkg/nonexistent.py"])
        assert result == []

    @pytest.mark.asyncio
    async def test_verify_executes_via_exec_shell(
        self, mock_router, mock_settings, sample_reproduction, tmp_path
    ):
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        with patch(
            "ascend_agent.verification.engine.exec_shell", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = json.dumps({
                "status": "success",
                "stdout": "1 passed",
                "stderr": "",
                "exit_code": 0,
                "summary": {"passed": 1, "failed": 0, "error": 0},
                "tests": [],
            })
            result = await engine.verify(sample_reproduction)
            assert mock_exec.called
            assert "--json-report" in mock_exec.call_args[0][0]
            assert result.status == "pass"

    @pytest.mark.asyncio
    async def test_verify_handles_exec_shell_exception(
        self, mock_router, mock_settings, sample_reproduction, tmp_path
    ):
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        with patch(
            "ascend_agent.verification.engine.exec_shell", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.side_effect = RuntimeError("execution failed")
            result = await engine.verify(sample_reproduction)
            assert result.status == "error"
            assert "execution failed" in result.summary

    def test_validate_path_rejects_outside_repo(self, mock_router, mock_settings, tmp_path):
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        assert engine._validate_path("/etc/passwd") is False

    def test_validate_path_accepts_inside_repo(self, mock_router, mock_settings, tmp_path):
        legit_path = tmp_path / "tests" / "test_core.py"
        legit_path.parent.mkdir(parents=True)
        legit_path.write_text("")
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        assert engine._validate_path("tests/test_core.py") is True
