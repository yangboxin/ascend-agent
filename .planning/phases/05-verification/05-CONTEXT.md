# Phase 5: Verification &闭环 - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement test verification of fixes — consume `ReproductionResult` from Phase 4, run relevant tests against the repo, and produce a structured pass/fail report with details and summary. This is the final phase in the diagnostic pipeline: Diagnose → Fix → Reproduce → Verify.

**Requirements:** VERIF-01 (Agent can run tests to verify fixes), VERIF-02 (Agent can report verification results)

**Success criteria from roadmap:**
1. Agent runs relevant tests to verify fixes
2. Agent reports pass/fail status with details
3. Agent provides summary of what was verified

</domain>

<decisions>
## Implementation Decisions

### Test Discovery & Execution
- **D-01:** Auto-detect the test framework by probing the target repo for pytest config files (pytest.ini, pyproject.toml [tool.pytest], setup.cfg). Fall back to `pytest` if detected. Report inability to verify if no supported framework is found.
- **D-02:** Run only relevant tests — map `files_changed` from `ReproductionResult` to their corresponding test files using a heuristic (e.g., `src/foo.py` → `tests/test_foo.py`, `tests/foo_test.py`). Do not run the full test suite by default.
- **D-03:** Parse test results using structured JSON output (`pytest --json-report`). Extract pass/fail/error counts, per-test details, and durations. Requires `pytest-json-report` plugin as a dependency.
- **D-04:** Reuse the exec_shell MCP tool pattern from Phase 4 for test execution. Local subprocess by default; SSH via `ASCEND_SSH_HOST` when configured. Same environment as reproduction.

### The Agent's Discretion
- Exact test file mapping heuristic (e.g., strip `src/` → prepend `tests/test_`, glob for `*_test.py`, etc.)
- Pydantic model structure for `VerificationResult` (pass/fail/error counts, per-test details, summary)
- Construction of `VerificationEngine` class (follows existing Engine pattern: constructor + public method → structured result)
- `verify` CLI command design (Typer subcommand with Rich display)
- Timeout values and retry strategy for test execution
- Whether verification engine uses LLM assistance (ModelRouter) or is purely deterministic

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Definition
- `.planning/PROJECT.md` — Project vision, architecture layers, constraints (verification requirement, human review requirement)
- `.planning/REQUIREMENTS.md` — VERIF-01 and VERIF-02 requirements for Phase 5
- `.planning/ROADMAP.md` — Phase 5 goal, success criteria, full roadmap context

### Phase 4 (Input Contract)
- `.planning/phases/04-reproduction-capability/04-CONTEXT.md` — ReproductionResult schema (D-11, D-12), exec_shell MCP tool pattern, Engine pattern
- `src/ascend_agent/diagnosis/models.py` — ReproductionResult model (status, command, stdout, stderr, exit_code, duration_seconds, hypothesis_id_tested, files_changed) — stable input contract for Phase 5
- `src/ascend_agent/tools/shell_exec.py` — exec_shell MCP tool implementation (reused for test execution, D-04)

### Phase 5 Integration Points
- `src/ascend_agent/tools/test_runner.py` — run_test MCP tool stub (target for implementation)
- `src/ascend_agent/tools/server.py` — FastMCP server where run_test is registered
- `src/ascend_agent/cli/app.py` — Root Typer app where verify CLI will be registered
- `src/ascend_agent/config.py` — Settings class with SSH config fields (ASCEND_SSH_HOST, etc.)

### Phase 1-3 Patterns
- `.planning/phases/01-architecture-foundation/01-CONTEXT.md` — Typer CLI patterns, Rich output conventions, MCP tool layer
- `.planning/phases/02-diagnosis-engine/02-CONTEXT.md` — Engine pattern (constructor + public method → structured Pydantic result)
- `.planning/phases/03-fix-generation/03-CONTEXT.md` — FixSuggestion stable schema (D-21), path traversal protection pattern

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `exec_shell` MCP tool (`src/ascend_agent/tools/shell_exec.py`) — fully implemented async shell exec with local/SSH routing. Reused directly for running test commands (D-04).
- `run_test` MCP tool stub (`src/ascend_agent/tools/test_runner.py`) — returns stub JSON. Phase 5 fills in the implementation.
- `ReproductionResult` model (`src/ascend_agent/diagnosis/models.py`) — input contract with `files_changed`, `hypothesis_id_tested`, `status`, `stdout`, `stderr`, `exit_code`, `duration_seconds`.
- `Engine` pattern (`src/ascend_agent/diagnosis/engine.py`, `src/ascend_agent/diagnosis/fix_engine.py`, `src/ascend_agent/reproduction/engine.py`) — constructor takes router + repo_path, public method returns structured Pydantic result. VerificationEngine follows this pattern.
- `ModelRouter` (`src/ascend_agent/diagnosis/router.py`) — OpenAI client wrapper with structured outputs via `.parse()`. Available if LLM-assisted verification is needed.
- `Settings` class (`src/ascend_agent/config.py`) — extensible with `ASCEND_*` env prefix. SSH config fields already present.

### Established Patterns
- Typer-based CLI with subcommands and Rich terminal output (Panel, Syntax, color-coded status)
- Pydantic v2 models with `ConfigDict(extra="forbid")`
- FastMCP for tool layer (async tools with `ctx: Context | None`)
- Engine pattern: constructor(router, repo_path) → public method → structured Pydantic result
- Path traversal protection (edit_file D-15 pattern) — applicable if writing verification output files
- CLI commands accept `--output` flag for JSON persistence (diagnose, fix, reproduce)

### Integration Points
- `verify` CLI command (to be created) — new Typer subcommand registered in `app.py`, similar pattern to `reproduce.py`
- `run_test` MCP tool (to be implemented) — already registered in `server.py` as stub
- `VerificationResult` Pydantic model (to be created) — lives in `diagnosis/models.py` alongside other phase contracts
- Phase 5 consumes `ReproductionResult` JSON (from `reproduce --output`) as its primary input
- Phase 5 is the final phase — produces terminal verification summary, no downstream consumers

</code_context>

<specifics>
## Specific Ideas

- Follow the same Engine pattern from Phases 2-4 — consistent architecture across all engine components.
- pytest-json-report is a well-established plugin for structured test output parsing — low-risk dependency.
- Test file mapping heuristic should be straightforward for the vllm-ascend codebase (conventional src/tests mirroring).
- The user chose auto-detection and relevant-test-only scope — keep the verify command simple with minimal required flags.
- Verification is the final validation step before the human signs off — the report should be clear and actionable.

</specifics>

<deferred>
## Deferred Ideas

- **Full test suite mode** — Running all tests as a final gate. Deferred to keep scope focused on targeted per-fix verification. Could be a `--full` flag in a future enhancement.
- **Custom test command flag** — Letting the user override the test command. Deferred until auto-detection proves insufficient for non-pytest repos.
- **Custom parsing rules** — Regex-based parsers for non-pytest test frameworks. Deferred until multi-framework support is needed.

</deferred>

---

*Phase: 5-Verification*
*Context gathered: 2026-05-25*
