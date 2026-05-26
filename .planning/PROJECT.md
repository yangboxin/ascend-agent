# Ascend Diagnostic Agent

## What This Is

An AI agentic system for the Ascend maintenance team to diagnose and fix issues in Python codebases (starting with vllm-ascend). The agent analyzes code and stack traces, proposes hypotheses with evidence, suggests fixes for human review, reproduces issues on test machines (local or SSH), and verifies solutions by running relevant tests.

**Shipped:** v1.0 MVP (2026-05-25) — full diagnostic pipeline: diagnose → fix → reproduce → verify

## Core Value

Enable the Ascend maintenance team to diagnose and fix production issues 10x faster by automating the investigation, reproduction, and verification loop.

## Current State

- **Version:** v1.0 MVP (shipped 2026-05-25)
- **Architecture:** Typer CLI → Engine pattern (4 engines) → MCP tool layer → ModelRouter (OpenAI)
- **Source code:** ~2,756 LOC Python (src/) | ~2,044 LOC tests (tests/)
- **Key capabilities:**
  - CLI: `ascend-agent diagnose run`, `fix run`, `reproduce run`, `verify run`
  - MCP tools: `code_search`, `edit_file`, `exec_shell`, `run_test`
  - Local and SSH execution for reproduction/verification
- **Limitations:**
  - Requires Python 3.10+ runtime
  - asyncssh install pending (same version constraint)
  - pytest-json-report required in target environment for verification
  - Full test suite mode deferred (--full flag)

## Current Milestone: v1.1 Multi-Provider & Multi-Repo

**Goal:** Add LLM provider flexibility (Claude, Gemini, Ollama, Qwen, DeepSeek) with per-task cost optimization, and extend to multi-repo support.

**Target features:**
- Provider-agnostic ModelRouter supporting OpenAI, Anthropic, Google, Ollama, Chinese models
- Per-task model routing via env vars + config file
- Multi-repo support — diagnose/reproduce/verify across multiple target repos
- Cost optimization — cheap models for simple tasks, capable models for complex reasoning

## Requirements

### Validated (shipped in v1.0)

- ✓ **ARCH-01**: Agent can ingest Python code repositories — v1.0 (RepoScanner)
- ✓ **ARCH-02**: Agent can ingest stack traces and log files — v1.0 (TraceParser)
- ✓ **DIAG-01**: Agent can analyze stack traces, propose hypotheses — v1.0 (Engine + LLM)
- ✓ **DIAG-02**: Agent can locate relevant source code — v1.0 (code_search + AST)
- ✓ **FIX-01**: Agent can generate code fixes — v1.0 (FixEngine)
- ✓ **FIX-02**: Agent can suggest fixes for human review — v1.0 (review workflow)
- ✓ **REPRO-01**: Agent can reproduce issues (local/SSH) — v1.0 (ReproductionEngine)
- ✓ **VERIF-01**: Agent can run tests to verify fixes — v1.0 (VerificationEngine)
- ✓ **VERIF-02**: Agent can report verification results — v1.0 (verify CLI)

### Active (for next milestone)

(None yet — define with `/gsd-new-milestone`)

### Out of Scope (confirmed)

| Item | Reason |
|------|--------|
| Agent auto-applies fixes without review | Safety critical — fixes must be reviewed |
| Support for non-Python languages | Focus on Python first |
| Real-time monitoring | Diagnostic tool, not monitoring |

## Architecture Layers

The agent uses a layered architecture:

1. **CLI Interaction Layer** — Typer commands with Rich terminal output (4 subcommands)
2. **Context Builder** — Gathers and structures problem context (repo + trace + config)
3. **Orchestrator (Engine)** — 4 engines: Diagnosis, Fix, Reproduction, Verification
4. **Model Router** — Routes requests to OpenAI with structured outputs (Pydantic)
5. **Tool Layer** — 4 MCP tools: code_search, edit_file, exec_shell, run_test

## Context

- **Primary codebase**: vllm-ascend (target for diagnosis/reproduction/verification)
- **Initial use case**: Analyze runtime errors, logic bugs, performance issues, test failures
- **Target environment**: Internal Ascend test machines (SSH accessible)
- **Team**: Ascend maintenance team
- **Total codebase**: ~4,800 LOC (source + tests), 81 commits, 127 files

## Constraints

- **Tech Stack**: Typer, Rich, Pydantic v2, FastMCP, OpenAI SDK, pytest
- **Python**: Requires 3.10+ (asyncssh, union type syntax)
- **Execution**: Local subprocess + SSH (asyncssh) via ASCEND_SSH_HOST env var
- **Review**: All code fixes must be reviewed by human before application
- **Verification**: All fixes verified by running relevant tests (not full suite by default)
- **Path Safety**: Path traversal protection on all file operations (resolve + startswith)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Agent output: Suggest and review | Safety critical — fixes must be reviewed | ✓ Good — Phase 3 review workflow |
| Target: vllm-ascend first | Real production use case to validate | ✓ Good — full pipeline built |
| Problem types: All (runtime, logic, performance, tests) | Comprehensive coverage needed | ✓ Good — engine handles all |
| Pydantic v2 with extra="forbid" | Type safety across all models | ✓ Good — consistent across 5 phases |
| ModelRouter: Concrete class (not Protocol) | Simpler implementation | ✓ Good — Phase 2, reused in 3, 4, 5 |
| exec_shell: Local subprocess + asyncssh | Dual execution mode | ✓ Good — Phase 4, reused in 5 |
| VerificationEngine: Deterministic (no LLM) | Import caching issues with pytest.main() | ✓ Good — subprocess approach |
| Subprocess for test execution | Avoids pytest.main() import caching | ✓ Good — fresh process per run |

---

*Last updated: 2026-05-25 after v1.0 milestone*
