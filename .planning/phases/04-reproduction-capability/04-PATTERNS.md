# Phase 4: Reproduction Capability - Pattern Map

**Mapped:** 2026-05-25
**Files analyzed:** 12 new/modified files
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/ascend_agent/tools/shell_exec.py` (MODIFY) | MCP tool | request-response (async→JSON) | `src/ascend_agent/tools/file_edit.py` | exact |
| `src/ascend_agent/reproduction/__init__.py` (NEW) | package marker | N/A | N/A (boilerplate) | N/A |
| `src/ascend_agent/reproduction/engine.py` (NEW) | engine orchestrator | workflow (prepare→execute→report) | `src/ascend_agent/diagnosis/engine.py` | exact |
| `src/ascend_agent/diagnosis/models.py` (MODIFY) | Pydantic model | CRUD (data structure) | `src/ascend_agent/diagnosis/models.py` (same file) | exact (same file) |
| `src/ascend_agent/config.py` (MODIFY) | settings config | N/A (configuration) | `src/ascend_agent/config.py` (same file) | exact (same file) |
| `src/ascend_agent/cli/reproduce.py` (MODIFY) | CLI command (Typer) | request-response | `src/ascend_agent/cli/fix.py` | exact |
| `pyproject.toml` (MODIFY) | build config | N/A | `pyproject.toml` (same file) | exact (same file) |
| `tests/test_tools/test_shell_exec.py` (NEW) | test (pytest) | request-response (async tool) | `tests/test_tools/test_file_edit.py` | exact |
| `tests/test_reproduction/__init__.py` (NEW) | package marker | N/A | `tests/test_diagnosis/__init__.py` | exact |
| `tests/test_reproduction/conftest.py` (NEW) | test fixtures | N/A | `tests/test_diagnosis/conftest.py` | exact |
| `tests/test_reproduction/test_engine.py` (NEW) | test (pytest) | workflow | `tests/test_diagnosis/test_engine.py` | exact |
| `tests/test_reproduction/test_models.py` (NEW) | test (pytest) | CRUD (model validation) | `tests/test_diagnosis/test_models.py` | exact |

## Pattern Assignments

---

### 1. `src/ascend_agent/tools/shell_exec.py` (MCP tool, request-response)

**Analog:** `src/ascend_agent/tools/file_edit.py`

**Imports pattern** (lines 1-5):
```python
import json
from pathlib import Path

from mcp.server.fastmcp import Context
from pydantic import BaseModel, ConfigDict, Field
```

**New imports for shell_exec** (copy pattern, adapt to asyncssh + asyncio):
```python
# file_edit imports json, Path, Context — shell_exec also needs these
# ADD for shell_exec:
import asyncio
import os
import logging

# CONDITIONAL import (only when SSH path is taken, avoid import errors if not installed):
# import asyncssh  — import inside _exec_remote function body
```

**Core MCP tool pattern** (lines 21-26 of file_edit.py):
```python
async def exec_shell(
    command: str,
    timeout: int = 60,
    ctx: Context | None = None,
) -> str:
    """Execute a shell command locally or via SSH.

    Returns JSON string with keys: status, stdout, stderr, exit_code.
    """
    # ... implementation
```

**Return JSON pattern** (lines 35-38 of file_edit.py):
```python
# Every MCP tool returns json.dumps({...}) string
return json.dumps({
    "status": "error",
    "error": "...",
})
```

For shell_exec, the success pattern:
```python
return json.dumps({
    "status": "success",  # or "fail", or "error"
    "stdout": "...",
    "stderr": "...",
    "exit_code": 0,
})
```

**Error handling pattern** (lines 130-138 of file_edit.py):
```python
except OSError as e:
    return json.dumps({
        "status": "error",
        "error": str(e),
    })
except Exception as e:
    return json.dumps({
        "status": "error",
        "error": f"Unexpected error: {e}",
    })
```

For shell_exec, extend with asyncssh-specific errors:
```python
except asyncssh.Error as e:
    return json.dumps({
        "status": "error",
        "stdout": "",
        "stderr": f"SSH error: {e}",
        "exit_code": -1,
    })
except asyncio.TimeoutError:
    return json.dumps({
        "status": "error",
        "stdout": "",
        "stderr": f"Command timed out after {timeout}s",
        "exit_code": -1,
    })
```

**Path traversal protection pattern** (lines 50-59 of file_edit.py — D-10 reference):
```python
# Copy this pattern for safety validation
path = Path(file_path).resolve()

if repo_path is not None:
    resolved_repo = Path(repo_path).resolve()
    if not str(path).startswith(str(resolved_repo)):
        return json.dumps({
            "status": "error",
            "error": f"Path {file_path} resolves outside repository root",
        })
```

**MCP tool registration** (`src/ascend_agent/tools/server.py`, lines 12-14):
```python
# Already registered — no change needed to server.py:
mcp.tool(name="exec_shell", description="...")(exec_shell)
# Update the description string from "[STUB]..." to actual description
```

---

### 2. `src/ascend_agent/reproduction/__init__.py` (package marker)

**Analog:** `src/ascend_agent/diagnosis/__init__.py` (package marker — empty file)

**Pattern:** Empty file. No code needed. The planner knows this is boilerplate.

---

### 3. `src/ascend_agent/reproduction/engine.py` (engine orchestrator, workflow)

**Analog:** `src/ascend_agent/diagnosis/engine.py`

**Module docstring pattern** (lines 1-6):
```python
"""Core reproduction engine — orchestrates issue reproduction from diagnosis.

The ReproductionEngine runs a prepare → execute → report workflow,
calling exec_shell for command execution (local or remote via SSH),
and produces a structured ReproductionResult for Phase 5 consumption.
"""
```

**Imports pattern** (lines 8-18):
```python
import asyncio
import logging
from pathlib import Path

from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    ReproductionResult,
)
from ascend_agent.diagnosis.router import ModelRouter
from ascend_agent.config import Settings

logger = logging.getLogger(__name__)
```

**Engine class pattern (constructor)** (lines 161-171 of engine.py):
```python
class ReproductionEngine:
    """Orchestrates issue reproduction from diagnosis hypotheses."""

    def __init__(self, router: ModelRouter, repo_path: str, settings: Settings | None = None):
        self._router = router
        self._repo_path = Path(repo_path).resolve()
        self._settings = settings or Settings()
```

**Public API method pattern** (lines 175-231 of engine.py, `diagnose()`):
```python
async def reproduce(self, diagnosis: DiagnosisResult) -> ReproductionResult:
    """Run the reproduction workflow. Returns structured ReproductionResult."""
    # Step 1: prepare (D-13, D-14)
    # Step 2: execute (D-03) — for each hypothesis, call exec_shell
    # Step 3: report (D-11)
    # ...
    return result
```

**Error handling pattern** (lines 262-283 of engine.py, `_generate_hypotheses`):
```python
try:
    # ... main logic
    result = await self._execute_command(command, timeout)
except Exception as exc:
    logger.error("Reproduction failed: %s", exc)
    result = ReproductionResult(
        status="error",
        command=command,
        stdout="",
        stderr=str(exc),
        exit_code=-1,
        duration_seconds=0,
        hypothesis_id_tested=-1,
        files_changed=[],
    )
```

**Logging pattern** (lines 186-188 of engine.py):
```python
logger.info("Reproducing hypothesis %d/%d", i + 1, len(diagnosis.hypotheses))
```

---

### 4. `src/ascend_agent/diagnosis/models.py` — add ReproductionResult (Pydantic model)

**Analog:** `src/ascend_agent/diagnosis/models.py` (same file — lines 62-77, `DiagnosisResult`)

**Add new model after existing models.** Follow the exact conventions:

**Model config pattern** (line 9 of models.py):
```python
model_config = ConfigDict(extra="forbid")
```

**Field definition pattern** (lines 11-14, 22-24):
```python
root_cause: str = Field(description="What went wrong — concise statement of the root cause")
evidence: list[Evidence] = Field(description="Supporting evidence items (file:line + code snippets)")
confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0 to 1.0")
```

**Status field with regex validation pattern** (line 41-43, `SearchDecision.action`):
```python
status: str = Field(
    pattern=r"^(success|fail|error)$",
    description="Outcome: success (exit 0), fail (non-zero exit), error (execution failure)",
)
```

**New ReproductionResult model** (add after `FixGenerationResult`, before `DiagnosisOutput`, around line 142):
```python
class ReproductionResult(BaseModel):
    """Structured result from reproduction execution (D-11, D-12)."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(
        pattern=r"^(success|fail|error)$",
        description="Outcome: success (exit 0), fail (non-zero exit), error (execution failure)",
    )
    command: str = Field(description="The command that was executed")
    stdout: str = Field(default="", description="Standard output captured")
    stderr: str = Field(default="", description="Standard error captured")
    exit_code: int = Field(default=-1, description="Process exit code")
    duration_seconds: float = Field(ge=0.0, description="Wall-clock duration of command execution")
    hypothesis_id_tested: int = Field(
        ge=-1, description="Index of hypothesis this test addresses (-1 if none)"
    )
    files_changed: list[str] = Field(
        default_factory=list,
        description="List of repo-relative paths to files modified during reproduction",
    )
```

**Import pattern:** No new imports needed — `BaseModel`, `ConfigDict`, `Field` already imported at line 3.

---

### 5. `src/ascend_agent/config.py` — add SSH settings (settings config)

**Analog:** `src/ascend_agent/config.py` (same file — lines 7-15)

**Existing Settings class for reference:**
```python
# Lines 7-21 of config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASCEND_")

    python_version: str = ""
    platform: str = ""
    env_vars: dict[str, str] = {}
    repo_path: str | None = None
    mcp_server_command: str = "python -m ascend_agent.tools.server"

    def model_post_init(self, __context):
        self.python_version = sys.version
        self.platform = sys.platform
        self.env_vars = dict(os.environ)
```

**Add new SSH fields after `mcp_server_command` and before `model_post_init`** (after line 14):
```python
    # SSH configuration (D-06)
    ssh_host: str = Field(default="", description="SSH hostname for remote execution")
    ssh_user: str = Field(default="", description="SSH username for remote execution")
    ssh_key_path: str = Field(default="", description="Path to SSH private key file")
    shell_timeout: int = Field(default=60, ge=1, description="Default timeout in seconds for shell commands")
```

**Import addition needed** (add `Field` to existing import at line 4):
```python
# Change line 4 from:
from pydantic_settings import BaseSettings, SettingsConfigDict
# To:
from pydantic import Field as PydanticField
from pydantic_settings import BaseSettings, SettingsConfigDict
```

**Important:** `Field` is already imported from pydantic in `models.py`. In `config.py`, the existing Settings class doesn't use `Field` yet — the new SSH fields need it. Use a distinct alias (e.g., `PydanticField`) to avoid confusion, or just use `from pydantic import Field`.

**`ASCEND_` prefix pattern** (line 8): The `env_prefix="ASCEND_"` means `ssh_host` is read from `ASCEND_SSH_HOST`, `ssh_user` from `ASCEND_SSH_USER`, etc. No extra mapping needed.

---

### 6. `src/ascend_agent/cli/reproduce.py` (CLI command, request-response)

**Analog:** `src/ascend_agent/cli/fix.py` — best match (newer, same pattern: loads JSON → dispatches to Engine → displays result)

**Imports pattern** (lines 1-17 of fix.py):
```python
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from ascend_agent.config import settings
from ascend_agent.diagnosis.models import DiagnosisOutput, ReproductionResult
from ascend_agent.diagnosis.router import ModelRouter
from ascend_agent.reproduction.engine import ReproductionEngine

console = Console()
reproduce_app = typer.Typer(name="reproduce", help="Reproduce an issue from a diagnosis")
```

**Command definition pattern** (lines 23-29 of fix.py):
```python
@reproduce_app.command(name="run")
def reproduce_run(
    diagnosis: str = typer.Argument(..., help="Path to diagnosis JSON file"),
    output: str | None = typer.Option(None, "--output", help="Path to write reproduction result as JSON"),
):
    """Reproduce diagnosed issues by executing reproduction commands."""
```

**JSON loading + validation pattern** (lines 33-46 of fix.py):
```python
try:
    if diagnosis is not None:
        with open(diagnosis) as f:
            data = f.read()
    elif not sys.stdin.isatty():
        data = sys.stdin.read()
    else:
        console.print("[red]Error:[/red] No diagnosis input provided.")
        raise typer.Exit(code=1)

    diagnosis_output = DiagnosisOutput.model_validate_json(data)
except (json.JSONDecodeError, Exception) as e:
    console.print(f"[red]Error:[/red] Failed to parse diagnosis JSON: {e}")
    raise typer.Exit(code=1)
```

**Repo path extraction pattern** (line 49 of fix.py):
```python
repo_path = diagnosis_output.context_doc.repo.path
```

**Engine initialization pattern** (lines 52-60 of fix.py):
```python
try:
    router = ModelRouter()
    engine = ReproductionEngine(router=router, repo_path=repo_path, settings=settings)
except ValueError as e:
    console.print(f"[red]Error:[/red] {e}")
    console.print("[yellow]Hint: Set the OPENAI_API_KEY environment variable.[/yellow]")
    raise typer.Exit(code=1)
```

**Result display pattern** (lines 63-75, `_display_fix_summary` in fix.py, simplified for reproduce):
```python
console.print("\n[bold cyan]Running reproduction...[/bold cyan]")
try:
    result = engine.reproduce(diagnosis_output.diagnosis_result)
except ValueError as e:
    console.print(f"[red]Error:[/red] {e}")
    raise typer.Exit(code=1)

# Display result
console.print(f"\n[bold]Reproduction Result[/bold]")
console.print(f"Status: [{'green' if result.status == 'success' else 'red'}]{result.status}[/]")
console.print(f"Command: {result.command}")
console.print(f"Exit code: {result.exit_code}")
console.print(f"Duration: {result.duration_seconds:.2f}s")
if result.stdout:
    console.print(f"\n[bold]stdout:[/bold]\n{result.stdout}")
if result.stderr:
    console.print(f"\n[bold red]stderr:[/bold red]\n{result.stderr}")
```

**Output saving pattern** (lines 85-89 of fix.py):
```python
if output is not None:
    with open(output, "w") as f:
        f.write(result.model_dump_json(indent=2))
    console.print(f"[green]Saved reproduction result to {output}[/green]")
```

---

### 7. `pyproject.toml` — add asyncssh dependency (build config)

**Analog:** `pyproject.toml` (same file)

**Existing dependencies section** (lines 10-17):
```toml
dependencies = [
    "mcp>=1.27.1",
    "openai>=2.37.0",
    "typer>=0.25.0",
    "rich>=15.0.0",
    "pydantic>=2.13.0",
    "pydantic-settings>=2.14.0",
]
```

**Edit to add asyncssh** (insert after pydantic-settings, before closing bracket):
```toml
dependencies = [
    "mcp>=1.27.1",
    "openai>=2.37.0",
    "typer>=0.25.0",
    "rich>=15.0.0",
    "pydantic>=2.13.0",
    "pydantic-settings>=2.14.0",
    "asyncssh>=2.23.0",
]
```

---

### 8. `tests/test_tools/test_shell_exec.py` (test, async tool)

**Analog:** `tests/test_tools/test_file_edit.py`

**Imports pattern** (lines 1-3):
```python
import json

import pytest
```

**Test function pattern** (lines 6-7, decorated async test):
```python
@pytest.mark.asyncio
async def test_exec_local_returns_json(tmp_path):
    """exec_shell returns valid JSON with status/stdout/stderr/exit_code for local execution."""
    from ascend_agent.tools.shell_exec import exec_shell

    result = json.loads(await exec_shell(command="echo hello", timeout=10))

    assert "status" in result
    assert "stdout" in result
    assert "stderr" in result
    assert "exit_code" in result
    assert result["status"] in ("success", "fail", "error")
```

**Test structure pattern** — plain functions (no test classes), use `tmp_path` fixture, `json.loads()` for result parsing:
```python
@pytest.mark.asyncio
async def test_exec_local_success(tmp_path):
    """Verify local command execution returns success with expected output."""
    from ascend_agent.tools.shell_exec import exec_shell

    result = json.loads(await exec_shell(command="echo hello", timeout=10))

    assert result["status"] == "success"
    assert "hello" in result["stdout"]
    assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_exec_local_failure(tmp_path):
    """Verify failed command returns fail status with non-zero exit code."""
    from ascend_agent.tools.shell_exec import exec_shell

    result = json.loads(await exec_shell(command="exit 1", timeout=10))

    assert result["status"] == "fail"
    assert result["exit_code"] == 1


@pytest.mark.asyncio
async def test_exec_local_timeout(tmp_path):
    """Verify slow command times out with status=error."""
    from ascend_agent.tools.shell_exec import exec_shell

    result = json.loads(await exec_shell(command="sleep 30", timeout=1))

    assert result["status"] == "error"
    assert "timed out" in result["stderr"].lower()
    assert result["exit_code"] == -1


@pytest.mark.asyncio
async def test_exec_ssh_routing(monkeypatch):
    """Verify SSH path is triggered when ASCEND_SSH_HOST is set (mocked)."""
    from ascend_agent.tools.shell_exec import exec_shell
    from unittest.mock import AsyncMock, patch

    monkeypatch.setenv("ASCEND_SSH_HOST", "testhost.example.com")
    monkeypatch.setenv("ASCEND_SSH_USER", "testuser")

    with patch("ascend_agent.tools.shell_exec._exec_remote", new_callable=AsyncMock) as mock_remote:
        mock_remote.return_value = json.dumps({
            "status": "success", "stdout": "ok", "stderr": "", "exit_code": 0,
        })
        result = json.loads(await exec_shell(command="echo test", timeout=10))
        mock_remote.assert_called_once()
        assert result["status"] == "success"


@pytest.mark.asyncio
async def test_exec_invalid_command(tmp_path):
    """Verify command not found returns error status."""
    from ascend_agent.tools.shell_exec import exec_shell

    result = json.loads(await exec_shell(command="nonexistent_command_xyz", timeout=10))

    assert result["status"] == "error"
```

---

### 9. `tests/test_reproduction/__init__.py` (package marker)

**Analog:** `tests/test_diagnosis/__init__.py`

**Pattern:** Empty file. Boilerplate only.

---

### 10. `tests/test_reproduction/conftest.py` (test fixtures)

**Analog:** `tests/test_diagnosis/conftest.py`

**Imports pattern** (lines 1-18):
```python
import logging
from pathlib import Path

import pytest
from unittest.mock import Mock

from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    Hypothesis,
    Evidence,
)
```

**Fixture: mock_router** (lines 87-95):
```python
@pytest.fixture(scope="function")
def mock_router() -> Mock:
    """Returns a Mock that replaces ModelRouter.

    Tests set .completion.side_effect to control return values per call.
    """
    router = Mock()
    router.completion = Mock()
    return router
```

**New fixtures for reproduction tests:**

```python
@pytest.fixture(scope="function")
def sample_diagnosis() -> DiagnosisResult:
    """Creates a DiagnosisResult with one hypothesis for reproduction testing."""
    return DiagnosisResult(
        hypotheses=[
            Hypothesis(
                root_cause="Config mismatch in dimension parsing",
                evidence=[
                    Evidence(
                        file_path="tests/test_dim.py",
                        line_number=42,
                        code_snippet="def test_dimensions():\n    assert dim == 4096",
                        relevance="This test reproduces the dimension mismatch error",
                    ),
                ],
                confidence=0.85,
            ),
        ],
        errors=[],
        iterations_used=2,
    )


@pytest.fixture(scope="function")
def sample_repo_dir(tmp_path: Path) -> Path:
    """Creates a minimal test repo with Python files."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_dim.py").write_text(
        "import os\n\ndef test_dimensions():\n    dim = int(os.environ.get('DIM', '4096'))\n    assert dim == 4096, f'Expected 4096, got {dim}'\n"
    )
    return tmp_path


@pytest.fixture(scope="function")
def mock_settings() -> Mock:
    """Returns a Mock Settings with default values for reproduction tests."""
    settings = Mock()
    settings.shell_timeout = 10
    settings.ssh_host = ""
    settings.ssh_user = ""
    settings.ssh_key_path = ""
    return settings
```

---

### 11. `tests/test_reproduction/test_engine.py` (test, engine workflow)

**Analog:** `tests/test_diagnosis/test_engine.py`

**Imports pattern** (lines 1-13):
```python
"""Tests for the ReproductionEngine class."""

from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

import pytest

from ascend_agent.reproduction.engine import ReproductionEngine
from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    ReproductionResult,
)
```

**Test class structure pattern** (lines 61-63):
```python
class TestReproductionEngine:
    """Tests for the ReproductionEngine class."""

    def test_constructor_stores_dependencies(self, mock_router, mock_settings, tmp_path: Path):
        """ReproductionEngine.__init__ stores router, repo_path, and settings."""
        engine = ReproductionEngine(
            router=mock_router,
            repo_path=str(tmp_path),
            settings=mock_settings,
        )
        assert engine._router is mock_router
        assert engine._repo_path == tmp_path.resolve()
        assert engine._settings is mock_settings
```

**Async test pattern** (use `@pytest.mark.asyncio` — same as tools):
```python
@pytest.mark.asyncio
async def test_reproduce_returns_result(self, mock_router, mock_settings, sample_diagnosis, tmp_path: Path):
    """ReproductionEngine.reproduce() returns ReproductionResult for valid diagnosis."""
    engine = ReproductionEngine(
        router=mock_router,
        repo_path=str(tmp_path),
        settings=mock_settings,
    )

    result = await engine.reproduce(sample_diagnosis)

    assert isinstance(result, ReproductionResult)
    assert result.status in ("success", "fail", "error")
```

**Mock patching pattern** (lines 92-98 of test_engine.py):
```python
@pytest.mark.asyncio
async def test_engine_handles_exec_shell_failure(self, mock_router, mock_settings, sample_diagnosis, tmp_path: Path):
    """ReproductionEngine handles exec_shell failure gracefully."""
    engine = ReproductionEngine(
        router=mock_router,
        repo_path=str(tmp_path),
        settings=mock_settings,
    )

    with patch("ascend_agent.reproduction.engine.exec_shell", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = RuntimeError("execution failed")
        result = await engine.reproduce(sample_diagnosis)

    assert result.status == "error"
    assert "execution failed" in result.stderr
```

**Venv detection tests:**
```python
def test_detect_venv_virtualenv(self, mock_router, mock_settings, tmp_path: Path, monkeypatch):
    """_detect_venv detects VIRTUAL_ENV env var."""
    monkeypatch.setenv("VIRTUAL_ENV", "/fake/venv")

    engine = ReproductionEngine(
        router=mock_router,
        repo_path=str(tmp_path),
        settings=mock_settings,
    )

    venv_env = engine._detect_venv()
    assert venv_env["VIRTUAL_ENV"] == "/fake/venv"


def test_detect_venv_conda(self, mock_router, mock_settings, tmp_path: Path, monkeypatch):
    """_detect_venv detects CONDA_PREFIX env var."""
    monkeypatch.setenv("CONDA_PREFIX", "/opt/conda/envs/test")

    engine = ReproductionEngine(
        router=mock_router,
        repo_path=str(tmp_path),
        settings=mock_settings,
    )

    venv_env = engine._detect_venv()
    assert venv_env["CONDA_PREFIX"] == "/opt/conda/envs/test"


def test_detect_venv_none(self, mock_router, mock_settings, tmp_path: Path, monkeypatch):
    """_detect_venv returns empty dict when no venv is active."""
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.delenv("CONDA_PREFIX", raising=False)

    engine = ReproductionEngine(
        router=mock_router,
        repo_path=str(tmp_path),
        settings=mock_settings,
    )

    venv_env = engine._detect_venv()
    assert venv_env == {}
```

**Path traversal tests:**
```python
def test_path_traversal_blocked(self, mock_router, mock_settings, tmp_path: Path):
    """Path traversal outside repo is blocked (D-10)."""
    engine = ReproductionEngine(
        router=mock_router,
        repo_path=str(tmp_path),
        settings=mock_settings,
    )

    # _validate_path should block paths outside the repo
    is_safe = engine._validate_path("/etc/passwd")
    assert is_safe is False

    is_safe = engine._validate_path(str(tmp_path / "legit.py"))
    assert is_safe is True
```

---

### 12. `tests/test_reproduction/test_models.py` (test, model validation)

**Analog:** `tests/test_diagnosis/test_models.py`

**Imports pattern** (lines 1-2):
```python
import pytest
from pydantic import ValidationError
```

**Test function pattern** — no test classes, plain functions:
```python
def test_reproduction_result_valid():
    """ReproductionResult accepts valid fields."""
    from ascend_agent.diagnosis.models import ReproductionResult

    result = ReproductionResult(
        status="success",
        command="python -m pytest tests/",
        stdout="2 passed",
        stderr="",
        exit_code=0,
        duration_seconds=1.5,
        hypothesis_id_tested=0,
        files_changed=[],
    )
    assert result.status == "success"
    assert result.exit_code == 0
    assert result.duration_seconds == 1.5
```

**Validation test pattern** (lines 46-55 of test_models.py):
```python
def test_reproduction_result_invalid_status():
    """ReproductionResult rejects invalid status values."""
    from ascend_agent.diagnosis.models import ReproductionResult

    with pytest.raises(ValidationError):
        ReproductionResult(
            status="invalid_status",
            command="echo test",
            stdout="",
            stderr="",
            exit_code=0,
            duration_seconds=0.0,
            hypothesis_id_tested=0,
        )
```

**Extra field rejection test pattern** (lines 20-30 of test_models.py):
```python
def test_reproduction_result_forbids_extra():
    """ReproductionResult rejects extra fields (extra='forbid')."""
    from ascend_agent.diagnosis.models import ReproductionResult

    with pytest.raises(ValidationError):
        ReproductionResult(
            status="success",
            command="echo test",
            stdout="",
            stderr="",
            exit_code=0,
            duration_seconds=0.0,
            hypothesis_id_tested=0,
            extra_field="should fail",
        )
```

**Default values test pattern** (lines 66-72 of test_models.py):
```python
def test_reproduction_result_defaults():
    """ReproductionResult has sensible defaults."""
    from ascend_agent.diagnosis.models import ReproductionResult

    result = ReproductionResult(
        status="success",
        command="echo test",
        duration_seconds=0.0,
        hypothesis_id_tested=0,
    )
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.exit_code == -1
    assert result.files_changed == []
```

**Field boundary tests:**
```python
def test_reproduction_result_duration_negative_rejected():
    """ReproductionResult rejects negative duration (ge=0.0)."""
    from ascend_agent.diagnosis.models import ReproductionResult

    with pytest.raises(ValidationError):
        ReproductionResult(
            status="success",
            command="echo test",
            duration_seconds=-0.1,
            hypothesis_id_tested=0,
        )


def test_reproduction_result_hypothesis_id_negative_one():
    """ReproductionResult allows hypothesis_id_tested=-1 (no hypothesis)."""
    from ascend_agent.diagnosis.models import ReproductionResult

    result = ReproductionResult(
        status="success",
        command="echo test",
        duration_seconds=0.0,
        hypothesis_id_tested=-1,
    )
    assert result.hypothesis_id_tested == -1
```

---

## Shared Patterns

### Authentication / Authorization
**Source:** `src/ascend_agent/diagnosis/router.py` (lines 19-26)
**Apply to:** ReproductionEngine (when using ModelRouter for LLM-assisted command construction)
```python
# ModelRouter validates OPENAI_API_KEY on construction
api_key = api_key or os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY is required.")
```
ReproductionEngine uses ModelRouter; this validation is inherited.

### Error Handling
**Source:** `src/ascend_agent/tools/file_edit.py` (lines 130-138)
**Apply to:** shell_exec tool, ReproductionEngine, reproduce CLI
```python
# Pattern: catch specific exceptions first, then broad Exception
# Return JSON error objects from MCP tools; raise typer.Exit from CLI
except OSError as e:
    return json.dumps({"status": "error", "error": str(e)})
except Exception as e:
    return json.dumps({"status": "error", "error": f"Unexpected error: {e}"})
```

### Logging
**Source:** `src/ascend_agent/diagnosis/engine.py` (line 20)
**Apply to:** All new source files
```python
import logging
logger = logging.getLogger(__name__)
```

### Async Test Pattern
**Source:** `tests/test_tools/test_file_edit.py` (line 6)
**Apply to:** All async test files
```python
# Each async test function: @pytest.mark.asyncio decorator
# asyncio_mode = "auto" in pyproject.toml [tool.pytest.ini_options]
# enables implicit pytest-asyncio handling
@pytest.mark.asyncio
async def test_foo(tmp_path):
    ...
```

### MCP Tool Return Convention
**Source:** `src/ascend_agent/tools/file_edit.py` (lines 35-38, 124-128)
**Apply to:** shell_exec tool
```python
# All MCP tools return json.dumps(str) with at minimum {"status": "..."}
# Success: {"status": "ok"} or {"status": "success"}
# Failure: {"status": "error", "error": "message"}
```

### Pyproject.toml Dependency Addition
**Source:** `pyproject.toml` (lines 10-17)
**Apply to:** Adding asyncssh
```toml
# Follow existing pattern: package>=major.minor.patch
# Insert alphabetically or grouped with similar deps
"asyncssh>=2.23.0",
```

### Pydantic Config Pattern
**Source:** `src/ascend_agent/diagnosis/models.py` (line 9)
**Apply to:** ReproductionResult model
```python
model_config = ConfigDict(extra="forbid")
```

---

## No Analog Found

All files have exact analog matches in the existing codebase. No gaps.

---

## Metadata

**Analog search scope:** `src/ascend_agent/`, `tests/`, `pyproject.toml`
**Files scanned:** 345 (engine.py) + 139 (file_edit.py) + 163 (models.py) + 22 (config.py) + 16 (reproduce.py stub) + 10 (shell_exec.py stub) + 194 (diagnose.py CLI) + 95 (diagnosis conftest.py) + 24 (server.py) + 21 (app.py) + 215 (test_engine.py) + 100 (test_models.py) + 154 (test_file_edit.py) + 60 (router.py) + 216 (fix.py CLI) + 25 (test_code_search.py) + 39 (root conftest.py) + 31 (pyproject.toml) = 18 files, ~1,869 lines
**Pattern extraction date:** 2026-05-25
