# Phase 5: Verification &闭环 - Pattern Map

**Mapped:** 2026-05-25
**Files analyzed:** 11 (7 new, 4 modified)
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/ascend_agent/verification/__init__.py` | package_init | n/a | `src/ascend_agent/reproduction/__init__.py` | exact |
| `src/ascend_agent/verification/engine.py` | service/engine | CRUD + transform | `src/ascend_agent/reproduction/engine.py` | exact |
| `src/ascend_agent/cli/verify.py` | controller | request-response | `src/ascend_agent/cli/reproduce.py` | exact |
| `src/ascend_agent/diagnosis/models.py` (modify) | model | n/a | Existing models in same file | internal |
| `src/ascend_agent/tools/test_runner.py` (modify) | tool | CRUD | `src/ascend_agent/tools/shell_exec.py` | role-match |
| `src/ascend_agent/tools/server.py` (modify) | config/registration | n/a | Existing tool registrations in same file | internal |
| `src/ascend_agent/config.py` (modify) | config | n/a | Existing Field declarations in same file | internal |
| `tests/test_verification/__init__.py` | test_init | n/a | `tests/test_reproduction/__init__.py` | exact |
| `tests/test_verification/conftest.py` | test_fixture | n/a | `tests/test_reproduction/conftest.py` | exact |
| `tests/test_verification/test_engine.py` | test | n/a | `tests/test_reproduction/test_engine.py` | exact |
| `tests/test_verification/test_models.py` | test | n/a | `tests/test_reproduction/test_models.py` | exact |

## Pattern Assignments

---

### `src/ascend_agent/verification/__init__.py` (package_init)

**Analog:** `src/ascend_agent/reproduction/__init__.py`

**Pattern:** Empty file. This is the project convention for all subpackages (`reproduction/__init__.py` is 0 lines).

---

### `src/ascend_agent/verification/engine.py` (service/engine, CRUD + transform)

**Analog:** `src/ascend_agent/reproduction/engine.py`

**Imports pattern** (lines 1-17):
```python
"""Core verification engine — orchestrates test verification from reproduction.

The VerificationEngine runs a detect → map → execute → parse → report workflow,
calling exec_shell for test execution (local or remote via SSH),
and produces a structured VerificationResult.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path

from ascend_agent.config import Settings
from ascend_agent.diagnosis.models import ReproductionResult, VerificationResult
from ascend_agent.diagnosis.router import ModelRouter

logger = logging.getLogger(__name__)
```

**Constructor pattern** (lines 30-38 of `reproduction/engine.py` — exact same interface):
```python
class VerificationEngine:
    """Orchestrates test verification from reproduction results.

    Follows the Engine pattern: constructor stores dependencies,
    public verify() method runs the detect→map→execute→parse→report
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
```

**Public async method pattern** (lines 40-55 of `reproduction/engine.py` — async method returning structured Pydantic result):
```python
    async def verify(self, reproduction: ReproductionResult) -> VerificationResult:
        """Run the verification workflow. Returns a structured result.

        Workflow: detect framework → map test files → build command →
        execute via exec_shell → parse JSON → report.
        """
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
            )
```

**exec_shell usage pattern** (lines 86-92 of `reproduction/engine.py` — exact same import + call):
```python
        from ascend_agent.tools.shell_exec import exec_shell

        start = time.monotonic()
        result_json = await exec_shell(
            command, timeout=self._settings.test_timeout
        )
        duration = time.monotonic() - start
        result = json.loads(result_json)
```

**Error handling pattern** (lines 116-126 of `reproduction/engine.py` — try/except returning Pydantic result with error status):
```python
            except Exception as exc:
                logger.error("Verification failed: %s", exc)
                return VerificationResult(
                    status="error",
                    command=command,
                    stderr=str(exc),
                    exit_code=-1,
                    duration_seconds=0.0,
                    hypothesis_id_tested=i,
                    files_changed=[],
                )
```

**Logging pattern** (lines 96-103 of `reproduction/engine.py` — structured log with timing):
```python
                logger.info(
                    "Verifying hypothesis %d: %s → %s (%.2fs)",
                    ...,
                    command[:80],
                    result.get("status", "unknown"),
                    duration,
                )
```

**Path traversal protection pattern** (lines 166-175 of `reproduction/engine.py` — copy verbatim):
```python
    def _validate_path(self, path_str: str) -> bool:
        """Check that a path resolves within the repo boundary (D-10)."""
        try:
            resolved = Path(path_str).resolve()
            return str(resolved).startswith(str(self._repo_path))
        except (ValueError, OSError):
            return False
```

---

### `src/ascend_agent/cli/verify.py` (controller, request-response)

**Analog:** `src/ascend_agent/cli/reproduce.py`

**Imports pattern** (lines 1-11):
```python
import asyncio
import json
import sys

import typer
from rich.console import Console

from ascend_agent.config import settings
from ascend_agent.diagnosis.models import ReproductionResult, VerificationResult
from ascend_agent.diagnosis.router import ModelRouter
from ascend_agent.verification.engine import VerificationEngine

console = Console()
verify_app = typer.Typer(name="verify", help="Verify fixes by running relevant tests")
```

**CLI command pattern** (lines 17-21 of `reproduce.py`):
```python
@verify_app.command(name="run")
def verify_run(
    reproduction: str = typer.Argument(..., help="Path to reproduction result JSON"),
    output: str | None = typer.Option(None, "--output", "-o", help="Path to write verification result as JSON"),
):
    """Verify fixes by running tests against the changed files.

    Loads a reproduction JSON, auto-detects the test framework, maps changed
    files to test files, runs the relevant tests, and displays pass/fail results.
    """
```

**JSON loading pattern** (lines 28-39 of `reproduce.py`):
```python
    try:
        with open(reproduction) as f:
            data = f.read()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[red]Error:[/red] Failed to read reproduction JSON: {e}")
        raise typer.Exit(code=1)

    try:
        reproduction_result = ReproductionResult.model_validate_json(data)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to parse reproduction JSON: {e}")
        raise typer.Exit(code=1)
```

**Engine init + run pattern** (lines 42-56 of `reproduce.py`):
```python
    try:
        router = ModelRouter()
        engine = VerificationEngine(router=router, repo_path=repo_path, settings=settings)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    console.print("\n[bold cyan]Running verification...[/bold cyan]")
    try:
        result = asyncio.run(engine.verify(reproduction_result))
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
```

**Rich display pattern** (lines 58-68 of `reproduce.py` — adapt with `verification`-specific fields):
```python
    status_color = "green" if result.status == "pass" else "red"
    console.print(f"\n[bold]Verification Result[/bold]")
    console.print(f"Status: [{status_color}]{result.status}[/{status_color}]")
    console.print(f"Framework: [cyan]{result.framework}[/cyan]")
    console.print(f"Command: [cyan]{result.command}[/cyan]")
    console.print(f"Tests: {result.passed} passed, {result.failed} failed, {result.errors} errors")
    console.print(f"Exit code: {result.exit_code}")
    console.print(f"Duration: {result.duration_seconds:.2f}s")
```

**Output JSON pattern** (lines 70-73 of `reproduce.py` — verbatim):
```python
    if output is not None:
        with open(output, "w") as f:
            f.write(result.model_dump_json(indent=2))
        console.print(f"[green]Saved verification result to {output}[/green]")
```

**app.py registration pattern** (lines 15-20 of `src/ascend_agent/cli/app.py`):
```python
# Add to app.py imports:
from ascend_agent.cli.verify import verify_app

# Add to app.py after other registrations:
app.add_typer(verify_app)
```

---

### `src/ascend_agent/diagnosis/models.py` (model, modify — add VerificationResult + TestDetail)

**Analog:** Existing Pydantic models in the same file (`ReproductionResult` at lines 144-164, `Evidence` at lines 6-14, `Hypothesis` at lines 17-24)

**Model structure pattern** (Pydantic v2 with `ConfigDict(extra="forbid")`, `Field` constraints):
```python
class TestDetail(BaseModel):
    """Per-test detail from pytest-json-report output."""

    model_config = ConfigDict(extra="forbid")

    nodeid: str = Field(description="Pytest node ID (e.g., tests/test_foo.py::test_bar)")
    outcome: str = Field(description="Test outcome: passed, failed, error, skipped, xfailed, xpassed")
    duration: float | None = Field(default=None, description="Test duration in seconds")
    message: str | None = Field(default=None, description="Failure/error message if applicable")


class VerificationResult(BaseModel):
    """Structured verification result from test execution."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(
        pattern=r"^(pass|fail|error|timeout|no_tests)$",
        description="Overall verification status",
    )
    hypothesis_id_verified: int = Field(
        description="Index of hypothesis this verification addresses"
    )
    framework: str | None = Field(
        default=None, description="Detected test framework (e.g., 'pytest') or None if not found"
    )
    command: str = Field(description="The test command that was executed")
    summary: str = Field(description="Human-readable summary of verification results")
    tests_found: int = Field(default=0, description="Number of test files mapped")
    tests_run: int = Field(default=0, description="Number of tests actually executed")
    passed: int = Field(default=0)
    failed: int = Field(default=0)
    errors: int = Field(default=0)
    skipped: int = Field(default=0)
    xfailed: int = Field(default=0)
    xpassed: int = Field(default=0)
    tests: list[TestDetail] = Field(
        default_factory=list, description="Per-test details (empty if no tests)"
    )
    exit_code: int = Field(default=-1, description="pytest process exit code")
    duration_seconds: float = Field(ge=0.0, description="Wall-clock duration of test execution")
    files_tested: list[str] = Field(
        default_factory=list, description="Repo-relative paths of test files that were executed"
    )
    stdout: str = Field(default="", description="Raw test output (if parsing fails)")
```

**Insertion location:** After the `ReproductionResult` model (after line 164), before the `DiagnosisOutput` model (line 167). The `VerificationResult` is the Phase 5 output contract, living alongside Phase 4's `ReproductionResult`.

---

### `src/ascend_agent/tools/test_runner.py` (tool, CRUD) — MODIFY

**Analog:** `src/ascend_agent/tools/shell_exec.py`

**Current stub** (lines 1-10 — to be replaced):
```python
import json
from mcp.server.fastmcp import Context

async def run_test(command: str, path: str | None = None, ctx: Context | None = None) -> str:
    return json.dumps({
        "status": "stub",
        "message": "run_test not implemented in Phase 1. Full implementation planned for Phase 5 (Verification).",
    })
```

**Target pattern** — follows `exec_shell` (lines 1-69 of `shell_exec.py`):

**Imports pattern:**
```python
import asyncio
import json
import logging

from mcp.server.fastmcp import Context

from ascend_agent.tools.shell_exec import exec_shell

logger = logging.getLogger(__name__)
```

**Function signature pattern** (matches `exec_shell` lines 13):
```python
async def run_test(
    reproduction_json: str,
    repo_path: str | None = None,
    timeout: int = 300,
    ctx: Context | None = None,
) -> str:
    """Run relevant tests to verify fixes from a reproduction result.

    Accepts a ReproductionResult JSON string, maps changed files to test files,
    executes tests via exec_shell, and returns a VerificationResult as JSON.

    Args:
        reproduction_json: JSON string of the ReproductionResult from Phase 4
        repo_path: Path to the target repo (defaults to ASCEND_REPO_PATH or cwd)
        timeout: Timeout in seconds for test execution (default 300s)
        ctx: MCP context for tool-level logging

    Returns:
        JSON string of VerificationResult with pass/fail details
    """
```

**Core pattern** (orchestrates VerificationEngine, follows ReproductionEngine execution pattern):
```python
    from pathlib import Path
    from ascend_agent.config import Settings
    from ascend_agent.diagnosis.models import ReproductionResult
    from ascend_agent.diagnosis.router import ModelRouter
    from ascend_agent.verification.engine import VerificationEngine

    if repo_path is None:
        repo_path = Settings().repo_path or str(Path.cwd())

    try:
        reproduction = ReproductionResult.model_validate_json(reproduction_json)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "summary": f"Failed to parse reproduction JSON: {e}",
            "tests_found": 0,
            "tests_run": 0,
            "passed": 0,
            "failed": 0,
            "errors": 1,
        })

    router = ModelRouter()
    settings = Settings()
    settings.test_timeout = timeout

    engine = VerificationEngine(router=router, repo_path=repo_path, settings=settings)
    result = await engine.verify(reproduction)

    return result.model_dump_json()
```

---

### `src/ascend_agent/tools/server.py` (config/registration, modify) — INTERNAL

**Analog:** Existing tool registration lines 12-15

**Current line 15 to modify:**
```python
mcp.tool(name="run_test", description="[STUB] Run a test command — implemented in Phase 5")(run_test)
```

**Replace with (following line 14 pattern):**
```python
mcp.tool(name="run_test", description="Run relevant tests to verify fixes. Accepts a ReproductionResult JSON, maps changed files to test files, executes tests, and returns a VerificationResult as JSON with pass/fail details.")(run_test)
```

---

### `src/ascend_agent/config.py` (config, modify) — INTERNAL

**Analog:** Existing `shell_timeout` Field declaration at line 19

**Current Field pattern:**
```python
    shell_timeout: int = Field(default=60, ge=1, description="Default timeout in seconds for shell commands")
```

**Add after line 19 (following exact same pattern):**
```python
    test_timeout: int = Field(default=300, ge=1, description="Default timeout in seconds for test execution")
```

---

### `tests/test_verification/__init__.py` (test_init)

**Analog:** `tests/test_reproduction/__init__.py`

**Pattern:** Empty file (0 bytes). Project convention — all test subpackages use empty `__init__.py`.

---

### `tests/test_verification/conftest.py` (test_fixture)

**Analog:** `tests/test_reproduction/conftest.py`

**Imports pattern** (lines 1-10):
```python
import os

import pytest
from unittest.mock import Mock

from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    Evidence,
    Hypothesis,
    ReproductionResult,
    VerificationResult,
    TestDetail,
)
```

**mock_router fixture** (lines 13-17 of `test_reproduction/conftest.py` — verbatim):
```python
@pytest.fixture
def mock_router():
    mock = Mock()
    mock.completion = Mock()
    return mock
```

**mock_settings fixture** (lines 57-63 of `test_reproduction/conftest.py` — extend with `test_timeout`):
```python
@pytest.fixture
def mock_settings():
    mock = Mock()
    mock.shell_timeout = 10
    mock.test_timeout = 30
    mock.ssh_host = ""
    mock.ssh_user = ""
    mock.ssh_key_path = ""
    return mock
```

**sample_reproduction fixture** (new, following `sample_diagnosis` pattern at lines 21-39):
```python
@pytest.fixture
def sample_reproduction():
    return ReproductionResult(
        status="success",
        command="python -m pytest tests/test_shell_exec.py",
        stdout="1 passed",
        stderr="",
        exit_code=0,
        duration_seconds=1.5,
        hypothesis_id_tested=0,
        files_changed=["src/ascend_agent/tools/shell_exec.py"],
    )
```

**sample_repo_dir fixture** (lines 42-53 of `test_reproduction/conftest.py` — adapt for test verification):
```python
@pytest.fixture
def sample_repo_dir(tmp_path):
    """Create a temporary repo with pytest config and sample test files."""
    # pytest config
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[tool.pytest.ini_options]\n"
        "testpaths = ['tests']\n"
        "asyncio_mode = 'auto'\n"
    )
    # Source files
    src_dir = tmp_path / "src" / "mypkg"
    src_dir.mkdir(parents=True)
    (src_dir / "core.py").write_text("def add(a, b): return a + b\n")
    # Test files (matching convention: src/mypkg/core.py → tests/test_core.py)
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_core.py").write_text(
        "from src.mypkg.core import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
    )
    return tmp_path
```

---

### `tests/test_verification/test_engine.py` (test)

**Analog:** `tests/test_reproduction/test_engine.py`

**Imports pattern** (lines 1-7):
```python
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ascend_agent.diagnosis.models import ReproductionResult, VerificationResult
from ascend_agent.verification.engine import VerificationEngine
```

**Test class structure** (lines 10-11 of `test_reproduction/test_engine.py`):
```python
class TestVerificationEngine:
```

**Constructor test** (lines 11-15 of `test_reproduction/test_engine.py`):
```python
    def test_constructor_stores_dependencies(self, mock_router, mock_settings, tmp_path):
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        assert engine._router is mock_router
        assert engine._repo_path == tmp_path.resolve()
        assert engine._settings is mock_settings
```

**Async execution test with patching** (lines 26-36 of `test_reproduction/test_engine.py`):
```python
    @pytest.mark.asyncio
    async def test_verify_handles_exec_shell_failure(
        self, mock_router, mock_settings, sample_reproduction, tmp_path
    ):
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        with patch(
            "ascend_agent.verification.engine.exec_shell", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.side_effect = RuntimeError("execution failed")
            result = await engine.verify(sample_reproduction)
            assert result.status == "error"
            assert "execution failed" in result.stderr
```

**Edge case tests** (lines 67-77 of `test_reproduction/test_engine.py` — adapt for verification):
```python
    def test_verify_no_files_changed(self, mock_router, mock_settings, tmp_path):
        empty_reproduction = ReproductionResult(
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
        async def run():
            return await engine.verify(empty_reproduction)
        result = asyncio.run(run())
        assert result.status == "no_tests"
```

**Mock integration test** (lines 17-23 of `test_reproduction/test_engine.py`):
```python
    @pytest.mark.asyncio
    async def test_verify_returns_result(
        self, mock_router, mock_settings, sample_reproduction, tmp_path
    ):
        engine = VerificationEngine(mock_router, str(tmp_path), mock_settings)
        result = await engine.verify(sample_reproduction)
        assert result.status in ("pass", "fail", "error", "no_tests")
```

---

### `tests/test_verification/test_models.py` (test)

**Analog:** `tests/test_reproduction/test_models.py`

**Imports pattern** (lines 1-3 of `test_reproduction/test_models.py`):
```python
import pytest
from pydantic import ValidationError
```

**Valid model test** (lines 5-20 of `test_reproduction/test_models.py`):
```python
def test_verification_result_valid():
    from ascend_agent.diagnosis.models import VerificationResult, TestDetail

    r = VerificationResult(
        status="pass",
        hypothesis_id_verified=0,
        framework="pytest",
        command="python -m pytest tests/test_core.py --json-report --json-report-file=none",
        summary="All tests passed",
        tests_found=1,
        tests_run=1,
        passed=1,
        failed=0,
        errors=0,
        skipped=0,
        xfailed=0,
        xpassed=0,
        tests=[
            TestDetail(
                nodeid="tests/test_core.py::test_add",
                outcome="passed",
                duration=0.01,
            )
        ],
        exit_code=0,
        duration_seconds=2.5,
        files_tested=["tests/test_core.py"],
    )
    assert r.status == "pass"
    assert r.passed == 1
    assert r.failed == 0
```

**Invalid status test** (lines 22-35 of `test_reproduction/test_models.py`):
```python
def test_verification_result_invalid_status():
    from ascend_agent.diagnosis.models import VerificationResult

    with pytest.raises(ValidationError):
        VerificationResult(
            status="invalid_status",
            hypothesis_id_verified=0,
            command="echo test",
            summary="should fail",
            duration_seconds=0.0,
        )
```

**Forbids extra fields test** (lines 38-51 of `test_reproduction/test_models.py`):
```python
def test_verification_result_forbids_extra():
    from ascend_agent.diagnosis.models import VerificationResult

    with pytest.raises(ValidationError):
        VerificationResult(
            status="pass",
            hypothesis_id_verified=0,
            command="echo test",
            summary="should fail",
            duration_seconds=0.0,
            extra_field="should fail",
        )
```

**Defaults test** (lines 54-66 of `test_reproduction/test_models.py`):
```python
def test_verification_result_defaults():
    from ascend_agent.diagnosis.models import VerificationResult

    r = VerificationResult(
        status="no_tests",
        hypothesis_id_verified=0,
        command="",
        summary="No tests to run",
        duration_seconds=0.0,
    )
    assert r.tests_found == 0
    assert r.tests_run == 0
    assert r.passed == 0
    assert r.failed == 0
    assert r.errors == 0
    assert r.exit_code == -1
    assert r.files_tested == []
    assert r.stdout == ""
```

**Duration negative test** (lines 69-78 of `test_reproduction/test_models.py`):
```python
def test_verification_result_duration_negative_rejected():
    from ascend_agent.diagnosis.models import VerificationResult

    with pytest.raises(ValidationError):
        VerificationResult(
            status="pass",
            hypothesis_id_verified=0,
            command="echo test",
            summary="should fail",
            duration_seconds=-0.1,
        )
```

**TestDetail model test** (new, following `Evidence` test pattern from `tests/test_diagnosis/test_models.py`):
```python
def test_test_detail_valid():
    from ascend_agent.diagnosis.models import TestDetail

    td = TestDetail(
        nodeid="tests/test_core.py::test_add",
        outcome="passed",
        duration=0.01,
        message=None,
    )
    assert td.nodeid == "tests/test_core.py::test_add"
    assert td.outcome == "passed"
    assert td.duration == 0.01
    assert td.message is None

def test_test_detail_forbids_extra():
    from ascend_agent.diagnosis.models import TestDetail

    with pytest.raises(ValidationError):
        TestDetail(
            nodeid="tests/test_core.py::test_add",
            outcome="passed",
            extra_field="should fail",
        )
```

---

## Shared Patterns

### Engine Pattern
**Source:** `src/ascend_agent/reproduction/engine.py` (all lines)
**Apply to:** `src/ascend_agent/verification/engine.py`

All engines in the project follow the same convention:
- Constructor: `__init__(self, router: ModelRouter, repo_path: str, settings: Settings | None = None)`
- Public method is async, takes a Pydantic input, returns a structured Pydantic result
- `self._router`, `self._repo_path = Path(repo_path).resolve()`, `self._settings = settings or Settings()`
- Error handling returns structured Pydantic result (never raises exceptions out of public method)
- `time.monotonic()` for wall-clock duration measurement
- Lazy import `from ascend_agent.tools.shell_exec import exec_shell` inside the method body

### MCP Tool Pattern
**Source:** `src/ascend_agent/tools/shell_exec.py` (entire file)
**Apply to:** `src/ascend_agent/tools/test_runner.py`

All MCP tools follow the same convention:
- `async def tool_name(args, ctx: Context | None = None) -> str`
- Return JSON strings (`json.dumps({...})` or `model.model_dump_json()`)
- `Context` object used for logging (`ctx.info()`) — optional, None-safe
- `logger = logging.getLogger(__name__)` for module-level logging
- Local subprocess execution via `asyncio.create_subprocess_shell()`

### CLI Pattern (Typer + Rich)
**Source:** `src/ascend_agent/cli/reproduce.py` (entire file)
**Apply to:** `src/ascend_agent/cli/verify.py`

All CLI subcommands follow the same convention:
- `from rich.console import Console` → `console = Console()`
- `typer.Typer(name="...", help="...")` for subcommand app
- `@app.command(name="run")` wrapping a sync function
- `asyncio.run(engine.method(...))` for calling async engines
- Rich output: `console.print(f"[color]message[/color]")`, `[red]Error:[/red]`, `[green]success[/green]`
- `--output/-o` flag for JSON persistence: `result.model_dump_json(indent=2)`
- `raise typer.Exit(code=1)` for error exits
- `raise typer.Exit()` after `--help` on no-arg invocation

### Pydantic Model Pattern
**Source:** `src/ascend_agent/diagnosis/models.py` (all models)
**Apply to:** `VerificationResult`, `TestDetail` (added to same file)

All Pydantic models follow:
- `from __future__ import annotations` at top of file
- `model_config = ConfigDict(extra="forbid")` on every model
- `Field(description=...)` with explicit docs on every field
- `Field(ge=...)` and `Field(pattern=r"^...$")` for validation
- `Field(default_factory=list)` for default empty lists
- `| None` (PEP 604 union syntax) for optional fields

### Test Patterns
**Source:** `tests/test_reproduction/` (entire directory)
**Apply to:** `tests/test_verification/` (entire directory)

All test modules follow:
- `pytest.mark.asyncio` decorator for async test methods
- `from unittest.mock import Mock, AsyncMock, patch`
- Fixtures in `conftest.py` scoped `function` or `session`
- Test classes: `class TestXxxEngine:` or standalone functions
- `from ascend_agent.xxx.models import XxxResult` — imports inside test functions (not top-level, for late-binding to avoid import-time validation errors)
- `pytest.raises(ValidationError)` for model validation tests
- `tmp_path` fixture (built-in) for temporary directories
- `monkeypatch` fixture for environment variable manipulation

### Path Traversal Protection
**Source:** `src/ascend_agent/reproduction/engine.py` lines 166-175
**Apply to:** `src/ascend_agent/verification/engine.py`

```python
def _validate_path(self, path_str: str) -> bool:
    try:
        resolved = Path(path_str).resolve()
        return str(resolved).startswith(str(self._repo_path))
    except (ValueError, OSError):
        return False
```

### Error Handling
**Source:** `src/ascend_agent/reproduction/engine.py` lines 116-126
**Apply to:** `src/ascend_agent/verification/engine.py`

All engines return structured error Pydantic results instead of raising exceptions:
```python
except Exception as exc:
    logger.error("Operation failed: %s", exc)
    return XxxResult(
        status="error",
        ...
        stderr=str(exc),
    )
```

---

## No Analog Found

All 11 files have close analogs in the existing codebase. No files fall into the "no analog" category.

---

## Metadata

**Analog search scope:**
- `src/ascend_agent/reproduction/` — Engine pattern, package init
- `src/ascend_agent/cli/` — CLI pattern, app registration
- `src/ascend_agent/tools/` — MCP tool pattern, server registration
- `src/ascend_agent/diagnosis/models.py` — Pydantic model patterns
- `src/ascend_agent/config.py` — Settings Field patterns
- `tests/test_reproduction/` — Test fixtures, engine tests, model tests
- `tests/test_diagnosis/test_models.py` — Model validation test patterns

**Files scanned:** 23 (all existing project Python files + test files)
**Pattern extraction date:** 2026-05-25
