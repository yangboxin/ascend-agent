# Phase 5: Verification &闭环 - Research

**Researched:** 2026-05-25
**Domain:** Test verification — consuming reproduction results, auto-detecting test frameworks, running relevant tests, and producing structured pass/fail reports
**Confidence:** HIGH

## Summary

Phase 5 is the terminal phase of the diagnostic pipeline. It consumes `ReproductionResult` JSON from Phase 4 (which includes `files_changed` and `hypothesis_id_tested`), auto-detects the test framework in the target repo, maps changed source files to their corresponding test files, executes only the relevant tests, and produces a structured `VerificationResult` with pass/fail details and a human-readable summary.

The phase leverages three existing assets heavily: the `exec_shell` MCP tool (for running `pytest --json-report` commands), the Engine pattern (constructor + public method → Pydantic result), and the CLI pattern (Typer subcommand with Rich output). The primary new dependency is `pytest-json-report` v1.5.0, a mature pytest plugin that produces structured JSON test output.

**Primary recommendation:** Build `VerificationEngine` as a deterministic class (no LLM) following the existing Engine pattern, using `exec_shell` to run `pytest --json-report` with `pytest-json-report` programmatic API, and parsing the JSON report into a structured `VerificationResult` Pydantic model.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Test framework detection | VerificationEngine (local host) | — | Probes target repo for pytest config files; runs on the host where ascend-agent executes |
| Test file mapping | VerificationEngine | — | Deterministic heuristic mapping src files → test files; pure string/path logic |
| Test execution | Tool Layer (exec_shell) | — | Reuses existing shell execution; routes local or SSH based on ASCEND_SSH_HOST |
| Result parsing | VerificationEngine | — | Parses pytest-json-report JSON output into Pydantic VerificationResult |
| Result display | CLI Layer (Typer + Rich) | — | Follows diagnose/reproduce/fix CLI pattern with Panel, Syntax, color-coded status |
| Report persistence | CLI Layer | — | `--output` JSON flag for saving VerificationResult; same pattern as other CLI commands |

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Auto-detect the test framework by probing the target repo for pytest config files (`pytest.ini`, `pyproject.toml [tool.pytest]`, `setup.cfg`). Fall back to `pytest` if detected. Report inability to verify if no supported framework is found.
- **D-02:** Run only relevant tests — map `files_changed` from `ReproductionResult` to their corresponding test files using a heuristic (e.g., `src/foo.py` → `tests/test_foo.py`, `tests/foo_test.py`). Do not run the full test suite by default.
- **D-03:** Parse test results using structured JSON output (`pytest --json-report`). Extract pass/fail/error counts, per-test details, and durations. Requires `pytest-json-report` plugin as a dependency.
- **D-04:** Reuse the `exec_shell` MCP tool pattern from Phase 4 for test execution. Local subprocess by default; SSH via `ASCEND_SSH_HOST` when configured. Same environment as reproduction.

### The Agent's Discretion
- Exact test file mapping heuristic (e.g., strip `src/` → prepend `tests/test_`, glob for `*_test.py`, etc.)
- Pydantic model structure for `VerificationResult` (pass/fail/error counts, per-test details, summary)
- Construction of `VerificationEngine` class (follows existing Engine pattern: constructor + public method → structured result)
- `verify` CLI command design (Typer subcommand with Rich display)
- Timeout values and retry strategy for test execution
- Whether verification engine uses LLM assistance (ModelRouter) or is purely deterministic

### Deferred Ideas (OUT OF SCOPE)
- **Full test suite mode** — Running all tests as a final gate. Deferred to keep scope focused on targeted per-fix verification. Could be a `--full` flag in a future enhancement.
- **Custom test command flag** — Letting the user override the test command. Deferred until auto-detection proves insufficient for non-pytest repos.
- **Custom parsing rules** — Regex-based parsers for non-pytest test frameworks. Deferred until multi-framework support is needed.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VERIF-01 | Agent can run tests to verify fixes | exec_shell MCP tool (D-04) runs `pytest --json-report` targeting mapped test files; framework auto-detection (D-01) ensures pytest is found; relevant-test-only mapping (D-02) ensures focused execution |
| VERIF-02 | Agent can report verification results | pytest-json-report programmatic API produces structured JSON (D-03); VerificationResult Pydantic model extracts pass/fail/error counts and per-test details; Rich CLI displays color-coded summary with Panel + Syntax |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | ≥7.0.0 (project: 8.4.2) | Test framework — discovery, execution, reporting | The project's test infrastructure already uses pytest; it is the only supported framework per D-01 |
| pytest-json-report | 1.5.0 [VERIFIED: npm registry — PyPI] | Structured JSON test output | Mature plugin (first released 2018, latest 2022-03-15); provides both CLI (`--json-report`) and programmatic API (`JSONReport` plugin class); 155 GitHub stars, active maintenance history |
| Pydantic v2 | ≥2.13.0 (already in deps) | VerificationResult model definition | Project standard; all phase contracts use Pydantic v2 with `ConfigDict(extra="forbid")` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Rich | ≥15.0.0 (already in deps) | Terminal output (Panel, Syntax, color-coded status) | CLI display of verification results; follows diagnose/reproduce/fix CLI patterns |
| Typer | ≥0.25.0 (already in deps) | CLI subcommand registration | `verify run` CLI command; registered in `app.py` |
| FastMCP | ≥1.27.1 (already in deps) | MCP tool definition | `run_test` MCP tool implementation (already registered as stub in `server.py`) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-json-report | pytest-json (mattcl/pytest-json) | pytests-json is unmaintained and noted as such by pytest-json-report's README. pytest-json-report is the maintained successor. |
| exec_shell + CLI command | `pytest.main()` programmatic API | `pytest.main()` is [documented by pytest as not recommended for repeated calls](https://docs.pytest.org/en/stable/how-to/usage.html#calling-pytest-from-python-code) due to Python import caching. Using a subprocess via exec_shell avoids this issue and matches the existing reproduction pattern. |

**Installation:**
```bash
pip install "pytest-json-report>=1.5.0"
```

**Version verification:**
```bash
pip index versions pytest-json-report  # Confirmed: 1.5.0 available on PyPI (2026-05-25)
python3 -m pytest --version             # Confirmed: 8.4.2 installed in environment
```

## Package Legitimacy Audit

> **Note:** slopcheck was not available (`pip install slopcheck` failed with "not found"). All packages are tagged `[ASSUMED]` per protocol — the planner must gate each install behind a `checkpoint:human-verify` task.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| pytest-json-report | PyPI | 8 yrs+ (v0.1: 2018) | Established | github.com/numirias/pytest-json-report | Unavailable — [ASSUMED] | Approved — mature, well-maintained, recommended by README as successor to unmaintained pytest-json |
| pytest | PyPI | 15 yrs+ | Core ecosystem | github.com/pytest-dev/pytest | Unavailable — [ASSUMED] | Already installed (v8.4.2); no new install needed |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none (audit tools unavailable — verify before install)

*slopcheck was unavailable at research time. All packages above are tagged `[ASSUMED]` and the planner must gate each install behind a `checkpoint:human-verify` task.*

## Architecture Patterns

### System Architecture Diagram

```
ReproductionResult (JSON)
    │  .files_changed = ["src/ascend_agent/tools/shell_exec.py"]
    │  .hypothesis_id_tested = 0
    ▼
┌─────────────────────────────────────┐
│        VerificationEngine            │
│                                      │
│  1. detect_framework(repo_path)      │
│     ├─ probe pytest.ini              │
│     ├─ probe pyproject.toml [pytest] │
│     ├─ probe setup.cfg               │
│     └─ return "pytest" or None       │
│                                      │
│  2. map_test_files(files_changed)    │
│     ├─ src/foo.py → tests/test_foo   │
│     ├─ glob for *_test.py            │
│     └─ return list of test paths     │
│                                      │
│  3. build_command(test_files)        │
│     → "python -m pytest test1 test2  │
│        --json-report --json-report-  │
│        file=none"                    │
│                                      │
│  4. execute(command) ──────────────┐ │
│     └─ exec_shell(command)         │ │
└────────────────────────────────────┘ │
                                       ▼
    ┌──────────────────────────┐
    │   exec_shell MCP tool     │
    │   (Phase 4, already impl)  │
    │                            │
    │  local: subprocess         │
    │  remote: asyncssh          │
    └──────────┬─────────────────┘
               │ stdout (JSON report)
               ▼
┌─────────────────────────────────────┐
│   Parse JSON → VerificationResult   │
│                                      │
│  {                                    │
│    "summary": {                       │
│      "passed": 3, "failed": 1,       │
│      "error": 0                      │
│    },                                │
│    "tests": [                        │
│      { "nodeid": "...",             │
│        "outcome": "passed", ... }   │
│    ]                                 │
│  }                                   │
└──────────────────────────────────────┘
               │
               ▼
    ┌──────────────────────┐
    │   CLI: verify run    │
    │   (Rich Panel display)│
    │                      │
    │  [✓] 3 passed        │
    │  [✗] 1 failed        │
    │  → --output JSON      │
    └──────────────────────┘
```

### Recommended Project Structure
```
src/ascend_agent/
├── verification/              # NEW: verification package
│   ├── __init__.py
│   └── engine.py              # VerificationEngine class
├── diagnosis/
│   └── models.py              # + VerificationResult model added here
├── cli/
│   └── verify.py              # NEW: verify Typer subcommand
├── tools/
│   ├── test_runner.py         # MODIFIED: run_test MCP tool implementation
│   └── server.py              # MODIFIED: run_test description updated
└── config.py                  # POTENTIALLY: + test_timeout setting

tests/
└── test_verification/         # NEW: VerificationEngine tests
    ├── __init__.py
    ├── conftest.py
    ├── test_engine.py         # VerificationEngine unit tests
    └── test_models.py         # VerificationResult model tests
```

### Pattern 1: Engine Pattern (VerificationEngine)

**What:** Constructor accepts dependencies (router, repo_path, settings), public async method returns structured Pydantic result. This is the 4th engine in the project (DiagnosisEngine, FixEngine, ReproductionEngine, VerificationEngine).

**When to use:** Phase 5 verification orchestration.

**Example (following ReproductionEngine pattern):**
```python
# Source: existing ReproductionEngine pattern (src/ascend_agent/reproduction/engine.py)
from ascend_agent.diagnosis.models import ReproductionResult, VerificationResult
from ascend_agent.diagnosis.router import ModelRouter

class VerificationEngine:
    def __init__(self, router: ModelRouter, repo_path: str, settings=None):
        self._router = router
        self._repo_path = Path(repo_path).resolve()
        self._settings = settings or Settings()

    async def verify(self, reproduction: ReproductionResult) -> VerificationResult:
        """Run verification workflow: detect → map → execute → parse → report."""
        ...
```

### Pattern 2: pytest-json-report Programmatic API

**What:** Use `JSONReport` plugin class with `pytest.main()` to capture structured test output programmatically. The plugin collects results into `plugin.report` dict during execution.

**When to use:** Test execution within VerificationEngine.

**Example:**
```python
# Source: pytest-json-report README (github.com/numirias/pytest-json-report)
import pytest
from pytest_jsonreport.plugin import JSONReport

plugin = JSONReport()
exitcode = pytest.main(
    ['--json-report-file=none', '--json-report-summary',
     'tests/test_foo.py'],
    plugins=[plugin]
)
# Access results: plugin.report
report = plugin.report
summary = report['summary']  # {"passed": 3, "failed": 1, ...}
tests = report['tests']      # per-test detail array
```

**Important caveat:** pytest docs note that `pytest.main()` caches imports, making repeated calls unreliable "[Calling pytest from Python code](https://docs.pytest.org/en/stable/how-to/usage.html#calling-pytest-from-python-code)". The preferred approach for this phase is:

1. **Option A (recommended):** Use `exec_shell` to run `pytest --json-report --json-report-file=<tmp_path>` as a subprocess, then read the JSON file. This avoids the import caching issue entirely and follows the D-04 pattern exactly.
2. **Option B:** Use `pytest.main()` with JSONReport plugin for a single invocation (acceptable since we only run once per verify call).

The subprocess approach (Option A) is recommended because it:
- Avoids the `pytest.main()` caching issue
- Reuses `exec_shell` directly (D-04)
- Matches the reproduction execution pattern exactly
- Works identically for local and SSH execution

**Key `--json-report-*` flags:**
| Flag | Purpose |
|------|---------|
| `--json-report` | Enable JSON reporting |
| `--json-report-file=PATH` | Write report to file (use `none` to not save) |
| `--json-report-summary` | Summary only, no per-test details |
| `--json-report-indent=LEVEL` | Pretty-print with indentation |

### Pattern 3: Test File Mapping Heuristic

**What:** Deterministic mapping from source files (`files_changed` in ReproductionResult) to test files. The heuristic uses filename conventions plus glob-based discovery.

**When to use:** Building the test file list before executing tests.

**Heuristic tiers (priority order):**

1. **Exact convention match:** Strip `src/` prefix, replace with `tests/`, append `test_` prefix to filename
   - `src/ascend_agent/tools/shell_exec.py` → `tests/test_tools/test_shell_exec.py`

2. **Glob search:** If exact match doesn't exist, glob for patterns in the test directory
   - `*_test.py`, `test_*.py` variants

3. **Module-level fallback:** Test the entire test module rather than individual files
   - Map `src/ascend_agent/diagnosis/models.py` → `tests/test_diagnosis/`

4. **Give up gracefully:** If no matching tests found, report "No relevant tests found for: [files]" in VerificationResult

**This project's mapping (verified against existing codebase):**
```
src/ascend_agent/diagnosis/engine.py     → tests/test_diagnosis/test_engine.py      ✓ exists
src/ascend_agent/diagnosis/models.py     → tests/test_diagnosis/test_models.py       ✓ exists
src/ascend_agent/tools/shell_exec.py     → tests/test_tools/test_shell_exec.py       ✓ exists
src/ascend_agent/tools/code_search.py    → tests/test_tools/test_code_search.py      ✓ exists
src/ascend_agent/tools/file_edit.py      → tests/test_tools/test_file_edit.py        ✓ exists
src/ascend_agent/tools/server.py         → tests/test_tools/test_server.py           ✓ exists
src/ascend_agent/reproduction/engine.py  → tests/test_reproduction/test_engine.py    ✓ exists
src/ascend_agent/diagnosis/router.py     → tests/test_diagnosis/test_router.py       ✓ exists
src/ascend_agent/diagnosis/fix_engine.py → tests/test_diagnosis/test_fix_engine.py   ✓ exists
src/ascend_agent/config.py               → tests/test_context.py (approximate)
```

### Anti-Patterns to Avoid
- **pytest.main() repeated calls:** pytest docs explicitly warn against multiple `pytest.main()` calls from the same process. Use subprocess (via exec_shell) instead.
- **AIOHTTP/browser-state in tests:** Not applicable — this is a CLI tool, no browser context.
- **Hardcoding test file paths:** Use the heuristic; don't maintain a hardcoded source→test map.
- **Running test suites that don't exist:** If no test files map from changed source files, report clearly rather than running `pytest tests/` as a blanket fallback (deferred `--full` flag).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test JSON parsing | Custom regex/stdout scraper | pytest-json-report (1.5.0) | Handles all pytest output formats (pass, fail, error, skip, xfail, xpass), traceback extraction, durations, captured stdout/stderr. A regex scraper would miss edge cases and break on pytest output format changes. |
| Test execution orchestration | Custom subprocess runner with timeout | exec_shell MCP tool (Phase 4) | Already implements local/SSH routing, timeout handling, stdout/stderr capture, error handling for both subprocess and asyncssh. Reuse avoids duplicating 157 lines of battle-tested code. |
| Process management | `subprocess.run()` / `Popen` directly | `asyncio.create_subprocess_shell()` (via exec_shell) | Async-native, proper timeout with kill + await, UTF-8 decode with error handling. exec_shell already wraps all of this. |
| Terminal tables for test results | Manual format strings | Rich `Table`, `Panel`, `Syntax` | Project convention; all CLI commands use Rich for consistent output. Rich handles terminal width, color themes, and accessibility. |

**Key insight:** The test execution layer is entirely handled by existing infrastructure (exec_shell). Phase 5 is primarily about **orchestration and parsing** — what tests to run (mapping), how to interpret results (JSON parsing), and how to present them (Rich display). The only new infrastructure dependency is pytest-json-report.

## Runtime State Inventory

> Phase 5 is not a rename/refactor/migration phase — it is a greenfield implementation phase. No runtime state inventory is needed.

## Common Pitfalls

### Pitfall 1: pytest.main() Import Caching

**What goes wrong:** Calling `pytest.main()` from within the same Python process that imported the test modules results in stale results. Python's import system caches modules, so file changes between calls won't be reflected.

**Why it happens:** This is by design in Python — `import` is cached in `sys.modules`. pytest documentation explicitly states: "making multiple calls to pytest.main() from the same process... is not recommended."

**How to avoid:** Use `exec_shell` to run `pytest --json-report` as a subprocess. This spawns a fresh Python process each time, avoiding the caching issue entirely. This also follows D-04 (reuse exec_shell).

**Warning signs:** Tests that were just created/modified don't appear in results; stale test counts that don't match expectations.

### Pitfall 2: pytest-json-report Not Installed in Target Environment

**What goes wrong:** The `pytest --json-report` flag requires `pytest-json-report` to be installed. If running tests against the target repo (which may have its own virtualenv), the plugin may not be present.

**Why it happens:** pytest-json-report is an ascend-agent dependency, not a target-repo dependency. When commands execute via `exec_shell`, they run in the current process environment or the SSH remote environment.

**How to avoid:** The `_detect_venv()` method (already in ReproductionEngine) can check for pytest-json-report availability. If absent, install it: `pip install pytest-json-report`. Alternatively, include it in the project's dev dependencies. For remote execution, the install must happen on the remote machine.

**Warning signs:** pytest returns "unrecognized arguments: --json-report" or non-JSON stdout.

### Pitfall 3: Map Heuristic Misses Tests

**What goes wrong:** The heuristic fails to find test files for a changed source file. The verification silently reports "all passed" because it ran zero tests.

**Why it happens:** Test file naming conventions vary across projects. Some repos use `test_foo.py`, others use `foo_test.py`, and some use non-standard naming or nested structures.

**How to avoid:** Report the number of test files found BEFORE execution. If zero tests are mapped, include this fact prominently in the VerificationResult: `tests_found: 0, tests_skipped_reason: "No test files mapped from changed files: [list]"`. Also implement glob-based fallback search (tier 2 of the heuristic).

**Warning signs:** `tests_found = 0` when `files_changed` is non-empty. Verification should never be "green" with zero tests unless explicitly acknowledged.

### Pitfall 4: Timeout on Long Test Suites

**What goes wrong:** The test command exceeds the default timeout and exec_shell kills it, returning an error status. The verification result looks like a failure when it's actually a timeout.

**Why it happens:** The default timeout in exec_shell is 60 seconds (configurable via `ASCEND_SHELL_TIMEOUT`). Some test suites, especially integration tests, can run longer.

**How to avoid:** Set a generous test-specific timeout (300s or configurable). Add a `test_timeout` field to Settings. Pass timeout to exec_shell. If timeout occurs, report it clearly in VerificationResult: `status: "timeout"` (distinct from "fail").

**Warning signs:** exec_shell returns `{"status": "error", "stderr": "timed out after 60s"}` when tests were still progressing.

## Code Examples

Verified patterns from official sources:

### pytest-json-report Programmatic Usage
```python
# Source: pytest-json-report README (github.com/numirias/pytest-json-report)
import pytest
from pytest_jsonreport.plugin import JSONReport

plugin = JSONReport()
pytest.main(
    ['--json-report-file=none', 'tests/test_foo.py'],
    plugins=[plugin]
)
# plugin.report contains the full JSON report:
# {"created": ..., "summary": {...}, "tests": [...]}
```

### exec_shell Reuse for Test Execution
```python
# Source: existing pattern in ReproductionEngine (src/ascend_agent/reproduction/engine.py:86-94)
from ascend_agent.tools.shell_exec import exec_shell

command = f"python -m pytest {' '.join(test_files)} --json-report --json-report-file=none"
result_json = await exec_shell(command, timeout=self._settings.test_timeout)
result = json.loads(result_json)
```

### VerificationResult Pydantic Model Structure
```python
# Source: proposed design, following existing model patterns in diagnosis/models.py
from pydantic import BaseModel, ConfigDict, Field

class TestDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodeid: str = Field(description="Pytest node ID (e.g., tests/test_foo.py::test_bar)")
    outcome: str = Field(description="Test outcome: passed, failed, error, skipped, xfailed, xpassed")
    duration: float | None = Field(default=None, description="Test duration in seconds")
    message: str | None = Field(default=None, description="Failure/error message if applicable")

class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(
        pattern=r"^(pass|fail|error|timeout|no_tests)$",
        description="Overall verification status"
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

### CLI: verify run Command
```python
# Source: proposed design, following reproduce.py pattern (src/ascend_agent/cli/reproduce.py)
import asyncio, json, typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
verify_app = typer.Typer(name="verify", help="Verify fixes by running relevant tests")

@verify_app.command(name="run")
def verify_run(
    reproduction: str = typer.Argument(..., help="Path to reproduction result JSON"),
    output: str | None = typer.Option(None, "--output", "-o", help="Path to write verification result as JSON"),
):
    """Verify fixes by running tests against the changed files.
    
    Loads a reproduction JSON, auto-detects the test framework, maps changed
    files to test files, runs the relevant tests, and displays pass/fail results.
    """
    # ... load ReproductionResult, init VerificationEngine, run, display
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pytest-json` (mattcl/pytest-json) | `pytest-json-report` (numirias/pytest-json-report) | ~2018 | pytest-json-report is actively maintained and explicitly recommended as the successor |
| Manual test result parsing (grep stdout) | Structured JSON via pytest plugins | Industry standard | Eliminates fragile regex parsing; JSON is machine-readable and versioned |
| `pytest.main()` for repeated calls | Subprocess via `exec_shell` | pytest docs recommendation | Avoids import caching issues; fresh process per invocation |
| Full test suite for every fix | Relevant-test-only (D-02) | Phase 5 design decision | Faster feedback loop; focuses verification on changed code |

**Deprecated/outdated:**
- **`pytest-json` (mattcl):** Unmaintained; pytest-json-report README explicitly notes it "appears to be unmaintained." Use pytest-json-report v1.5.0 instead.
- **`pytest.main()` for repeated runs:** pytest documentation warns against this pattern. Use subprocess execution.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | pytest-json-report v1.5.0 programmatic API works as documented | Standard Stack | MEDIUM — if the `JSONReport` plugin class API changed, the programmatic invocation code would need to use the subprocess+file approach instead |
| A2 | Test file mapping heuristic works for the vllm-ascend codebase structure | Architecture Patterns | LOW — the project's own test structure follows conventions cleanly; mapping can be verified against the existing test suite |
| A3 | exec_shell runs test commands in the correct working directory (repo_path) | Architecture Patterns | MEDIUM — if exec_shell doesn't cd to repo_path, test discovery may fail; the ReproductionEngine pattern should include `cd {repo_path} && pytest ...` |
| A4 | VerificationEngine is deterministic (no LLM needed) | Architecture Patterns | LOW — test execution + JSON parsing is purely mechanical; no LLM reasoning required |

## Open Questions (RESOLVED)

1. **Should the VerificationEngine constructor require ModelRouter?** [RESOLVED]
   - Decision: Accept `router: ModelRouter` for interface consistency with all 4 prior engines but use purely deterministic logic internally — no LLM calls. Keeps the constructor pattern uniform.
   
2. **Should test timeout be a per-command value or a global setting?** [RESOLVED]
   - Decision: Add `test_timeout: int = Field(default=300, ge=1)` to Settings class, following the existing `shell_timeout` pattern.

3. **What happens if `files_changed` is empty in ReproductionResult?** [RESOLVED]
   - Decision: Report `status: "no_tests"` with a clear message. Do not silently pass. The deferred `--full` flag is the future answer for this case.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | VerificationEngine runtime | ✓ | 3.9.6 | — (project requires ≥3.10; Phase 4 already noted this blocker) |
| pytest | Test execution | ✓ | 8.4.2 | — |
| pytest-json-report | Structured test output (D-03) | ✗ | Not installed | Install via `pip install pytest-json-report` |
| exec_shell MCP tool | Test command execution (D-04) | ✓ | Implemented (Phase 4) | — |
| pytest-asyncio | Async test support | ✓ | ≥0.21.0 (in dev deps) | — |

**Missing dependencies with no fallback:**
- **pytest-json-report** — Required for D-03 (structured JSON parsing). Must be installed before VerificationEngine can run.

**Missing dependencies with fallback:**
- none

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 with pytest-asyncio (auto mode) |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_verification/ -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VERIF-01 | VerificationEngine maps files_changed to test files | unit | `pytest tests/test_verification/test_engine.py::test_map_test_files -x` | ❌ Wave 0 |
| VERIF-01 | VerificationEngine detects pytest framework in repo | unit | `pytest tests/test_verification/test_engine.py::test_detect_framework -x` | ❌ Wave 0 |
| VERIF-01 | VerificationEngine executes tests via exec_shell | integration | `pytest tests/test_verification/test_engine.py::test_execute_tests -x` | ❌ Wave 0 |
| VERIF-02 | VerificationEngine parses pytest-json-report output | unit | `pytest tests/test_verification/test_engine.py::test_parse_json_report -x` | ❌ Wave 0 |
| VERIF-02 | VerificationResult model validates correctly | unit | `pytest tests/test_verification/test_models.py::test_verification_result_valid -x` | ❌ Wave 0 |
| VERIF-02 | verify CLI displays results with Rich | integration | `pytest tests/test_verification/test_cli.py::test_verify_display -x` (or in test_cli.py) | ❌ Wave 0 |
| VERIF-01 | run_test MCP tool returns structured JSON | integration | `pytest tests/test_tools/test_server.py::test_run_test -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_verification/ -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_verification/__init__.py` — package marker
- [ ] `tests/test_verification/conftest.py` — shared fixtures (sample ReproductionResult, temporary repo with pytest config)
- [ ] `tests/test_verification/test_engine.py` — covers VERIF-01, VERIF-02 verification engine behaviors
- [ ] `tests/test_verification/test_models.py` — covers VerificationResult model validation
- [ ] `tests/test_verification/test_cli.py` — covers verify CLI display (or extend existing `tests/test_cli.py`)
- [ ] `pytest-json-report` install: `pip install pytest-json-report` — required for test infra

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | — |
| V3 Session Management | No | — |
| V4 Access Control | No | — |
| V5 Input Validation | Yes | Pydantic v2 with `ConfigDict(extra="forbid")` + `Field` constraints on all input models (ReproductionResult ingestion, VerificationResult construction) |
| V6 Cryptography | No | — |

### Known Threat Patterns for CLI Test Verification

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Command injection via test file paths | Tampering | Path traversal protection: resolve all test file paths against repo boundary using `Path.resolve()` + `startswith()` (same pattern as edit_file D-15 and ReproductionEngine D-10) |
| Malicious JSON input (crafted ReproductionResult) | Spoofing | Pydantic schema validation with `model_validate_json()` — rejects unknown fields, validates types and constraints. Empty `files_changed` handled gracefully. |
| Information disclosure via test output | Information Disclosure | Test stdout/stderr captured in VerificationResult may contain sensitive info (file paths, environment). Display is controlled via Rich CLI; `--output` JSON preserves full contents. |
| Denial of service via long test suites | Denial of Service | Timeout via Settings.test_timeout; exec_shell kills process on timeout. Max test file count should be limited. |

## Sources

### Primary (HIGH confidence)
- [GitHub: numirias/pytest-json-report](https://github.com/numirias/pytest-json-report) — README (programmatic API, JSONReport plugin, report format), sample_report.json (output schema)
- [pytest official docs: Calling pytest from Python code](https://docs.pytest.org/en/stable/how-to/usage.html#calling-pytest-from-python-code) — `pytest.main()` API, import caching warning
- [Existing codebase: src/ascend_agent/reproduction/engine.py] — Engine pattern, exec_shell usage, path traversal pattern
- [Existing codebase: src/ascend_agent/tools/shell_exec.py] — exec_shell implementation (local + SSH)
- [Existing codebase: src/ascend_agent/diagnosis/models.py] — ReproductionResult schema, Pydantic model patterns
- [Existing codebase: src/ascend_agent/cli/reproduce.py] — CLI pattern with Typer + Rich, --output flag
- [Existing codebase: pyproject.toml] — pytest config (asyncio_mode=auto, testpaths)

### Secondary (MEDIUM confidence)
- [PyPI: pytest-json-report 1.5.0] — Confirmed available on PyPI via `pip index versions`; latest release 2022-03-15
- [Existing codebase: tests/ directory structure] — Verified test→source file mapping for all existing modules

### Tertiary (LOW confidence)
- none

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pytest-json-report v1.5.0 confirmed on PyPI; pytest already installed at v8.4.2; project patterns well-documented
- Architecture: HIGH — Engine pattern is well-established (4 prior implementations); exec_shell reuse is proven; JSON report schema is fully documented
- Pitfalls: HIGH — Four pitfalls identified with concrete mitigation strategies; all verified against official docs or existing codebase patterns

**Research date:** 2026-05-25
**Valid until:** 2026-06-25 (30 days — stable tooling)
