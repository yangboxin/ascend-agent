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

### reproduce (stub)

```bash
ascend-agent reproduce run diagnosis.json
```

Not yet implemented — planned for Phase 4.

### fix (stub)

```bash
ascend-agent fix run diagnosis.json
```

Not yet implemented — planned for Phase 3.

## Project Structure

```
ascend-agent/
├── pyproject.toml              # Project metadata, deps, entry point
├── src/
│   └── ascend_agent/
│       ├── __init__.py          # Package init (__version__)
│       ├── __main__.py          # python -m ascend_agent support
│       ├── main.py              # Console_scripts entry point
│       ├── config.py            # pydantic-settings (ASCEND_ env prefix)
│       ├── cli/
│       │   ├── app.py           # Typer app, callback, sub-typer registration
│       │   ├── diagnose.py      # diagnose run command (one-shot + REPL)
│       │   ├── reproduce.py     # Stub (Phase 4)
│       │   └── fix.py           # Stub (Phase 3)
│       ├── context/
│       │   ├── models.py        # Pydantic v2 models (ContextDocument, RepoInfo, TraceInfo...)
│       │   ├── repo.py          # RepoScanner (.gitignore-aware)
│       │   └── trace.py         # TraceParser (regex, 3 input methods)
│       └── tools/
│           ├── server.py        # FastMCP server with 4 tool registrations
│           ├── code_search.py   # Code search (rg + Python fallback)
│           ├── file_edit.py     # Stub (Phase 3)
│           ├── shell_exec.py    # Stub (Phase 4)
│           └── test_runner.py   # Stub (Phase 5)
└── tests/
    ├── conftest.py              # Shared fixtures (sample_trace, sample_repo_dir)
    ├── test_cli.py              # CLI integration tests (CliRunner)
    ├── test_context.py          # Context builder unit tests (7 tests)
    └── test_tools/
        ├── test_server.py       # MCP server tests
        └── test_code_search.py  # Code search integration tests
```

## Architecture

The agent uses a layered architecture:

```
┌─────────────────────────────────────────────┐
│  CLI Layer (Typer + Rich)                   │
│  diagnose | reproduce (stub) | fix (stub)   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Context Builder (Pydantic models)          │
│  RepoScanner + TraceParser → ContextDocument│
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  MCP Tool Layer (subprocess, STDIO)         │
│  code_search (full) + 3 stubs               │
└─────────────────────────────────────────────┘
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
| 2 | Diagnosis Engine | ⏳ Pending |
| 3 | Fix Generation | ⏳ Pending |
| 4 | Reproduction Capability | ⏳ Pending |
| 5 | Verification &闭环 | ⏳ Pending |

## Architecture Constraints

- `print()` must never be used in MCP tools — stdout is the STDIO transport channel
- Use `ctx.info()` or `stderr` for logging in tool functions
- Stack trace parsing is regex-based (no AST), one trace at a time
- Code search restricted to `.py` files in Phase 1
- No SSH/remote support (Phase 4)
- All fix suggestions require human review before application

## License

[License type] — see LICENSE file.
