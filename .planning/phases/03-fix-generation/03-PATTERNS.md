# Phase 3: Fix Generation — Pattern Map

**Mapped:** 2026-05-21
**Files analyzed:** 9 (2 new, 3 replace, 4 modify)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/ascend_agent/diagnosis/models.py` | model | CRUD | `src/ascend_agent/diagnosis/models.py` (existing) | exact-match (same file) |
| `src/ascend_agent/diagnosis/__init__.py` | config | — | `src/ascend_agent/diagnosis/__init__.py` (existing) | exact-match (same file) |
| `src/ascend_agent/diagnosis/fix_engine.py` | service | CRUD | `src/ascend_agent/diagnosis/engine.py` (Engine class) | exact-match (same role + same data flow) |
| `src/ascend_agent/tools/file_edit.py` | utility | file-I/O | `src/ascend_agent/tools/code_search.py` | role-match (MCP tool pattern) |
| `src/ascend_agent/tools/server.py` | config | — | `src/ascend_agent/tools/server.py` (existing) | exact-match (same file) |
| `src/ascend_agent/cli/fix.py` | controller | request-response | `src/ascend_agent/cli/diagnose.py` | exact-match (CLI command + Rich display) |
| `tests/test_diagnosis/test_fix_engine.py` | test | — | `tests/test_diagnosis/test_engine.py` | exact-match (same test structure + fixtures) |
| `tests/test_tools/test_file_edit.py` | test | — | `tests/test_tools/test_code_search.py` | exact-match (async MCP tool test) |
| `tests/test_cli.py` | test | — | `tests/test_cli.py` (existing) | exact-match (same file, add tests) |

---

## Pattern Assignments

### `src/ascend_agent/diagnosis/models.py` — ADD FixSuggestion, FixGenerationResult, FixResponse, Replacement, DiagnosisOutput

**Analog:** `src/ascend_agent/diagnosis/models.py` (lines 1-75) — existing file, add new models following same conventions.

**Imports & ConfigDict pattern** (lines 1-2):
```python
from pydantic import BaseModel, ConfigDict, Field
```

**Every model uses `ConfigDict(extra="forbid")` and `Field(description=...)`:**
```python
# From lines 4-13 — Evidence is the template for new models
class Evidence(BaseModel):
    """A single piece of evidence supporting a hypothesis."""
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(description="Absolute or repo-relative path to the source file")
    line_number: int = Field(ge=1, description="Line number where the evidence is found")
    code_snippet: str = Field(description="5-10 lines of surrounding code context")
    relevance: str = Field(description="Why this evidence is relevant to the hypothesis")
```

**PartialFailure pattern (for FixGenerationResult errors, lines 50-57):**
```python
class PartialFailure(BaseModel):
    """Information about a partial failure during diagnosis."""
    model_config = ConfigDict(extra="forbid")
    stage: str = Field(description="Where the failure occurred ...")
    reason: str = Field(description="Specific failure reason")
    details: str | None = Field(default=None, description="Additional details ...")
```

**DiagnosisResult pattern (for FixGenerationResult to follow — lines 60-75):**
```python
class DiagnosisResult(BaseModel):
    """Final output of the diagnosis engine."""
    model_config = ConfigDict(extra="forbid")
    hypotheses: list[Hypothesis] = Field(default_factory=list, description="...")
    errors: list[PartialFailure] = Field(default_factory=list, description="...")
    iterations_used: int = Field(default=0, ge=0, le=3, description="...")
```

**Apply pattern:** New `FixSuggestion`, `FixGenerationResult`, `FixResponse`, `Replacement`, and `DiagnosisOutput` models follow the same `BaseModel` → `ConfigDict(extra="forbid")` → typed `Field(description=...)` pattern.

---

### `src/ascend_agent/diagnosis/__init__.py` — ADD new model exports

**Analog:** `src/ascend_agent/diagnosis/__init__.py` (lines 1-22)

**Barrel export pattern (lines 1-22):**
```python
from ascend_agent.diagnosis.engine import Engine, _read_function_body
from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    Evidence,
    Hypothesis,
    PartialFailure,
    SearchAction,
    SearchDecision,
)
from ascend_agent.diagnosis.router import ModelRouter

__all__ = [
    "_read_function_body",
    "DiagnosisResult",
    "Engine",
    "Evidence",
    "Hypothesis",
    "ModelRouter",
    "PartialFailure",
    "SearchAction",
    "SearchDecision",
]
```

**Apply pattern:** Add `FixEngine`, `FixSuggestion`, `FixGenerationResult`, `FixResponse`, `Replacement`, `DiagnosisOutput` to imports and `__all__`.

---

### `src/ascend_agent/diagnosis/fix_engine.py` — CREATE new FixEngine class

**Analog:** `src/ascend_agent/diagnosis/engine.py` — Engine class (exact role match, same directory)

**Imports pattern** (engine.py lines 1-18):
```python
import asyncio
import ast
import logging
from pathlib import Path

from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    PartialFailure,
    SearchDecision,
)
from ascend_agent.diagnosis.router import ModelRouter

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3
```

**Engine class pattern — constructor + public API** (engine.py lines 161-175):
```python
class Engine:
    """Orchestrates the LLM-driven diagnosis search loop.

    The Engine receives a ContextDocument, runs up to *MAX_ITERATIONS*
    LLM-directed code searches, and produces a DiagnosisResult with
    ranked hypotheses and evidence.
    """

    def __init__(self, router: ModelRouter, repo_path: str):
        self._router = router
        self._repo_path_resolved = Path(repo_path).resolve()

    # -- Public API ----------------------------------------------------------

    def diagnose(self, context_doc) -> DiagnosisResult:
        """Run the diagnosis loop. Returns a structured result."""
```

**Engine method pattern — LLM call with `.completion()` + error handling** (engine.py lines 197-209):
```python
            try:
                decision: SearchDecision = self._router.completion(
                    messages=decision_messages,
                    response_model=SearchDecision,
                    max_tokens=4096,
                )
            except Exception as exc:
                logger.warning(
                    "LLM call failed at iteration %d: %s", iteration, exc
                )
                iterations_used = iteration
                break
```

**Engine method pattern — fallback on failure with PartialFailure** (engine.py lines 262-280):
```python
        try:
            result: DiagnosisResult = self._router.completion(
                messages=hypothesis_messages,
                response_model=DiagnosisResult,
                max_tokens=8192,
            )
        except Exception as exc:
            logger.error("Hypothesis generation failed: %s", exc)
            result = DiagnosisResult(
                hypotheses=[],
                errors=[
                    PartialFailure(
                        stage="hypothesis_generation",
                        reason="LLM call failed",
                        details=str(exc),
                    )
                ],
                iterations_used=iterations_used,
            )
```

**`_read_function_body` utility to reuse** (engine.py lines 29-68):
```python
def _read_function_body(
    file_path: str, target_line: int, context_lines: int = 5
) -> str | None:
    """Read a function body ±N lines of surrounding context."""
    try:
        with open(file_path, "r") as f:
            source = f.read()
        lines = source.splitlines()
    except (FileNotFoundError, OSError):
        return None
    # ... AST-based extraction with line-window fallback
```

**Apply pattern:** FixEngine follows exact same constructor pattern (`router: ModelRouter, repo_path: str` → `self._router` / `self._repo_path_resolved`), same `_router.completion()` call pattern, same error handling pattern with `logger.warning` / `PartialFailure`. The public method is `generate_fixes(self, diagnosis: DiagnosisResult) -> FixGenerationResult`. Import `_read_function_body` from `ascend_agent.diagnosis.engine`.

---

### `src/ascend_agent/tools/file_edit.py` — REPLACE stub with search-and-replace implementation

**Analog:** `src/ascend_agent/tools/code_search.py` (role-match: MCP tool in same directory)

**Imports pattern** (code_search.py lines 1-5):
```python
import os
import re
import subprocess

from mcp.server.fastmcp import Context
```

**Async tool function pattern** (code_search.py lines 8-28):
```python
async def search_code(pattern: str, path: str = ".", ctx: Context | None = None) -> str:
    try:
        if ctx:
            await ctx.info(f"Searching for '{pattern}' in {path}")
        result = subprocess.run(...)
        if result.returncode == 0:
            return _truncate(result.stdout)
        if result.returncode == 1:
            return f"No matches found for '{pattern}'"
        raise ValueError(f"rg search failed: {result.stderr}")
    except FileNotFoundError:
        if ctx:
            await ctx.info("rg not found, using Python fallback")
        return await _native_search(pattern, path)
    except subprocess.TimeoutExpired:
        raise ValueError(f"Search timed out for pattern '{pattern}'")
    except Exception as e:
        raise ValueError(f"Search failed: {e}")
```

**Return format pattern:** Tools return plain strings (JSON-serializable dicts as JSON strings):
```python
# Existing edit_file stub (lines 6-9) returns JSON dict as string:
return json.dumps({
    "status": "stub",
    "message": "...",
})
```

**Apply pattern:** The new `edit_file` implementation follows the same `async def` signature with `ctx: Context | None = None`, returns `json.dumps({...})` for structured results. Uses `pathlib` (`Path.read_text()`, `Path.write_text()`, `Path.rename()`) instead of `open()` directly. Validation-first approach (validate all operations before applying any).

---

### `src/ascend_agent/tools/server.py` — MODIFY edit_file description

**Analog:** `src/ascend_agent/tools/server.py` (lines 1-24, existing file)

**Tool registration pattern** (lines 12-15):
```python
mcp.tool(name="code_search", description="Search for a regex pattern in Python files in the codebase")(search_code)
mcp.tool(name="edit_file", description="[STUB] Edit a file in the codebase — implemented in Phase 3")(edit_file)
mcp.tool(name="exec_shell", description="[STUB] Execute a shell command — implemented in Phase 4")(exec_shell)
mcp.tool(name="run_test", description="[STUB] Run a test command — implemented in Phase 5")(run_test)
```

**Apply pattern:** Change `edit_file` description from `"[STUB] Edit a file..."` to a proper description: `"Edit a file using search-and-replace operations with automatic .bak backup"`.

---

### `src/ascend_agent/cli/fix.py` — REPLACE stub with full fix CLI implementation

**Analog:** `src/ascend_agent/cli/diagnose.py` (exact match: CLI command with Rich display)

**Imports pattern** (diagnose.py lines 1-18):
```python
import json
import sys

import typer
from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from ascend_agent.config import settings
from ascend_agent.context.models import ConfigEnv, ContextDocument
from ascend_agent.context.repo import RepoScanner
from ascend_agent.context.trace import trace_from_file, trace_from_stdin, trace_from_text
from ascend_agent.diagnosis.engine import Engine
from ascend_agent.diagnosis.models import DiagnosisResult, Hypothesis, Evidence, PartialFailure
from ascend_agent.diagnosis.router import ModelRouter

console = Console()
```

**Typer app definition pattern** (diagnose.py line 19):
```python
diagnose_app = typer.Typer(name="diagnose", help="Diagnose an issue from a stack trace against a code repository")
```

**CLI command pattern** (diagnose.py lines 22-39):
```python
@diagnose_app.command(name="run")
def diagnose_run(
    repo: str = typer.Argument(..., help="Path to local repository"),
    trace: str | None = typer.Option(None, "--trace", help="Path to trace/log file"),
    trace_text: str | None = typer.Option(None, "--trace-text", help="Inline pasted trace text"),
    output: str | None = typer.Option(None, "--output", help="Path to write context as JSON"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Start interactive REPL mode"),
):
```

**Error handling with typer.Exit** (diagnose.py lines 51-55):
```python
    except OSError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
```

**Rich Panel + Syntax display pattern** (diagnose.py lines 179-191):
```python
    for i, hyp in enumerate(result.hypotheses, 1):
        border = "green" if hyp.confidence >= 0.7 else ("yellow" if hyp.confidence >= 0.4 else "red")
        panel = Panel(
            "",
            title=f"Hypothesis #{i} — Confidence: {hyp.confidence:.0%}",
            border_style=border,
        )
        console.print(panel)
        console.print(f"[bold]Root Cause:[/bold] {hyp.root_cause}")
        for ev in hyp.evidence:
            console.print(f"[blue]File: {ev.file_path}:{ev.line_number}[/blue]")
            console.print(Syntax(ev.code_snippet, "python", theme="monokai", line_numbers=True))
```

**Stdin reading pattern** (diagnose.py lines 60-63):
```python
    elif not sys.stdin.isatty():
        trace_info = trace_from_stdin()
```

**JSON output pattern** (diagnose.py lines 85-87):
```python
    if output_path is not None:
        with open(output_path, "w") as f:
            f.write(doc.model_dump_json(indent=2))
```

**Current fix.py stub (for argument signature pattern)** (fix.py lines 8-11):
```python
@fix_app.command(name="run")
def fix_run(
    diagnosis: str = typer.Argument(..., help="Path to diagnosis JSON file"),
):
```

**Apply pattern:** The new `fix run` command follows the same typer app pattern as `diagnose_app`. Connects the fix sub-app (already registered in `app.py` line 21). Uses `Rich Panel + Syntax` for diff display. Uses `Prompt.ask(choices=["a", "s", "r"])` for interactive review (from RESEARCH.md). Uses `sys.stdin.isatty()` for stdin fallback (diagnose.py line 62 pattern). Saves output with `model_dump_json(indent=2)` (diagnose.py line 87 pattern).

---

### `tests/test_diagnosis/test_fix_engine.py` — CREATE new test file for FixEngine

**Analog:** `tests/test_diagnosis/test_engine.py` (lines 1-215, exact match: same directory, same test patterns)

**Imports pattern** (test_engine.py lines 1-13):
```python
"""Tests for the diagnosis Engine class and _read_function_body utility."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ascend_agent.diagnosis.engine import Engine, _read_function_body
from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    SearchAction,
    SearchDecision,
)
```

**Test class pattern** (test_engine.py lines 61-68):
```python
class TestEngine:
    """Tests for the Engine class."""

    def test_constructor_stores_dependencies(self, mock_router, tmp_path: Path):
        """Engine.__init__ stores router and repo_path."""
        engine = Engine(router=mock_router, repo_path=str(tmp_path))
        assert engine._router is mock_router
        assert engine._repo_path_resolved == tmp_path.resolve()
```

**Mock LLM side_effect pattern** (test_engine.py lines 70-98):
```python
    def test_search_loop_hypothesizes_after_searches(self, mock_router, sample_context_doc, tmp_path: Path):
        """Engine search loop iterates with mock LLM: searches then hypothesizes."""
        # First call returns search decision
        # Second call returns hypothesize decision
        mock_router.completion.side_effect = [
            SearchDecision(...),
            SearchDecision(...),
            DiagnosisResult(...),
        ]

        with patch("ascend_agent.tools.code_search.search_code", return_value="No matches"):
            engine = Engine(router=mock_router, repo_path=str(tmp_path))
            result = engine.diagnose(sample_context_doc)

        assert isinstance(result, DiagnosisResult)
```

**Conftest fixtures available** (tests/test_diagnosis/conftest.py lines 87-95):
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

**Apply pattern:** Follow same test class pattern with `TestFixEngine`. Use `mock_router` fixture from existing conftest.py. Set `.completion.side_effect` to control LLM responses. Use `tmp_path` for file-system tests. Test constructor dependencies, fix generation for a hypothesis, error handling (malformed LLM output), diff computation, and code re-reading.

---

### `tests/test_tools/test_file_edit.py` — CREATE new test file for edit_file

**Analog:** `tests/test_tools/test_code_search.py` (lines 1-25, exact match: same directory, async MCP tool test pattern)

**Async test pattern** (test_code_search.py lines 1-11):
```python
import pytest


@pytest.mark.asyncio
async def test_search_regex_pattern(tmp_path):
    from ascend_agent.tools.code_search import search_code
    (tmp_path / "test.py").write_text("x = 42  # the answer\n")
    result = await search_code("42", str(tmp_path))
    assert "test.py" in result
    assert "42" in result
```

**Apply pattern:** Follow same `@pytest.mark.asyncio` pattern. `edit_file` takes `(path, content, ctx=None)` but in tests call with `ctx=None`. Use `tmp_path` for file fixtures. Test: old_text validation, backup creation, duplicate match rejection, multiple replacements, successful application, path traversal prevention.

---

### `tests/test_cli.py` — MODIFY: add fix CLI integration tests

**Analog:** `tests/test_cli.py` (lines 1-78, existing file — add tests following same patterns)

**CliRunner + monkeypatch pattern** (test_cli.py lines 1-5, 21-36):
```python
from typer.testing import CliRunner
from ascend_agent.cli.app import app

runner = CliRunner()


def test_cli_diagnose_run_basic(tmp_path, monkeypatch):
    from unittest.mock import Mock
    (tmp_path / "test.py").write_text("x = 1\n")
    mock_engine = Mock()
    mock_engine.diagnose.return_value = Mock(hypotheses=[], errors=[], iterations_used=0)
    import ascend_agent.cli.diagnose as diag_mod
    monkeypatch.setattr(diag_mod, "Engine", lambda router, repo_path: mock_engine)
    monkeypatch.setattr("ascend_agent.diagnosis.router.ModelRouter.__init__", lambda self: None)

    result = runner.invoke(app, [
        "diagnose", "run", str(tmp_path),
        "--trace-text", "ValueError: test",
    ])
    assert result.exit_code == 0
    assert "Repository Info" in result.stdout
```

**Apply pattern:** Follow same `runner.invoke(app, ["fix", "run", ...])` pattern. Write mock diagnosis JSON to tmp_path. Monkeypatch FixEngine and ModelRouter. Test: `fix run` reads diagnosis JSON, shows fix suggestions, review workflow prompts, batch apply.

---

## Shared Patterns

### Authentication / LLM Router
**Source:** `src/ascend_agent/diagnosis/router.py` (lines 10-57)
**Apply to:** `fix_engine.py` (via FixEngine → ModelRouter dependency)

```python
# ModelRouter constructor pattern — accepts model override from env var
class ModelRouter:
    _DEFAULT_MODEL = "gpt-4o"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required ...")
        self._client = OpenAI(api_key=api_key)
        self._model = model or os.environ.get(
            "ASCEND_DIAGNOSIS_MODEL", self._DEFAULT_MODEL
        )

    def completion(self, messages, response_model, max_tokens=4096, temperature=0.1):
        completion = self._client.chat.completions.parse(
            model=self._model,
            messages=messages,
            response_format=response_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return completion.choices[0].message.parsed
```

**Phase 3 adaptation:** FixEngine uses `ModelRouter(model=os.environ.get("ASCEND_FIX_MODEL", "gpt-4o"))` instead of the diagnosis default.

### Error Handling
**Source:** `src/ascend_agent/diagnosis/models.py` — PartialFailure (lines 50-57)
**Apply to:** `fix_engine.py` (FixGenerationResult includes errors list)

```python
class PartialFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: str = Field(description="Where the failure occurred ...")
    reason: str = Field(description="Specific failure reason")
    details: str | None = Field(default=None, description="Additional details ...")
```

**Engine error pattern** (engine.py lines 262-280) — fallback result with PartialFailure:
```python
    result = DiagnosisResult(
        hypotheses=[],
        errors=[PartialFailure(stage="fix_generation", reason="LLM call failed", details=str(exc))],
        iterations_used=iterations_used,
    )
```

### Validation
**Source:** `src/ascend_agent/diagnosis/models.py` — `ConfigDict(extra="forbid")` pattern (lines 6-7)
**Apply to:** All new Pydantic models in models.py

```python
model_config = ConfigDict(extra="forbid")
```

### Rich Display for Diffs
**Source:** `src/ascend_agent/cli/diagnose.py` (lines 163-191) — Panel + Syntax pattern
**Apply to:** `cli/fix.py` — fix review diff display (same pattern with `"diff"` lexer instead of `"python"`)

```python
from rich.panel import Panel
from rich.syntax import Syntax

# Reuse this pattern with "diff" lexer for fix display:
console.print(Panel(
    Syntax(diff_patch, "diff", theme="monokai", line_numbers=True),
    title=f"Suggested Changes — {file_path}",
    border_style="blue",
))
```

### Interactive Prompts (Rich Prompt.ask)
**Source:** Rich Prompt documentation (confirmed by RESEARCH.md)
**Apply to:** `cli/fix.py` — Accept/Skip/Reject review workflow

```python
from rich.prompt import Prompt

action = Prompt.ask(
    "[bold]Action[/bold] ([green]A[/green]ccept / [yellow]S[/yellow]kip / [red]R[/red]eject)",
    choices=["a", "s", "r"],
    default="s",
)
```

### `.bak` file pattern
**Source:** RESEARCH.md (verified approach from `Path.read_bytes()` + `Path.write_bytes()`)
**Apply to:** `tools/file_edit.py` — backup before edit

```python
# Create backup before edit
if create_backup:
    backup_path = path.with_suffix(path.suffix + ".bak")
    path.rename(backup_path)

# Apply replacements
result = original
for op in operations:
    result = result.replace(op.old_text, op.new_text, 1)
path.write_text(result)
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| — | — | — | All files have at least a role-match analog in the existing codebase |

---

## Metadata

**Analog search scope:** `src/ascend_agent/` (all Python files), `tests/` (all test files)
**Files scanned:** 15+ files across src and tests
**Pattern extraction date:** 2026-05-21
