# Ascend Diagnostic Agent

AI-powered diagnostic tool for the Ascend maintenance team — analyze stack traces against Python codebases, diagnose root causes, and generate fixes 10x faster.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Start interactive REPL (recommended)
ascend-agent
# or explicitly:
ascend-agent chat

# Diagnose a stack trace against a code repository
ascend-agent diagnose run /path/to/repo --trace-text "ValueError: test"

# Or via a trace file
ascend-agent diagnose run /path/to/repo --trace /path/to/trace.log

# Or pipe stdin
echo "ZeroDivisionError: division by zero" | ascend-agent diagnose run /path/to/repo
```

## Installation

**Requires Python 3.10+**

```bash
git clone <repo-url>
cd ascend-agent
pip install -e ".[dev]"
```

This installs the `ascend-agent` CLI and all dependencies.

## Usage

### Interactive REPL

```bash
ascend-agent
# or
ascend-agent chat
# Resume a previous session
ascend-agent chat --resume <thread_id>
```

The REPL features streaming token-by-token output and automatic session saving.
Slash commands:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/models` | Show current model, or `/models use <id>` to switch |
| `/tools` | List registered runtime tools |
| `/permissions` | Show current permission mode |
| `/plan` | Enter read-only plan mode |
| `/exit-plan` | Return to default permissions |
| `/sessions` | List saved sessions |
| `/reset` | Start a new conversation session |
| `/quit` | Exit (auto-saves current session) |

### Diagnose — Analyze a stack trace against a code repository

```bash
ascend-agent diagnose run /path/to/repo --trace-text "ValueError: oops"
ascend-agent diagnose run /path/to/repo --trace error.log
echo "Error" | ascend-agent diagnose run /path/to/repo
ascend-agent diagnose run /path/to/repo --trace error.log --output diagnosis.json
```

Three input methods: `--trace` (file), `--trace-text` (inline), or stdin pipe.

### Fix — Generate and review code fixes

```bash
ascend-agent fix run diagnosis.json
ascend-agent fix run diagnosis.json --output accepted.json
```

Interactive review workflow with Rich syntax-highlighted diffs (Accept / Skip / Reject).

### Reproduce — Reproduce diagnosed issues

```bash
ascend-agent reproduce run diagnosis.json
ascend-agent reproduce run diagnosis.json --output reproduction.json
```

Executes reproduction commands locally or via SSH (`ASCEND_SSH_HOST`).

### Verify — Run tests to verify fixes

```bash
ascend-agent verify run reproduction.json
ascend-agent verify run reproduction.json --output verification.json
```

Auto-detects pytest, maps changed files to test files, produces pass/fail report.

### Provider selection

All commands support `--provider` and `--permission-mode`:

```bash
# Global provider override
ascend-agent --provider deepseek diagnose run /path/to/repo --trace-text "Error"

# Per-command override
ascend-agent diagnose run --provider qwen /path/to/repo --trace-text "Error"

# Permission control
ascend-agent fix run diagnosis.json --permission-mode accept_edits
```

Supported providers: `openai` (default), `deepseek`, `qwen`, `ollama`.
Permission modes: `default`, `plan`, `accept_edits`, `bypass`.

## Project Structure

```
ascend-agent/
├── pyproject.toml                     # Project metadata, deps, entry point
├── src/
│   └── ascend_agent/
│       ├── __init__.py               # Package init
│       ├── __main__.py               # python -m support
│       ├── main.py                   # Console_scripts entry point
│       ├── config.py                 # pydantic-settings (ASCEND_ env prefix)
│       ├── cli/
│       │   ├── app.py                # Typer app, callbacks, --provider, --resume
│       │   ├── repl.py               # Interactive REPL with streaming output
│       │   ├── diagnose.py           # diagnose run command
│       │   ├── fix.py                # fix run command (review workflow)
│       │   ├── reproduce.py          # reproduce run command (local + SSH)
│       │   ├── verify.py             # verify run command
│       │   ├── io.py                 # JSON I/O helpers
│       │   ├── models.py             # models sub-command
│       │   └── model_catalog.py      # model catalog display
│       ├── context/
│       │   ├── models.py             # Pydantic models (ContextDocument, RepoInfo)
│       │   ├── repo.py               # RepoScanner (.gitignore-aware)
│       │   └── trace.py              # TraceParser (regex, 3 input methods)
│       ├── diagnosis/
│       │   ├── models.py             # Domain models (Evidence, Hypothesis, ...)
│       │   ├── router.py             # Re-exports from providers.router
│       │   ├── engine.py             # LLM-driven search loop
│       │   ├── fix_engine.py         # Fix generation engine
│       │   ├── fix_apply.py          # Batch search-and-replace applier
│       │   └── tool_client.py        # MCP/local tool client abstraction
│       ├── providers/
│       │   ├── catalog.py            # Provider presets (openai, deepseek, qwen, ollama)
│       │   ├── config_manager.py     # JSON config read/write
│       │   ├── router.py             # ModelRouter (chat, chat_stream, completion)
│       │   └── service.py            # resolve_provider, validation helpers
│       ├── reproduction/
│       │   └── engine.py             # Reproduction engine
│       ├── runtime/
│       │   ├── __init__.py           # Public API exports
│       │   ├── core.py               # Runtime facade (create, run_turn, run_turn_sync)
│       │   ├── loop.py               # AgentLoop (async generator with streaming events)
│       │   ├── session.py            # Session (JSONL persistence, fork, load)
│       │   ├── query_engine.py       # Prompt assembly, skill injection, compaction
│       │   ├── tools.py              # ToolRegistry (patterns, permissions, OpenAI schemas)
│       │   ├── permissions.py        # PermissionContext (default/plan/accept_edits/bypass)
│       │   ├── commands.py           # Typed slash-command registry
│       │   └── workflow_runner.py    # Unified entry for domain workflows
│       ├── skills/
│       │   ├── __init__.py
│       │   └── loader.py             # Markdown+YAML frontmatter skill loader
│       ├── tools/
│       │   ├── catalog.py            # ToolSpec definitions (8 tools)
│       │   ├── server.py             # FastMCP server (all 8 tools)
│       │   ├── code_search.py        # Code search (ripgrep + Python fallback)
│       │   ├── file_edit.py          # Search-and-replace with .bak backup
│       │   ├── shell_exec.py         # Shell execution (local + SSH via asyncssh)
│       │   ├── test_runner.py        # Test execution via VerificationEngine
│       │   └── workflows.py          # Domain workflow tool wrappers
│       └── verification/
│           └── engine.py             # Verification engine
└── tests/
    ├── conftest.py                   # Shared fixtures
    ├── test_cli.py                   # CLI integration tests
    ├── test_config_manager.py        # Config manager tests
    ├── test_context.py               # Context builder tests
    ├── test_runtime.py               # Runtime + skills + session + compaction tests
    ├── test_diagnosis/               # Engine + router + fix tests
    ├── test_reproduction/            # Reproduction tests
    ├── test_tools/                   # MCP tool tests
    └── test_verification/            # Verification tests (199 tests total)
```

## Architecture

The runtime unifies all interaction paths through a single layered stack:

```
┌──────────────────────────────────────────────────────────────────┐
│  Interaction Layer                                                │
│  Typer/Rich CLI, streaming REPL, slash commands, skill injection  │
│  diagnose | fix | reproduce | verify  →  WorkflowRunner           │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│  Runtime Layer                                                    │
│  Runtime, Session (JSONL persist), QueryEngine, skill injection   │
│  PermissionContext (default/plan/accept_edits/bypass)             │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│  Agent Loop (async generator)                                     │
│  native tool calling → tool execution → streaming events          │
│  context compaction, max_turns guard                              │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│  Tool Layer                                                       │
│  ToolRegistry, ToolSpec metadata, 8 MCP-registered tools          │
│  code_search | edit_file | exec_shell | run_test | 4 workflows    │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│  Provider Layer                                                   │
│  ModelRouter: completion(), chat(), chat_stream()                 │
│  Native OpenAI tool calling + JSON fallback                       │
│  openai | deepseek | qwen | ollama                                │
└──────────────────────────────────────────────────────────────────┘
```

Key design decisions:
- **Unified runtime** — all commands share WorkflowRunner for provider resolution, permission modes, and session management.
- **Native tool calling** — `ModelRouter.chat()` passes tools to the API; JSON text-parsing fallback for providers without native support.
- **Streaming output** — `AgentLoop` is an async generator yielding `LoopEvent` tuples; REPL renders token-by-token.
- **Permission modes** — `default`, `plan` (read-only), `accept_edits`, `bypass`; available on all commands via `--permission-mode`.
- **Session persistence** — JSONL transcripts in `~/.config/ascend-agent/sessions/`; `Session.save()`, `Session.load()`, `Session.fork()`.
- **Skill system** — Markdown files with YAML frontmatter in `~/.config/ascend-agent/skills/`; injected into system prompt.
- **Context compaction** — `_compact_context()` trims old tool results when estimated token count exceeds threshold.
- **Command registry** — typed `CommandRegistry` replaces ad-hoc if/elif dispatch in the REPL.
- **Three trace input methods** — file (`--trace`), stdin pipe, inline paste (`--trace-text`).
- **OpenAI-compatible** — any provider with an OpenAI-compatible API works via `ASCEND_*_API_KEY` env vars.

## Development

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run a specific test file
python3 -m pytest tests/test_runtime.py -v

# Start the MCP server standalone
python3 -m ascend_agent.tools.server

# Create a user skill
mkdir -p ~/.config/ascend-agent/skills
cat > ~/.config/ascend-agent/skills/my-skill.md << 'EOF'
---
name: my-skill
description: A custom diagnostic skill
when_to_use: When debugging NPU memory issues
---
# My Skill

When the user mentions NPU memory, suggest checking:
1. Memory allocation logs
2. Device memory fragmentation
3. Batch size configuration
EOF
```

### Dependencies

| Library | Purpose |
|---------|---------|
| `typer` | CLI framework |
| `rich` | Terminal formatting (tables, colors, streaming) |
| `pydantic` | Data validation, context model schemas |
| `pydantic-settings` | Environment/config management |
| `mcp` | Model Context Protocol server (FastMCP) |
| `openai` | LLM API client |
| `asyncssh` | Remote shell execution |
| `pyyaml` | Skill file frontmatter parsing |

### Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | Architecture Foundation | ✅ Complete |
| 2 | Diagnosis Engine | ✅ Complete |
| 3 | Fix Generation | ✅ Complete |
| 4 | Reproduction Capability | ✅ Complete |
| 5 | Verification | ✅ Complete |
| 6 | Provider Routing Foundation | ✅ Complete |
| 7 | Chinese Model Integration | ✅ Complete |
| 8 | Runtime Unification | ✅ Complete |
| 9 | Session Persistence & Streaming | ✅ Complete |
| 10 | Multi-Repo Support | ⏳ Planned |
| 11 | Provider & Multi-Repo Testing | ⏳ Planned |

## Architecture Constraints

- `print()` must never be used in MCP tools — stdout is the STDIO transport channel
- Stack trace parsing is regex-based (no AST), one trace at a time
- SSH/remote support via `ASCEND_SSH_HOST` env var (asyncssh)
- All fix suggestions require human review before application
- Provider routing via `ASCEND_*_API_KEY` env vars and `--provider` flag
- Structured output fallback: `.parse()` → `json.loads` on 400 errors
- Sessions auto-save to `~/.config/ascend-agent/sessions/<thread_id>.jsonl`

## License

[License type] — see LICENSE file.
