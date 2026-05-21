---
phase: 2
slug: 02-diagnosis-engine
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-21
---

# Phase 2 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| ModelRouter → OpenAI API | API key crosses process boundary via TLS | `OPENAI_API_KEY` env var → TLS transport |
| diagnosis/models.py → consumers | Pydantic models enforce schema on external data | Structured LLM output, user-supplied trace text |
| Engine.diagnose() → code_search tool | User trace data influences search patterns — potential prompt injection | Search patterns derived from LLM output |
| CLI stdout | Diagnosis results containing file paths and code snippets | `file:line` references, code context |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-2-01 | Information Disclosure | ModelRouter.__init__ | mitigate | API key read from `OPENAI_API_KEY` env var only — never logged. Logger outputs `"ModelRouter initialized (model: {model})"` only. No key serialization in any output. | closed |
| T-2-SC | Tampering | openai pip install | mitigate | openai package verified [OK] via slopcheck audit in RESEARCH.md. Standard PyPI package with 4yr history. | closed |
| T-2-02 | Spoofing | Engine.search loop | mitigate | `SearchDecision.action` constrained to `r'^(search\|hypothesize)$'` via Pydantic regex pattern. System prompt asserts "You are a Python debugging expert." LLM output bound by `response_format` Pydantic schema. | closed |
| T-2-03 | Denial of Service | _execute_search | mitigate | `code_search` tool has built-in 30s timeout. Engine catches all exceptions from `search_code` and converts to `PartialFailure` — never crashes. Hypothesis generation failure also returns graceful `DiagnosisResult` with error. | closed |
| T-2-04 | Information Disclosure | _read_function_body | mitigate | Only reads files within `repo_path` (validated via `Path.resolve()`). Returns `None` for non-existent files. Path construction uses `repo_path_resolved / candidate_path`. | closed |
| T-2-05 | Information Disclosure | _display_diagnosis | mitigate | Displays `file:line` from `Evidence.file_path` (relative paths). Raw trace frames shown at CLI level (user-facing diagnostic output, not logging). No raw trace data logged at INFO level — only at DEBUG. | closed |
| T-2-06 | Spoofing | CLI diagnose.run | mitigate | Missing `OPENAI_API_KEY` raises `ValueError` with clear actionable message containing "OPENAI_API_KEY" and hint about setting it. Caught in `_one_shot_mode` → `typer.Exit(code=1)` — no crash or stack trace. | closed |

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-21 | 7 | 7 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Verification evidence (all mitigations confirmed in code):**

| Threat ID | Code Evidence |
|-----------|---------------|
| T-2-01 | `router.py:20` — `api_key = api_key or os.environ.get("OPENAI_API_KEY")` ; `router.py:30` — `logger.info("ModelRouter initialized (model: %s)", self._model)` |
| T-2-SC | `RESEARCH.md` — slopcheck [OK] verdict for openai package |
| T-2-02 | `models.py:40` — `pattern=r"^(search\|hypothesize)$"` ; `engine.py:92-106` — system prompt with authority assertion |
| T-2-03 | `code_search.py:11` — `timeout=30` ; `engine.py:303-307` — exception catch ; `engine.py:268-280` — fallback DiagnosisResult |
| T-2-04 | `engine.py:171` — `Path(repo_path).resolve()` ; `engine.py:47-52` — `FileNotFoundError` → `None` |
| T-2-05 | `diagnose.py:189` — `console.print(f"[blue]File: {ev.file_path}:{ev.line_number}[/blue]")` ; no INFO-level trace logging |
| T-2-06 | `router.py:21-25` — `ValueError("OPENAI_API_KEY is required...")` ; `diagnose.py:80-83` — catch + hint + `typer.Exit` |

**Approval:** verified 2026-05-21
