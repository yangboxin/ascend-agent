---
phase: 5
slug: verification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 with pytest-asyncio (auto mode) |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/test_verification/ -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_verification/ -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | VERIF-01 | T-05-01 | Pydantic validation rejects unknown fields | unit | `pytest tests/test_verification/test_models.py::test_verification_result_valid -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | VERIF-01 | — | N/A | unit | `pytest tests/test_verification/test_engine.py::test_map_test_files -x` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | VERIF-01 | T-05-02 | Path traversal protection: Path.resolve()+startswith() | unit | `pytest tests/test_verification/test_engine.py::test_detect_framework -x` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 1 | VERIF-02 | T-05-03 | test_timeout kills long-running processes | unit | `pytest tests/test_verification/test_engine.py::test_parse_json_report -x` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 2 | VERIF-01 | T-05-02 | exec_shell runs test command via subprocess | integration | `pytest tests/test_verification/test_engine.py::test_execute_tests -x` | ❌ W0 | ⬜ pending |
| 05-04-01 | 04 | 3 | VERIF-02 | T-05-03 | Rich display captures stdout/stderr | integration | `pytest tests/test_verification/test_cli.py::test_verify_display -x` | ❌ W0 | ⬜ pending |
| 05-04-02 | 04 | 3 | VERIF-02 | T-05-03 | --output writes valid JSON | integration | `pytest tests/test_verification/test_cli.py::test_verify_output -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_verification/__init__.py` — package marker
- [ ] `tests/test_verification/conftest.py` — shared fixtures (sample ReproductionResult, temporary repo with pytest config)
- [ ] `tests/test_verification/test_engine.py` — covers VERIF-01, VERIF-02 verification engine behaviors
- [ ] `tests/test_verification/test_models.py` — covers VerificationResult model validation
- [ ] `tests/test_verification/test_cli.py` — covers verify CLI display
- [ ] `pip install pytest-json-report` — required dependency for all test infra

---

## Threat Verification Map

| Threat ID | Threat Description | Verification Test |
|-----------|--------------------|-------------------|
| T-05-01 | Malicious JSON input via crafted ReproductionResult | `test_models.py`: Pydantic rejects extra/invalid fields; validates types |
| T-05-02 | Command injection via test file path traversal | `test_engine.py`: Path.resolve() boundaries reject escape attempts |
| T-05-03 | Information disclosure / DoS via test output | `test_engine.py`: test_timeout enforced; output captured in VerificationResult |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Human reviews verification report | VERIF-02 | Subjective assessment of report clarity | Run `ascend verify reproduction.json` with real reproduction output and verify the Rich display is clear and actionable |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
