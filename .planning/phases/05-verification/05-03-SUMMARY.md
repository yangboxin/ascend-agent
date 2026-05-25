---
plan: 05-03
phase: 05-verification
status: complete
completed: 2026-05-25
tasks:
  - name: "Implement run_test MCP tool + update server.py description"
    status: complete
    notes: "run_test replaces stub with full VerificationEngine orchestration, accepts ReproductionResult JSON, returns VerificationResult JSON. Server description updated."
  - name: "Create verify CLI command + register in app.py"
    status: complete
    notes: "verify.py with verify run subcommand, Rich display (status, framework, counts, per-test table), --output flag, app.py registration"
  - name: "Create verify CLI integration tests"
    status: complete
    notes: "3 tests: test_verify_help, test_verify_run_with_fixture, test_verify_output_json. Sample reproduction fixture created."
---

# Plan 05-03 Summary: CLI & MCP Tool Wiring

## What Was Built

### MCP Tool (`src/ascend_agent/tools/test_runner.py`)
- `run_test` — async function replacing Phase 1 stub
- Accepts `reproduction_json: str`, `repo_path: str | None = None`, `timeout: int = 300`, `ctx: Context | None = None`
- Parses ReproductionResult JSON, initializes VerificationEngine, returns VerificationResult JSON
- Graceful error handling for invalid JSON and execution failures

### Server Registration (`src/ascend_agent/tools/server.py`)
- `run_test` description updated — no more `[STUB]` marker

### CLI (`src/ascend_agent/cli/verify.py`)
- `verify_app` Typer subcommand with `verify run` command
- Full Rich display: status (color-coded), framework, command, counts, duration, summary
- Per-test details table (green for pass, red for fail/error)
- `--output/-o` flag for JSON persistence
- Exits code 1 on fail/error/timeout, exits 0 on pass/no_tests

### App Registration (`src/ascend_agent/cli/app.py`)
- `verify_app` imported and registered after fix_app

### Test Fixture (`tests/fixtures/sample_reproduction.json`)
- Valid ReproductionResult JSON for CLI integration testing

### Tests (`tests/test_verification/test_cli.py`)
- 3 tests: help display, mock engine execution, --output JSON persistence

## Key Integration Points
- CLI follows reproduce.py pattern (asyncio.run, Typer, Rich display)
- run_test follows exec_shell MCP tool pattern (async, lazy imports, JSON return)
- VerificationEngine wired via lazy imports inside method body
- Existing commands (diagnose, reproduce, fix) unaffected
