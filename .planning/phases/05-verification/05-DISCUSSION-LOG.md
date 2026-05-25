# Phase 05: Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 05-verification
**Areas discussed:** Test Discovery

---

## Test Discovery

### How should the verification engine discover which test suite to run?

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-detect test framework (Recommended) | Probe the repo for pytest.ini/pyproject.toml[tool.pytest]/setup.cfg. Fall back to 'pytest' if found | ✓ |
| User specifies test command | Accept a --test-command flag on the verify CLI | |
| Support pytest only | Hardcode pytest as the only runner | |

**User's choice:** Auto-detect test framework

### Which tests should the verification engine run?

| Option | Description | Selected |
|--------|-------------|----------|
| Relevant tests only (Recommended) | Map files_changed to their corresponding test files and run only those | ✓ |
| Full test suite | Run all tests every time | |
| User-specified paths | Accept --test-path flag for specific test files | |

**User's choice:** Relevant tests only

### How should the engine parse and report test results?

| Option | Description | Selected |
|--------|-------------|----------|
| Parse pytest JSON output (Recommended) | Use pytest --json-report for structured results | ✓ |
| Report raw stdout/stderr | Capture raw command output without parsing | |
| Custom parsing rules | Write regex-based parsers for common formats | |

**User's choice:** Parse pytest JSON output

### How should the test runner handle test execution environment?

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse reproduction pattern (Recommended) | Same exec_shell MCP tool — local default, SSH via config | ✓ |
| Local only | Always run tests locally | |
| Requires explicit --test-env flag | User must choose local/remote for every run | |

**User's choice:** Reuse reproduction pattern

---

## the agent's Discretion

- Exact test file mapping heuristic implementation
- Pydantic model structure for VerificationResult
- Construction of VerificationEngine class
- verify CLI command design (Typer subcommand, Rich display)
- Timeout values and retry strategy for test execution
- Whether verification engine uses LLM assistance (ModelRouter)

## Deferred Ideas

- Full test suite mode (--full flag) — future enhancement
- Custom test command flag (--test-command) — deferred until non-pytest repos needed
- Custom parsing rules for non-pytest frameworks — deferred until multi-framework support needed
