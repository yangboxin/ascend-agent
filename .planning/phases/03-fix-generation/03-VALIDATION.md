---
phase: 3
slug: fix-generation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-21
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest -x tests/ -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest -x tests/ -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 8 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | FIX-01, FIX-02 | — | N/A | unit | `pytest tests/test_diagnosis/test_fix_engine.py -q` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | FIX-01 | — | N/A | unit | `pytest tests/test_diagnosis/test_models.py -q` | ✅ | ⬜ pending |
| 03-02-01 | 02 | 2 | FIX-02 | — | N/A | integration | `pytest tests/test_cli.py -k fix -q` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | FIX-02 | — | N/A | integration | `pytest tests/test_tools/ -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_diagnosis/test_fix_engine.py` — FixEngine unit tests (stubs)
- [ ] `tests/test_diagnosis/conftest.py` — update with fix engine fixtures
- [ ] `tests/test_cli.py` — fix CLI integration tests (extend existing)
- [ ] `tests/test_tools/test_file_edit.py` — edit_file unit tests (new)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Interactive human review workflow (Accept/Skip/Reject prompts) | FIX-02 | Terminal interaction cannot be automated | Run `ascend-agent fix run <diagnosis.json>` and verify each prompt shows diff + explanation, valid accept/skip/reject input handling |
| Search-and-replace edit_file creates .bak backup | FIX-01 | Side-effect verification (file system) | Create test file, run edit_file, verify .bak exists with original content |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 8s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
