# Phase 4: Reproduction Capability - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the ability to reproduce diagnosed issues on test machines. Takes a `DiagnosisResult` (from Phase 2/3) with hypotheses, evidence, and repo context, executes commands locally or via SSH to reproduce the issue, and produces a structured reproduction result that feeds Phase 5 (Verification).

**Requirements:** REPRO-01 (Agent can reproduce issues locally or via SSH using provided configuration)

**Success criteria from roadmap:**
1. Agent can execute commands locally to reproduce issues
2. Agent can connect via SSH to remote test machines
3. Agent uses provided configuration (or defaults) for reproduction

</domain>

<decisions>
## Implementation Decisions

### Reproduction Engine Design
- **D-01:** `ReproductionEngine` class following the Engine pattern from Phase 2/3 — constructor takes `router: ModelRouter` + `repo_path: str` + settings, public `reproduce()` method returns structured `ReproductionResult`.
- **D-02:** Multi-step workflow: prepare (parse diagnosis, check environment deps) → execute (run command) → report (capture structured result with stdout/stderr/exit_code).

### Local vs SSH Execution
- **D-03:** Config-based switching — if SSH host is configured (via `ASCEND_SSH_HOST` env var), use asyncssh for remote execution; otherwise run locally using `asyncio.create_subprocess_shell()`.
- **D-04:** Local execution context: same process cwd + inherited environment variables. No separate working directory management.

### SSH Library & Config
- **D-05:** Use `asyncssh` for async-native SSH execution — fits the async MCP tool pattern naturally. No sync wrappers needed.
- **D-06:** Minimal SSH config via env vars: `ASCEND_SSH_HOST`, `ASCEND_SSH_USER`, `ASCEND_SSH_KEY_PATH`. SSH agent is the default key management mechanism.

### Shell Execution Scope
- **D-07:** `exec_shell` MCP tool runs a single command string with a configurable timeout. Returns stdout, stderr, exit code. No script mode — the Engine handles orchestration.
- **D-08:** Non-interactive only — no PTY allocation. Commands requiring TTY interaction are flagged with guidance. STDIO transport limitation is respected.

### Credential & Security Handling
- **D-09:** SSH agent forwarding is the primary authentication method. Falls back to key path from config if the agent is unavailable.
- **D-10:** Local execution includes path traversal protection — validates that command execution stays within the repo boundary. Same pattern as `edit_file`'s path traversal check (Phase 3 D-15).

### Output Format & Phase 5 Contract
- **D-11:** `ReproductionResult` Pydantic model with fields: `status` (success/fail/error), `command`, `stdout`, `stderr`, `exit_code`, `duration_seconds`, `hypothesis_id_tested`, `files_changed`. Structured contract for Phase 5 consumption.
- **D-12:** Output includes `hypothesis_id_tested` to directly map which diagnosis hypothesis was tested. Phase 5 Verification consumes this to confirm or refute fixes.

### Environment Preparation
- **D-13:** ReproductionEngine checks dependencies exist before running the command. Installs missing packages if needed. Sets environment variables from config.
- **D-14:** If the target repo has an active virtualenv/conda environment, respect and use it. The engine does not create or manage virtual environments.

### The Agent's Discretion
- Exact command construction for the reproduction execution.
- Timeout values and retry strategy for transient SSH failures.
- Test approach and coverage targets.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Definition
- `.planning/PROJECT.md` — Project vision, architecture layers (Tool Layer with shell execution and test runner), constraints
- `.planning/REQUIREMENTS.md` — REPRO-01 requirement for Phase 4
- `.planning/ROADMAP.md` — Phase 4 goal, success criteria, full roadmap context (Phase 5 consumes reproduction output)

### Phase 1 Foundation (Consumed by Phase 4)
- `.planning/phases/01-architecture-foundation/01-CONTEXT.md` — D-07 (SSH deferred to Phase 4), D-17 (shell_exec stub), MCP tool layer patterns
- `src/ascend_agent/tools/server.py` — FastMCP server with tool registration pattern (where exec_shell is registered)
- `src/ascend_agent/tools/shell_exec.py` — exec_shell MCP tool stub (target for Phase 4 implementation)
- `src/ascend_agent/config.py` — Settings class with pydantic-settings, ASCEND_ env prefix

### Phase 2 & 3 (Consumed by Phase 4)
- `.planning/phases/02-diagnosis-engine/02-CONTEXT.md` — Engine pattern (ModelRouter, diagnosis workflow)
- `.planning/phases/03-fix-generation/03-CONTEXT.md` — D-21 (FixSuggestion schema stable), DiagnosisOutput wrapper
- `src/ascend_agent/diagnosis/models.py` — DiagnosisResult, DiagnosisOutput, FixSuggestion (stable schemas, D-21)
- `src/ascend_agent/diagnosis/engine.py` — Engine pattern (multi-turn LLM loop, ModelRouter integration)
- `src/ascend_agent/diagnosis/router.py` — ModelRouter abstraction
- `src/ascend_agent/cli/reproduce.py` — Existing CLI stub for Phase 4

### Phase 4 Integration
- `src/ascend_agent/cli/app.py` — Root Typer app with reproduce sub-app already registered
- `src/ascend_agent/tools/file_edit.py` — edit_file path traversal protection pattern (D-10 reference)

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `exec_shell` MCP tool stub (`src/ascend_agent/tools/shell_exec.py`) — exists but returns `{"status": "stub"}`. Phase 4 fills in the implementation.
- `reproduce` CLI stub (`src/ascend_agent/cli/reproduce.py`) — accepts `diagnosis` argument, prints planned features. Phase 4 wires to ReproductionEngine.
- `ModelRouter` (`src/ascend_agent/diagnosis/router.py`) — OpenAI client wrapper. ReproductionEngine uses it if LLM-assisted execution is needed.
- `Engine` pattern (`src/ascend_agent/diagnosis/engine.py`) — Constructor takes `router + repo_path`, public method returns structured result. ReproductionEngine follows same pattern.
- `DiagnosisOutput` (`src/ascend_agent/diagnosis/models.py`) — Wraps ContextDocument + DiagnosisResult. Input contract for reproduction CLI.
- `Settings` class (`src/ascend_agent/config.py`) — Extensible with SSH config fields under `ASCEND_SSH_*` env prefix.

### Established Patterns
- Typer-based CLI with subcommands and Rich terminal output
- Pydantic v2 models with `ConfigDict(extra="forbid")`
- FastMCP for tool layer (async tools, STDIO transport)
- Engine pattern: constructor → public method → structured Pydantic result
- Path traversal protection (edit_file D-15 pattern)
- Async-only MCP tools — all `async def` with `ctx: Context | None`

### Integration Points
- `cli/reproduce.py` CLI command parses diagnosis JSON, dispatches to ReproductionEngine
- `tools/shell_exec.py` MCP tool is the actual execution layer (local subprocess or asyncssh)
- `tools/server.py` registers exec_shell (already wired)
- ReproductionResult model lives in `diagnosis/models.py` alongside other phase contracts
- Phase 5 (Verification) consumes ReproductionResult as input — structured contract (D-12)
- Extend `src/ascend_agent/config.py` Settings with SSH connection parameters

</code_context>

<specifics>
## Specific Ideas

- Follow the same Engine pattern from Phase 2/3 — consistent architecture across all engine components.
- `asyncssh` was chosen over `paramiko` specifically because it fits the async MCP tool pattern without sync-wrapping.
- SSH agent forwarding avoids storing keys in env vars — follows security best practices.
- Path traversal protection reuses the same validation pattern from edit_file (Phase 3 D-15) for consistency.
- Start simple with single command execution + timeout. The Engine's multi-step workflow handles orchestration.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-repo support** — enhancement to ARCH-01. Currently single-repo only. Deferred to a future phase.
- **Multi-log ingestion with earliest-error tracing** — enhancement to DIAG-01/02. Currently single-trace analysis. Deferred to a future phase.
- **Multi-modal file input** (screenshots, .log, .txt, .pdf) — enhancement to ARCH-02. Currently text-only. Deferred to a future phase.
- **Provider/model setup CLI wizard** — new capability. Currently OpenAI-only via env vars. Deferred to a future architecture phase.

</deferred>

---

*Phase: 4-Reproduction Capability*
*Context gathered: 2026-05-25*
