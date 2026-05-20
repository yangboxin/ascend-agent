---
phase: 1
slug: architecture-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-20
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]` section) |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q --no-header`
- **After every plan wave:** Run `python -m pytest tests/ -v -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | ARCH-01 | T-01-01 | Path traversal prevention | unit | `pytest tests/test_context.py::test_repo_scanner_discovers_files -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | ARCH-01 | T-01-01 | .gitignore awareness | unit | `pytest tests/test_context.py::test_repo_scanner_respects_gitignore -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | ARCH-01 | — | RepoInfo schema output | unit | `pytest tests/test_context.py::test_repo_info_schema -x` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | ARCH-02 | — | TraceParser error type extraction | unit | `pytest tests/test_context.py::test_trace_parse_error_type -x` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 1 | ARCH-02 | — | TraceParser frame extraction | unit | `pytest tests/test_context.py::test_trace_parse_frames -x` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 1 | ARCH-02 | — | Stdin pipe input handling | unit | `pytest tests/test_context.py::test_trace_from_stdin -x` | ❌ W0 | ⬜ pending |
| 01-02-04 | 02 | 1 | ARCH-02 | — | Inline paste text handling | unit | `pytest tests/test_context.py::test_trace_text_arg -x` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 2 | ARCH-01 | T-01-01 | CLI help with no args | integration | `pytest tests/test_cli.py::test_cli_no_args_shows_help -x` | ❌ W0 | ⬜ pending |
| 01-03-02 | 03 | 2 | ARCH-01 | — | CLI diagnose subcommand exists | integration | `pytest tests/test_cli.py::test_cli_diagnose_subcommand -x` | ❌ W0 | ⬜ pending |
| 01-04-01 | 04 | 2 | — | — | MCP server starts and lists 4 tools | integration | `pytest tests/test_tools/test_server.py::test_mcp_server_lists_tools -x` | ❌ W0 | ⬜ pending |
| 01-04-02 | 04 | 2 | — | — | Code search regex tool works | integration | `pytest tests/test_tools/test_code_search.py::test_search_regex_pattern -x` | ❌ W0 | ⬜ pending |
| 01-04-03 | 04 | 2 | — | — | Tool results use MCP format | integration | `pytest tests/test_tools/test_server.py::test_tool_result_format -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared fixtures (temp directory, sample traces, repo fixtures)
- [ ] `tests/test_context.py` — covers all ARCH-01, ARCH-02 unit tests
- [ ] `tests/test_cli.py` — covers D-01, D-05 CLI behavior tests
- [ ] `tests/test_tools/__init__.py` — package init for tools tests
- [ ] `tests/test_tools/test_server.py` — MCP server startup + tool listing tests
- [ ] `tests/test_tools/test_code_search.py` — code search tool integration tests
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` section — test config
- [ ] pytest install: `pip install pytest`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Rich terminal output formatting | D-03 | Visual rendering can't be automated with unit tests | Run `agent diagnose --help` and verify colors, tables, syntax highlighting render correctly |
| No-args help text display | D-05 | Visual/UX validation | Run `agent` with no arguments and verify help text is displayed |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending 2026-05-20
