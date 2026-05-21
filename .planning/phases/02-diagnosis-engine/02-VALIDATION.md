---
phase: 2
slug: diagnosis-engine
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-21
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7+ with pytest-asyncio |
| **Config file** | `pyproject.toml` under `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_diagnosis/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_diagnosis/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | DIAG-01 | T-2-01 / — | N/A — Pydantic model validation | unit | `pytest tests/test_diagnosis/test_models.py -x` | ❌ W1 | ⬜ pending |
| 02-01-02 | 01 | 1 | DIAG-01 | T-2-02 / — | API key validated on init, never logged | unit | `pytest tests/test_diagnosis/test_router.py -x` | ❌ W1 | ⬜ pending |
| 02-02-01 | 02 | 2 | DIAG-01, DIAG-02 | T-2-03 / — | Code search pattern validation, path traversal | integration | `pytest tests/test_diagnosis/test_engine.py::test_search_loop -x` | ❌ W2 | ⬜ pending |
| 02-02-02 | 02 | 2 | DIAG-01 | T-2-04 / — | N/A — failure reporting | unit | `pytest tests/test_diagnosis/test_engine.py::test_partial_failure -x` | ❌ W2 | ⬜ pending |
| 02-02-03 | 02 | 2 | DIAG-02 | T-2-05 / — | Read scope limited to function body ±5 lines | unit | `pytest tests/test_diagnosis/test_engine.py::test_function_body_extraction -x` | ❌ W2 | ⬜ pending |
| 02-03-01 | 03 | 3 | DIAG-01, DIAG-02 | — | N/A — CLI wiring | integration | `pytest tests/test_cli.py::test_cli_diagnose_integration -x` | ❌ W3 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_diagnosis/__init__.py` — package for test discovery
- [ ] `tests/test_diagnosis/conftest.py` — shared fixtures (mock LLM responses, sample traces, sample repos)
- [ ] `tests/test_diagnosis/test_models.py` — Pydantic schema validation for DiagnosisResult/Hypothesis/Evidence
- [ ] `tests/test_diagnosis/test_router.py` — ModelRouter abstraction and openai provider
- [ ] `tests/test_diagnosis/test_engine.py` — search loop, partial failure, function body extraction

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full diagnosis output display in CLI | DIAG-01, DIAG-02 | Rich terminal rendering can't be automated | After Plan 02-03 execution, run `ascend-agent diagnose run ~/vllm-ascend --trace sample.log` and verify Rich formatted output shows ranked hypotheses with code snippets |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-05-21
