"""Verification engine — orchestrates test verification from reproduction results.

The VerificationEngine consumes ReproductionResult from Phase 4, auto-detects
the test framework, maps changed source files to test files, runs only relevant
tests via exec_shell, and produces a structured VerificationResult.

Follows the Engine pattern established by ReproductionEngine: constructor stores
dependencies, public async verify() method runs the detect->map->execute->parse->report
workflow and returns a structured Pydantic result.
"""

import json
import logging
import time
from pathlib import Path

from ascend_agent.config import Settings
from ascend_agent.diagnosis.models import ReproductionResult, TestDetail, VerificationResult
from ascend_agent.diagnosis.router import ModelRouter

logger = logging.getLogger(__name__)


class VerificationEngine:
    """Orchestrates test verification from reproduction results.

    Follows the Engine pattern: constructor stores dependencies,
    public verify() method runs the detect->map->execute->parse->report
    workflow and returns a structured VerificationResult.
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

    async def verify(self, reproduction: ReproductionResult) -> VerificationResult:
        """Run the verification workflow.

        Workflow: detect framework -> map test files -> build command ->
        execute via exec_shell -> parse JSON report -> return VerificationResult.
        """
        framework = None
        command = ""

        try:
            # Early return: no files changed
            if not reproduction.files_changed:
                return VerificationResult(
                    status="no_tests",
                    hypothesis_id_verified=reproduction.hypothesis_id_tested,
                    framework=None,
                    command="",
                    summary="No files were changed during reproduction — nothing to verify.",
                    tests_found=0,
                    tests_run=0,
                    passed=0,
                    failed=0,
                    errors=0,
                    skipped=0,
                    xfailed=0,
                    xpassed=0,
                    tests=[],
                    exit_code=-1,
                    duration_seconds=0.0,
                    files_tested=[],
                    stdout="",
                )

            # Detect test framework
            framework = self._detect_framework()
            if framework is None:
                return VerificationResult(
                    status="error",
                    hypothesis_id_verified=reproduction.hypothesis_id_tested,
                    framework=None,
                    command="",
                    summary=(
                        "No supported test framework detected in the repository. "
                        "Supported: pytest (looks for pytest.ini, "
                        "pyproject.toml [tool.pytest.ini_options], "
                        "setup.cfg [tool:pytest])"
                    ),
                    tests_found=0,
                    tests_run=0,
                    passed=0,
                    failed=0,
                    errors=0,
                    skipped=0,
                    xfailed=0,
                    xpassed=0,
                    tests=[],
                    exit_code=-1,
                    duration_seconds=0.0,
                    files_tested=[],
                    stdout="",
                )

            # Map changed files to test files
            test_files = self._map_test_files(reproduction.files_changed)
            if not test_files:
                return VerificationResult(
                    status="no_tests",
                    hypothesis_id_verified=reproduction.hypothesis_id_tested,
                    framework=framework,
                    command="",
                    summary=(
                        f"No relevant test files found for changed files: "
                        f"{', '.join(reproduction.files_changed)}"
                    ),
                    tests_found=0,
                    tests_run=0,
                    passed=0,
                    failed=0,
                    errors=0,
                    skipped=0,
                    xfailed=0,
                    xpassed=0,
                    tests=[],
                    exit_code=-1,
                    duration_seconds=0.0,
                    files_tested=[],
                    stdout="",
                )

            # Build pytest command
            test_files_str = " ".join(str(f) for f in test_files)
            command = (
                f"cd {self._repo_path} && python -m pytest "
                f"{test_files_str} --json-report --json-report-file=none "
                f"--json-report-summary"
            )

            # Execute via exec_shell (lazy import)
            from ascend_agent.tools.shell_exec import exec_shell

            start = time.monotonic()
            result_json = await exec_shell(command, timeout=self._settings.test_timeout)
            duration = time.monotonic() - start

            result = json.loads(result_json)

            exit_code = result.get("exit_code", -1)
            summary = result.get("summary", {})
            report_tests = result.get("tests", [])

            passed = summary.get("passed", 0)
            failed = summary.get("failed", 0)
            errors = summary.get("error", 0)
            skipped = summary.get("skipped", 0)
            xfailed = summary.get("xfailed", 0)
            xpassed = summary.get("xpassed", 0)
            tests_run = passed + failed + errors + skipped + xfailed + xpassed

            # Determine status
            stderr = result.get("stderr", "")
            if errors > 0:
                status = "error"
            elif "timed out after" in stderr:
                status = "timeout"
            elif exit_code != 0:
                status = "fail"
            else:
                status = "pass"

            # Map report tests to TestDetail objects
            test_details = []
            for t in report_tests:
                test_details.append(
                    TestDetail(
                        nodeid=t.get("nodeid", ""),
                        outcome=t.get("outcome", "error"),
                        duration=t.get("duration"),
                        message=t.get("message"),
                    )
                )

            logger.info(
                "Verification complete: %d/%d passed (%.2fs)",
                passed,
                passed + failed + errors,
                duration,
            )

            return VerificationResult(
                status=status,
                hypothesis_id_verified=reproduction.hypothesis_id_tested,
                framework=framework,
                command=command,
                summary=f"{passed} passed, {failed} failed, {errors} errors",
                tests_found=len(test_files),
                tests_run=tests_run,
                passed=passed,
                failed=failed,
                errors=errors,
                skipped=skipped,
                xfailed=xfailed,
                xpassed=xpassed,
                tests=test_details,
                exit_code=exit_code,
                duration_seconds=duration,
                files_tested=test_files,
                stdout=result.get("stdout", ""),
            )

        except Exception as exc:
            logger.error("Verification failed: %s", exc)
            return VerificationResult(
                status="error",
                hypothesis_id_verified=reproduction.hypothesis_id_tested,
                framework=framework,
                command=command,
                summary=f"Verification failed: {exc}",
                tests_found=0,
                tests_run=0,
                passed=0,
                failed=0,
                errors=0,
                skipped=0,
                xfailed=0,
                xpassed=0,
                tests=[],
                exit_code=-1,
                duration_seconds=0.0,
                files_tested=[],
                stdout="",
            )

    def _detect_framework(self) -> str | None:
        """Auto-detect test framework in the target repo (D-01).

        Probes for pytest config files in order:
        1. pytest.ini
        2. pyproject.toml with [tool.pytest.ini_options]
        3. setup.cfg with [tool:pytest]

        Returns 'pytest' on first match, None if no config found.
        """
        if (self._repo_path / "pytest.ini").exists():
            return "pytest"

        pyproject = self._repo_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            if "[tool.pytest.ini_options]" in content or "[tool.pytest]" in content:
                return "pytest"

        setup_cfg = self._repo_path / "setup.cfg"
        if setup_cfg.exists():
            content = setup_cfg.read_text(encoding="utf-8", errors="replace")
            if "[tool:pytest]" in content:
                return "pytest"

        return None

    def _map_test_files(self, files_changed: list[str]) -> list[str]:
        """Map changed source files to corresponding test files (D-02).

        Three-tier heuristic:
        1. Exact convention match: strip src/ prefix, prepend tests/
        2. Glob search for *_test.py and test_*.py variants
        3. Return deduplicated list of existing test file paths
        """
        test_files = []

        for file_path in files_changed:
            path = Path(file_path)
            stem = path.stem

            # Tier 1: Exact convention match
            # src/foo/bar.py -> tests/test_foo/test_bar.py or tests/test_bar.py
            if str(path).startswith("src/"):
                relative = path.relative_to("src")
                parent = relative.parent
                # Try tests/{parent}/test_{stem}.py
                candidate = Path("tests") / parent / f"test_{stem}.py"
                if self._validate_path(str(candidate)):
                    test_files.append(str(candidate))
                    continue
                # Try tests/{parent}/{stem}_test.py
                candidate = Path("tests") / parent / f"{stem}_test.py"
                if self._validate_path(str(candidate)):
                    test_files.append(str(candidate))
                    continue

            # Tier 2: Glob search for test files in corresponding test dir
            # Map src/foo/bar.py -> tests/foo/ (look for *_test.py and test_*.py)
            if str(path).startswith("src/"):
                relative = path.relative_to("src")
                test_dir = Path("tests") / relative.parent
                if (self._repo_path / test_dir).exists():
                    found = False
                    for glob_pat in ["*_test.py", "test_*.py"]:
                        for matched in (self._repo_path / test_dir).glob(glob_pat):
                            rel_path = str(Path("tests") / matched.relative_to(self._repo_path / "tests"))
                            if rel_path not in test_files:
                                test_files.append(rel_path)
                            found = True
                    if found:
                        continue

            # Tier 3: Module-level fallback — try the entire test directory
            if str(path).startswith("src/"):
                relative = path.relative_to("src")
                test_dir = Path("tests") / relative.parent
                if (self._repo_path / test_dir).exists():
                    test_files.append(str(test_dir))

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for f in test_files:
            if f not in seen:
                seen.add(f)
                deduped.append(f)

        return deduped

    def _validate_path(self, path_str: str) -> bool:
        """Check that a path resolves within the repo boundary.

        Uses the same pattern as edit_file's path traversal protection.
        """
        try:
            test_path = (self._repo_path / path_str).resolve()
            return str(test_path).startswith(str(self._repo_path))
        except (ValueError, OSError):
            return False
