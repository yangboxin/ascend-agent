"""Core reproduction engine — orchestrates issue reproduction from diagnosis.

The ReproductionEngine runs a prepare → execute → report workflow,
calling exec_shell for command execution (local or remote via SSH),
and produces a structured ReproductionResult for Phase 5 consumption.
"""

import json
import logging
import os
import shlex
import time
from pathlib import Path

from ascend_agent.config import Settings
from ascend_agent.context.models import TraceInfo
from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    Hypothesis,
    ReproductionAttempt,
    ReproductionResult,
)
from ascend_agent.diagnosis.router import ModelRouter
from ascend_agent.tools.shell_exec import exec_shell

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

    async def reproduce(
        self, diagnosis: DiagnosisResult, trace: TraceInfo | None = None
    ) -> ReproductionResult:
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

        attempts: list[ReproductionAttempt] = []
        last_error = ""
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

                result, duration = await self._execute_command(command)
                exec_status = result.get("status", "error")
                exit_code = result.get("exit_code", -1)
                stdout = result.get("stdout", "")
                stderr = result.get("stderr", "")
                signals = self._error_signals(trace, hypothesis)
                matched, matched_signal = self._matches_error(stdout, stderr, signals)
                reproduced = exit_code != 0 and (matched or not signals)
                if reproduced and not matched_signal:
                    matched_signal = "non-zero exit"

                attempts.append(
                    ReproductionAttempt(
                        kind="existing_command",
                        command=command,
                        status=exec_status,
                        exit_code=exit_code,
                        matched_error=reproduced,
                        matched_signal=matched_signal,
                        summary="Existing evidence command reproduced the original error"
                        if reproduced
                        else "Existing evidence command did not match the original error",
                    )
                )

                logger.info(
                    "Reproducing hypothesis %d/%d: %s → %s (%.2fs)",
                    i + 1,
                    len(diagnosis.hypotheses),
                    command[:80],
                    exec_status,
                    duration,
                )

                repro_file = self._write_bad_case(i, command, signals)
                repro_command = f"python -m pytest {shlex.quote(str(self._repo_path / repro_file))}"
                repro_result, repro_duration = await self._execute_command(repro_command)
                repro_status = repro_result.get("status", "error")
                repro_exit_code = repro_result.get("exit_code", -1)
                bad_case_verified = repro_exit_code == 0
                attempts.append(
                    ReproductionAttempt(
                        kind="generated_bad_case",
                        command=repro_command,
                        repro_file=repro_file,
                        status=repro_status,
                        exit_code=repro_exit_code,
                        matched_error=bad_case_verified,
                        matched_signal=matched_signal
                        or (signals[0] if signals and bad_case_verified else ""),
                        summary="Generated bad case verified the reproduction"
                        if bad_case_verified
                        else "Generated bad case did not verify the reproduction",
                    )
                )

                return ReproductionResult(
                    status="success" if bad_case_verified else "fail",
                    command=repro_command,
                    stdout=repro_result.get("stdout", ""),
                    stderr=repro_result.get("stderr", ""),
                    exit_code=repro_exit_code,
                    duration_seconds=repro_duration,
                    hypothesis_id_tested=i,
                    repo_path=str(self._repo_path),
                    files_changed=[repro_file],
                    reproduced=bad_case_verified,
                    repro_file=repro_file,
                    matched_error=bad_case_verified,
                    matched_error_signal=matched_signal
                    or (signals[0] if signals and bad_case_verified else ""),
                    attempts=attempts,
                )

            except Exception as exc:
                logger.error("Reproduction failed for hypothesis %d/%d: %s", i + 1, len(diagnosis.hypotheses), exc)
                last_error = str(exc)
                continue

        return ReproductionResult(
            status="error",
            command="",
            stderr=last_error or "No hypotheses could be executed",
            exit_code=-1,
            duration_seconds=0.0,
            hypothesis_id_tested=-1,
            files_changed=[],
            attempts=attempts,
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

    async def _execute_command(self, command: str) -> tuple[dict, float]:
        start = time.monotonic()
        result_json = await exec_shell(command, timeout=self._settings.shell_timeout)
        duration = time.monotonic() - start
        return json.loads(result_json), duration

    def _build_reproduction_command(self, hypothesis: Hypothesis) -> str:
        """Construct a reproduction command from hypothesis evidence (heuristic, not LLM).

        Returns the command string or "" if no actionable command can be built.
        """
        for evidence in hypothesis.evidence:
            file_path = self._resolve_evidence_path(evidence.file_path)
            if file_path and file_path.suffix == ".py":
                quoted_path = shlex.quote(str(file_path))
                if "test" in str(file_path).lower():
                    return f"python -m pytest {quoted_path}"
                return f"python {quoted_path}"
        return f"echo 'No actionable command for: {hypothesis.root_cause[:80]}'"

    def _resolve_evidence_path(self, file_path: str) -> Path | None:
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = self._repo_path / path
            resolved = path.resolve()
            if str(resolved).startswith(str(self._repo_path)):
                return resolved
        except (ValueError, OSError):
            return None
        return None

    def _error_signals(
        self, trace: TraceInfo | None, hypothesis: Hypothesis
    ) -> list[str]:
        raw_signals: list[str] = []
        if trace is not None:
            raw_signals.extend([trace.error_type or "", trace.error_message or ""])
            raw_signals.extend(trace.runtime_signals.values())
            raw_signals.extend(event.message for event in trace.error_events)
            if trace.raw_text:
                raw_signals.extend(trace.raw_text.splitlines()[-5:])

        if not raw_signals:
            raw_signals.append(hypothesis.root_cause)

        signals: list[str] = []
        seen: set[str] = set()
        for signal in raw_signals:
            normalized = " ".join(str(signal).strip().split())
            if len(normalized) < 4:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            signals.append(normalized[:240])
        return signals

    def _matches_error(
        self, stdout: str, stderr: str, signals: list[str]
    ) -> tuple[bool, str]:
        output = f"{stdout}\n{stderr}".lower()
        for signal in signals:
            if signal.lower() in output:
                return True, signal
        return False, ""

    def _write_bad_case(
        self, hypothesis_index: int, command: str, signals: list[str]
    ) -> str:
        repro_dir = self._repo_path / ".ascend-agent" / "repros"
        repro_dir.mkdir(parents=True, exist_ok=True)
        repro_file = repro_dir / f"test_repro_h{hypothesis_index}.py"
        command_args = shlex.split(command)
        content = (
            '"""Generated by Ascend Agent to reproduce a diagnosis hypothesis."""\n\n'
            "import subprocess\n\n"
            f"COMMAND = {command_args!r}\n"
            f"EXPECTED_SIGNALS = {signals!r}\n"
            f"CWD = {str(self._repo_path)!r}\n\n\n"
            "def test_reproduces_diagnosis():\n"
            "    result = subprocess.run(\n"
            "        COMMAND,\n"
            "        cwd=CWD,\n"
            "        text=True,\n"
            "        stdout=subprocess.PIPE,\n"
            "        stderr=subprocess.PIPE,\n"
            "        check=False,\n"
            "    )\n"
            '    output = (result.stdout or "") + "\\n" + (result.stderr or "")\n'
            "    assert result.returncode != 0, (\n"
            '        "Expected the reproduction command to fail, but it exited 0.\\n"\n'
            '        f"stdout:\\n{result.stdout}\\nstderr:\\n{result.stderr}"\n'
            "    )\n"
            "    if EXPECTED_SIGNALS:\n"
            "        lowered = output.lower()\n"
            "        assert any(signal.lower() in lowered for signal in EXPECTED_SIGNALS), (\n"
            '            "The command failed, but did not match the original error signals.\\n"\n'
            '            f"Expected one of: {EXPECTED_SIGNALS}\\nOutput:\\n{output}"\n'
            "        )\n"
        )
        repro_file.write_text(content)
        return str(repro_file.relative_to(self._repo_path))

    def _validate_path(self, path_str: str) -> bool:
        """Check that a path resolves within the repo boundary (D-10).

        Uses the same pattern as edit_file's path traversal protection.
        """
        return self._resolve_evidence_path(path_str) is not None
