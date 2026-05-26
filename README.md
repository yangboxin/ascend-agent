# Ascend Diagnostic Agent

AI-powered diagnostic tool for the Ascend maintenance team — analyze stack traces against Python codebases, diagnose root causes, and generate fixes 10x faster.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Show available commands
ascend-agent --help

# Diagnose a stack trace against a code repository
ascend-agent diagnose run /path/to/repo --trace-text "ValueError: test"

# Or via a trace file
ascend-agent diagnose run /path/to/repo --trace /path/to/trace.log

# Or pipe stdin
echo "ZeroDivisionError: division by zero" | ascend-agent diagnose run /path/to/repo

# Interactive REPL mode
ascend-agent diagnose run /path/to/repo --interactive
```

## Installation

**Requires Python 3.10+**

```bash
git clone <repo-url>
cd ascend-agent
pip install -e ".[dev]"
```

This installs the `ascend-agent` CLI and all dependencies (Typer, Rich, Pydantic, MCP SDK).

## Usage

### diagnose — Analyze a stack trace against a code repository

The `diagnose run` command accepts a repository path (required) and a stack trace via one of three input methods:

| Method | Flag | Example |
|--------|------|---------|
| File path | `--trace` | `--trace /var/log/error.log` |
| Inline text | `--trace-text` | `--trace-text "ValueError: oops"` |
| stdin pipe | _(auto-detected)_ | `echo "Error" \| ascend-agent diagnose ...` |

#### Output

```
Ascend Diagnostic Agent
Building context...

      Repository Info
┌──────────┬──────────────────────────┐
│ Property │ Value                    │
├──────────┼──────────────────────────┤
│ Path     │ /home/user/vllm-ascend   │
│ Language │ python                   │
│ Files    │ 142                      │
│ Structure│ main.py, utils/...       │
└──────────┴──────────────────────────┘

Error: ValueError
Invalid dimension: expected 4096, got 8192

Stack Trace:
  api_server.py:245 create_chat_completion
  async_llm_engine.py:89 generate
  async_llm_engine.py:156 _run_engine

Environment: Python 3.10.8 on darwin
```

#### REPL mode

```bash
ascend-agent diagnose run /path/to/repo --interactive
```

Interactive mode provides a prompt where you can:
- Paste stack traces for immediate analysis
- `:repo <path>` — rescan a different repository
- `:output` — print current context as JSON
- `:help` — list commands
- `:quit` — exit

#### JSON output

```bash
ascend-agent diagnose run /path/to/repo --trace error.log --output context.json
```

### reproduce — Reproduce diagnosed issues as shell commands

```bash
ascend-agent reproduce run diagnosis.json
ascend-agent reproduce run diagnosis.json --output reproduction.json
```

Evaluates each diagnosis hypothesis, constructs reproduction commands (pytest or python) from the evidence file paths, executes them locally or via SSH (ASCEND_SSH_HOST), and displays structured results (status, command, exit code, stdout/stderr, duration).

### fix — Generate and review code fixes

```bash
ascend-agent fix run diagnosis.json
ascend-agent fix run diagnosis.json --output accepted.json
```

Generates fix suggestions for each diagnosis hypothesis using the LLM. Presents an interactive review workflow (Accept/Skip/Reject per suggestion with Rich syntax-highlighted diffs), applies accepted fixes via search-and-replace with `.bak` backup, and optionally saves accepted fixes as JSON.

### verify — Run tests to verify fixes

```bash
ascend-agent verify run reproduction.json
ascend-agent verify run reproduction.json --output verification.json
```

Auto-detects the test framework (pytest), maps changed source files to corresponding test files, executes only relevant tests via `pytest --json-report`, and produces a structured pass/fail report with per-test details.

### Provider selection

All commands support `--provider` for LLM provider selection:

```bash
# Use DeepSeek
ascend-agent --provider deepseek diagnose run /path/to/repo --trace-text "Error"

# Per-command override
ascend-agent diagnose run --provider qwen /path/to/repo --trace-text "Error"
```

Supported providers: `openai` (default), `deepseek`, `qwen`. Configure via `ASCEND_*_API_KEY` env vars.

## Project Structure

```
ascend-agent/
├── pyproject.toml                  # Project metadata, deps, entry point
├── src/
│   └── ascend_agent/
│       ├── __init__.py            # Package init (__version__)
│       ├── __main__.py            # python -m support
│       ├── main.py                # Console_scripts entry point
│       ├── config.py              # pydantic-settings (ASCEND_ env prefix)
│       ├── cli/
│       │   ├── app.py             # Typer app, callback, sub-typer registration
│       │   ├── diagnose.py        # diagnose run command (one-shot + REPL)
│       │   ├── fix.py             # fix run command (review workflow + batch apply)
│       │   ├── reproduce.py       # reproduce run command (local + SSH)
│       │   └── verify.py          # verify run command (test execution + reporting)
│       ├── context/
│       │   ├── models.py          # Pydantic models (ContextDocument, RepoInfo, TraceInfo)
│       │   ├── repo.py            # RepoScanner (.gitignore-aware)
│       │   └── trace.py           # TraceParser (regex, 3 input methods)
│       ├── diagnosis/
│       │   ├── models.py          # All Pydantic models (Evidence, Hypothesis, FixSuggestion, ...)
│       │   ├── router.py          # ModelRouter, create_router, ProviderConfig
│       │   ├── engine.py          # Diagnosis engine (LLM-driven search loop)
│       │   └── fix_engine.py      # Fix generation engine
│       ├── reproduction/
│       │   └── engine.py          # Reproduction engine (command construction + execution)
│       ├── verification/
│       │   └── engine.py          # Verification engine (test framework detection + execution)
│       └── tools/
│           ├── server.py          # FastMCP server with 4 tool registrations
│           ├── code_search.py     # Code search (ripgrep + Python fallback)
│           ├── file_edit.py       # Search-and-replace file editing with .bak backup
│           ├── shell_exec.py      # Shell execution (local + SSH via asyncssh)
│           └── test_runner.py     # Test execution via VerificationEngine
└── tests/
    ├── conftest.py                # Shared fixtures
    ├── test_cli.py                # CLI integration tests (12 tests)
    ├── test_context.py            # Context builder unit tests (7 tests)
    ├── test_diagnosis/            # Engine + router + fix tests (50 tests)
    ├── test_reproduction/         # Reproduction tests (13 tests)
    ├── test_tools/                # MCP tool tests (19 tests)
    └── test_verification/         # Verification tests (19 tests)
```

## Architecture

The agent uses a layered architecture:

```
┌───────────────────────────────────────────────┐
│  CLI Layer (Typer + Rich)                     │
│  diagnose | fix | reproduce | verify          │
│  --provider openai|deepseek|qwen              │
└───────────────────┬───────────────────────────┘
                    │
┌───────────────────▼───────────────────────────┐
│  Engine Layer (4 engines, Pydantic results)   │
│  Engine | FixEngine | ReproductionEngine      │
│  VerificationEngine                           │
└───────────────────┬───────────────────────────┘
                    │
┌───────────────────▼───────────────────────────┐
│  Model Router (create_router + ModelRouter)   │
│  ProviderConfig | PROVIDER_DEFAULTS           │
│  .parse() → json.loads fallback on 400        │
│  openai | deepseek | qwen                     │
└───────────────────┬───────────────────────────┘
                    │
┌───────────────────▼───────────────────────────┐
│  Context Builder (Pydantic models)            │
│  RepoScanner + TraceParser → ContextDocument  │
└───────────────────┬───────────────────────────┘
                    │
┌───────────────────▼───────────────────────────┐
│  MCP Tool Layer (subprocess, STDIO)           │
│  code_search | edit_file | exec_shell         │
│  run_test (local + SSH via asyncssh)          │
└───────────────────────────────────────────────┘
```

Key design decisions:
- **CLI and MCP server are separate processes** — the CLI launches the agent workflow; the MCP server runs as a subprocess providing tools to the orchestrator (Phase 2+)
- **Three trace input methods** — file (`--trace`), stdin pipe, inline paste (`--trace-text`)
- **No caching** — fresh repo scan per invocation
- **Context schema** — `ContextDocument` (Pydantic) with `repo_info + trace_info + config_env`

## Development

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run a specific test file
python3 -m pytest tests/test_context.py -v

# Start the MCP server standalone (for testing)
python3 -m ascend_agent.tools.server
```

### Dependencies

| Library | Purpose |
|---------|---------|
| `typer` | CLI framework (type-hint based, Rich integration) |
| `rich` | Terminal output formatting (tables, colors, syntax) |
| `pydantic` | Data validation, context model schemas |
| `pydantic-settings` | Environment/config management (12-factor) |
| `mcp` | Model Context Protocol server (FastMCP) |

### Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | Architecture Foundation | ✅ Complete |
| 2 | Diagnosis Engine | ✅ Complete |
| 3 | Fix Generation | ✅ Complete |
| 4 | Reproduction Capability | ✅ Complete |
| 5 | Verification &闭环 | ✅ Complete |
| 6 | Provider Routing Foundation | ✅ Complete |
| 7 | Chinese Model Integration | ✅ Complete |
| 8 | Multi-Repo Support | ⏳ Planned |
| 9 | Provider & Multi-Repo Testing | ⏳ Planned |

## Architecture Constraints

- `print()` must never be used in MCP tools — stdout is the STDIO transport channel
- Use `ctx.info()` or `stderr` for logging in tool functions
- Stack trace parsing is regex-based (no AST), one trace at a time
- Code search restricted to `.py` files
- SSH/remote support via `ASCEND_SSH_HOST` env var (asyncssh, known_hosts=None for internal test machines)
- All fix suggestions require human review before application (review workflow)
- Provider routing via `ASCEND_*_API_KEY` env vars and `--provider` flag
- Structured output fallback: `.parse()` → `json.loads` on 400 errors (transparent to callers)

## License

[License type] — see LICENSE file.
