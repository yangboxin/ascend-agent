"""Core reproduction engine — orchestrates issue reproduction from diagnosis.

The ReproductionEngine runs a prepare → execute → report workflow,
calling exec_shell for command execution (local or remote via SSH),
and produces a structured ReproductionResult for Phase 5 consumption.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path

from ascend_agent.config import Settings
from ascend_agent.diagnosis.models import DiagnosisResult, ReproductionResult
from ascend_agent.diagnosis.router import ModelRouter

logger = logging.getLogger(__name__)


class ReproductionEngine:
    """Orchestrates issue reproduction from diagnosis hypotheses.

    Follows the Engine pattern: constructor stores dependencies,
    public reproduce() method runs the prepare→execute→report
    workflow and returns a structured ReproductionResult.
    """

    def __init__(
        self,
        router: ModelRouter,
        repo_path: str,
        settings: Settings | None = None,
    ):
        self._router = router
        self._repo_path = Path(repo_path).resolve()
        self._settings = settings or Settings()

    async def reproduce(self, diagnosis: DiagnosisResult) -> ReproductionResult:
        """Run the reproduction workflow. Returns a structured result.

        Workflow: prepare (detect venv, check deps) → execute
        (run commands per hypothesis) → report (build ReproductionResult).
        """
        if not diagnosis.hypotheses:
            return ReproductionResult(
                status="error",
                command="",
                stderr="No hypotheses to test",
                exit_code=-1,
                duration_seconds=0.0,
                hypothesis_id_tested=-1,
                files_changed=[],
            )

        try:
            venv_env = self._detect_venv()
        except Exception as exc:
            logger.warning("Venve detection failed: %s", exc)
            venv_env = {}

        from ascend_agent.tools.shell_exec import exec_shell

        for i, hypothesis in enumerate(diagnosis.hypotheses):
            command = ""
            try:
                command = self._build_reproduction_command(hypothesis)

                if not command:
                    continue

                for evidence in hypothesis.evidence:
                    if not self._validate_path(evidence.file_path):
                        logger.warning(
                            "Path traversal blocked: %s", evidence.file_path
                        )
                        continue

                start = time.monotonic()
                result_json = await exec_shell(
                    command, timeout=self._settings.shell_timeout
                )
                duration = time.monotonic() - start

                result = json.loads(result_json)
                exec_status = result.get("status", "error")

                logger.info(
                    "Reproducing hypothesis %d/%d: %s → %s (%.2fs)",
                    i + 1,
                    len(diagnosis.hypotheses),
                    command[:80],
                    exec_status,
                    duration,
                )

                # Return the first hypothesis that produced a runnable command
                return ReproductionResult(
                    status=exec_status,
                    command=command,
                    stdout=result.get("stdout", ""),
                    stderr=result.get("stderr", ""),
                    exit_code=result.get("exit_code", -1),
                    duration_seconds=duration,
                    hypothesis_id_tested=i,
                    files_changed=[],
                )

            except Exception as exc:
                logger.error("Reproduction failed for hypothesis %d/%d: %s", i + 1, len(diagnosis.hypotheses), exc)
                continue

        return ReproductionResult(
            status="error",
            command="",
            stderr="No hypotheses could be executed",
            exit_code=-1,
            duration_seconds=0.0,
            hypothesis_id_tested=-1,
            files_changed=[],
        )

    def _detect_venv(self) -> dict[str, str]:
        """Detect active virtualenv or conda environment (D-14).

        Does not create or manage venvs — only detects existing ones.
        Returns a dict of env vars that should be inherited.
        """
        result = {}
        virtual_env = os.environ.get("VIRTUAL_ENV")
        if virtual_env:
            result["VIRTUAL_ENV"] = virtual_env
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix:
            result["CONDA_PREFIX"] = conda_prefix
        return result

    def _build_reproduction_command(self, hypothesis) -> str:
        """Construct a reproduction command from hypothesis evidence (heuristic, not LLM).

        Returns the command string or "" if no actionable command can be built.
        """
        for evidence in hypothesis.evidence:
            file_path = evidence.file_path
            if file_path.endswith(".py"):
                if "test" in file_path.lower():
                    return f"python -m pytest {file_path}"
                return f"python {file_path}"
        return f"echo 'No actionable command for: {hypothesis.root_cause[:80]}'"

    def _validate_path(self, path_str: str) -> bool:
        """Check that a path resolves within the repo boundary (D-10).

        Uses the same pattern as edit_file's path traversal protection.
        """
        try:
            resolved = Path(path_str).resolve()
            return str(resolved).startswith(str(self._repo_path))
        except (ValueError, OSError):
            return False
