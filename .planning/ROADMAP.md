# Roadmap: Ascend Diagnostic Agent

**Created:** 2025-05-20

---

## Phase 1: Architecture Foundation ✅
**Goal:** Build the core infrastructure layers — CLI interaction, context builder, and tool layer foundation.
**Completed:** 2026-05-21

**Requirements:** ARCH-01, ARCH-02

**Success Criteria:**
1. ✅ Agent can accept code repository path as input (local)
2. ✅ Agent can accept stack traces/logs as input (file or pasted text)
3. ✅ CLI interface exists for running the agent

**Plans (5 in 4 waves):**

**Wave 1 *(foundation)* — Plan 01-01** ✅
- Project scaffold, pyproject.toml, Pydantic models (RepoInfo, TraceInfo, ConfigEnv, ContextDocument), config/settings, test infrastructure

**Wave 2 *(parallel — context builder + MCP server)* — Plans 01-02, 01-04** ✅
- 01-02: RepoScanner (pathlib + .gitignore), TraceParser (regex), 7 unit tests ✅
- 01-04: FastMCP server, code search tool (rg + Python fallback), 3 tool stubs ✅

**Wave 3 *(CLI integration)* — Plan 01-03** ✅
- Typer app, diagnose command, Rich output, three input methods, visual verify checkpoint ✅

**Wave 4 *(UAT gap closure)* — Plan 01-05** ✅
- CLI no-args shows full help (ctx.get_help()), MCP server stderr startup banner, code_search tool name correction

**Cross-cutting constraints:**
- `print()` must never be used in MCP tools — use `ctx.info()` or `stderr`
- No SSH/remote support (Phase 4)
- Code search restricted to `.py` files in Phase 1
- MCP server startup message goes to stderr exclusively (stdout is JSON-RPC transport)

---

## Phase 2: Diagnosis Engine ✅
**Goal:** Implement the core diagnosis capability — analyze stack traces, locate source code, generate hypotheses.
**Completed:** 2026-05-21

**Requirements:** DIAG-01, DIAG-02

**Success Criteria:**
1. ✅ Agent parses stack traces and extracts error locations (TraceParser — Phase 1)
2. ✅ Agent searches codebase to find relevant source files (Engine + code_search — Phase 2)
3. ✅ Agent proposes hypotheses with evidence (code snippets, line numbers) (Engine.diagnose + Rich display — Phase 2)

**Plans (3 in 3 waves):**

**Wave 1 *(foundation)* — Plan 02-01** ✅
- Pydantic models (Hypothesis, Evidence, SearchDecision, DiagnosisResult), ModelRouter abstraction (OpenAI client wrapper), Wave 0 test infrastructure ✅
- Key deliverables: `src/ascend_agent/diagnosis/` package with 6 models + ModelRouter + 10 tests

**Wave 2 *(engine core)* — Plan 02-02** ✅
- Engine class with LLM-driven search loop (max 3 iterations), AST-based function body extraction utility, engine unit tests ✅

**Wave 3 *(CLI integration)* — Plan 02-03** ✅
- Wire Engine into `diagnose run` command, Rich-formatted diagnosis result display, CLI integration tests, human-verify checkpoint ✅
- Implementation complete, human-verify approved ✅

**Cross-cutting constraints:**
- `openai` SDK >=2.37.0 for LLM calls with structured outputs
- Model router configured via `ASCEND_DIAGNOSIS_MODEL` env var (default `gpt-4o`)
- No cross-reference following, no error categorization (Phase 2 scope)
- Engine is silent — no clarifying questions

---

## Phase 3: Fix Generation ✅
**Goal:** Generate code fixes based on diagnosis findings.
**Completed:** 2026-05-21

**Requirements:** FIX-01, FIX-02

**Success Criteria:**
1. ✅ Agent generates fix suggestions based on diagnosis
2. ✅ Agent presents fixes for human review (not auto-apply)
3. ✅ Agent can explain the reasoning behind each fix

**Plans (3 in 2 waves):**

**Wave 1 *(parallel)* — Plans 03-01, 03-03** ✅
- 03-01: Pydantic models (FixSuggestion, FixGenerationResult, FixResponse, DiagnosisOutput), FixEngine class with multi-turn LLM strategy, `diagnose.py --output` update, Wave 0 test infrastructure ✅
- 03-03: edit_file MCP tool with search-and-replace, .bak backup, atomic multi-replacement validation ✅

**Wave 2 *(blocked on Wave 1)* — Plan 03-02** ✅
- 03-02: `fix run` CLI (file/stdin), sequential human review workflow (Accept/Skip/Reject), batch application, `--output` audit file, CLI integration tests ✅

**Cross-cutting constraints:**
- All fixes reviewed by human before application (no auto-apply)
- edit_file blocks path traversal — `file_path` must resolve within repo
- FixEngine reuses ModelRouter from Phase 2 with `ASCEND_FIX_MODEL` env var (default `gpt-4o`)
- Fixes use search-and-replace internally; unified diff computed via `difflib.unified_diff()` for display

---

## Phase 4: Reproduction Capability
**Goal:** Reproduce issues on test machines using provided configuration.

**Requirements:** REPRO-01

**Success Criteria:**
1. Agent can execute commands locally to reproduce issues
2. Agent can connect via SSH to remote test machines
3. Agent uses provided configuration (or defaults) for reproduction

**Plans:** 5 plans in 3 waves

**Wave 1 *(parallel — foundation)* — Plans 04-01, 04-02, 04-03**
- [ ] 04-01-PLAN.md — Add asyncssh>=2.23.0 to pyproject.toml, install with package legitimacy checkpoint, add SSH config fields (ssh_host, ssh_user, ssh_key_path, shell_timeout) to Settings (D-06)
- [ ] 04-02-PLAN.md — Add ReproductionResult Pydantic model to diagnosis/models.py (D-11, D-12), create test_reproduction package with conftest.py fixtures and test_models.py (6 tests)
- [ ] 04-03-PLAN.md — Replace exec_shell stub with full async implementation (local subprocess + remote SSH via asyncssh), create test_shell_exec.py (6 tests), update server.py description

**Wave 2 *(engine)* — Plan 04-04**
- [ ] 04-04-PLAN.md — Create reproduction package with ReproductionEngine class (prepare→execute→report workflow, venv detection D-14, path traversal protection D-10, heuristic command construction), create test_engine.py (8 tests)

**Wave 3 *(CLI integration)* — Plan 04-05**
- [ ] 04-05-PLAN.md — Wire reproduce CLI to ReproductionEngine with Rich display and --output flag, add CLI integration tests (3 tests), human-verify checkpoint for end-to-end workflow

**Cross-cutting constraints:**
- asyncssh is a NEW dependency — pip install gated behind package legitimacy checkpoint
- exec_shell MCP tool handles both local (asyncio subprocess) and remote (asyncssh) execution
- exec_shell uses `known_hosts=None` — acceptable for internal test machines
- Shell injection prevention delegated to Engine layer (commands built from trusted diagnosis data)
- ReproductionResult is the structured contract for Phase 5 Verification consumption
- No PTY allocation per D-08 — all execution is non-interactive

---

## Phase 5: Verification &闭环
**Goal:** Verify fixes by running tests and reporting results.

**Requirements:** VERIF-01, VERIF-02

**Success Criteria:**
1. Agent runs relevant tests to verify fixes
2. Agent reports pass/fail status with details
3. Agent provides summary of what was verified

---

## Summary

| Phase | Name | Requirements | Success Criteria |
|-------|------|--------------|------------------|
| 1 | Architecture Foundation ✅ | ARCH-01, ARCH-02 | 3 ✓ |
| 2 | Diagnosis Engine ✅ | DIAG-01, DIAG-02 | 3 ✓ |
| 3 | Fix Generation ✅ | FIX-01, FIX-02 | 3 ✓ |
| 4 | Reproduction Capability 📋 | REPRO-01 | 3 (planned 5 plans in 3 waves) |
| 5 | Verification &闭环 | VERIF-01, VERIF-02 | 3 |

**Total: 5 phases (3 complete, 2 planned) | 9 requirements | 15 success criteria**

---

*Roadmap created: 2025-05-20*
