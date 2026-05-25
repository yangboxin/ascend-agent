---
phase: 4
slug: reproduction-capability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 7.0.0 + pytest-asyncio >= 0.21.0 |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| **Quick run command** | `python -m pytest tests/test_tools/test_shell_exec.py -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_reproduction/ tests/test_tools/test_shell_exec.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | REPRO-01 | T-04-01 | exec_shell returns valid JSON with status/stdout/stderr/exit_code for local execution | unit | `pytest tests/test_tools/test_shell_exec.py::test_exec_local_returns_json -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | REPRO-01 | T-04-03 | exec_shell routes to asyncssh when ASCEND_SSH_HOST is set | unit | `pytest tests/test_tools/test_shell_exec.py::test_exec_ssh_routing -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | REPRO-01 | T-04-04 | exec_shell handles command timeout with status=error | unit | `pytest tests/test_tools/test_shell_exec.py::test_exec_local_timeout -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | REPRO-01 | T-04-05 | ReproductionEngine.reproduce() returns ReproductionResult for valid diagnosis | unit | `pytest tests/test_reproduction/test_engine.py::test_reproduce_returns_result -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | REPRO-01 | T-04-06 | ReproductionEngine detects active venv via VIRTUAL_ENV | unit | `pytest tests/test_reproduction/test_engine.py::test_detect_venv -x` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 2 | D-10 | T-04-02 | Path traversal blocked for files outside repo | unit | `pytest tests/test_reproduction/test_engine.py::test_path_traversal_blocked -x` | ❌ W0 | ⬜ pending |
| 04-02-04 | 02 | 2 | D-14 | T-04-06 | Engine respects VIRTUAL_ENV and CONDA_PREFIX env vars | unit | `pytest tests/test_reproduction/test_engine.py::test_venv_respected -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 3 | REPRO-01 | — | CLI `reproduce run` loads diagnosis JSON and prints result | integration | `pytest tests/test_cli.py::test_reproduce_run_command -x` | ❌ W0 | ⬜ pending |
| 04-03-02 | 03 | 3 | D-11 | — | ReproductionResult model validates status field enum | unit | `pytest tests/test_reproduction/test_models.py::test_reproduction_result_validation -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_tools/test_shell_exec.py` — stubs for REPRO-01 (exec_shell local + SSH routing + timeout + error handling)
- [ ] `tests/test_reproduction/__init__.py` — package marker
- [ ] `tests/test_reproduction/conftest.py` — shared fixtures: mock router, sample DiagnosisResult, env var manipulation
- [ ] `tests/test_reproduction/test_engine.py` — stubs for REPRO-01 (ReproductionEngine.reproduce(), venv detection, path traversal, command construction)
- [ ] `tests/test_reproduction/test_models.py` — stubs for D-11 (ReproductionResult field validation, status enum)
- [ ] `pip install "asyncssh>=2.23.0"` — new dependency not yet in pyproject.toml

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SSH connection to real remote host | REPRO-01 | Requires actual SSH server and valid credentials | Set ASCEND_SSH_HOST/USER/KEY_PATH, run `ascend reproduce run <diagnosis.json>`, verify remote command output |
| Known host key verification toggle | D-09 | Depends on user's SSH infrastructure | Test with known_hosts=None (accept all) and with known_hosts=<valid file> — verify connection succeeds or fails as expected |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
