# Phase 3: Fix Generation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 3-Fix Generation
**Areas discussed:** Implementation vs. Decisions, Downstream contracts, Discretion → Decisions, Deferred ideas status

---

## Implementation vs. Decisions

| Option | Description | Selected |
|--------|-------------|----------|
| Update to match code | Primary representation is search-and-replace (old_text→new_text), diff computed for display | ✓ |
| Keep as-is | Keep 'unified diff' framing | |

**User's choice:** Update to match code

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, formalize them | Document validation rules as explicit decisions for downstream | ✓ |
| No, leave implicit | Keep in Agent's Discretion | |

**User's choice:** Yes, formalize them

---

| Option | Description | Selected |
|--------|-------------|----------|
| Update to match code | Rich Syntax diff lexer with line numbers in Panel | ✓ |
| Keep original intent | Interleaved approach is the intent | |

**User's choice:** Update to match code

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, document | Add D-20 for batch grouping by file, collapsed replacements, single edit_file call per file | ✓ |
| No, skip | Implementation detail | |

**User's choice:** Yes, document

---

## Downstream Contracts

| Option | Description | Selected |
|--------|-------------|----------|
| Schema contract | Document accepted FixSuggestion schema as stable contract | ✓ |
| Output format spec | Document the output file JSON shape | |
| Both | Both schema + output format | |
| No downstream contract | Downstream phases operate independently | |

**User's choice:** Schema contract

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, add to canonical_refs | Point downstream agents to Phase 3 files | |
| No, output-only contract | Output JSON is sufficient | ✓ |

**User's choice:** No, output-only contract

---

| Option | Description | Selected |
|--------|-------------|----------|
| Stable / frozen | Formalize FixSuggestion as frozen for Phase 4/5 dependency | ✓ |
| Stable with caveat | Document shape but note it could evolve | |
| Implicit | Leave for agents to read models.py | |

**User's choice:** Stable / frozen

---

| Option | Description | Selected |
|--------|-------------|----------|
| Implementation detail | .bak backups have no downstream impact | ✓ |
| Document for downstream | .bak files may need awareness | |

**User's choice:** Implementation detail

---

## Discretion → Decisions

| Option | Description | Selected |
|--------|-------------|----------|
| All of them | Lock down all five discretion items | |
| Models + Engine pattern | Lock models and engine pattern, keep prompt engineering and tests as discretion | ✓ |
| None, leave as-is | Keep everything in Agent's Discretion | |

**User's choice:** Models + Engine pattern

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, formalize pattern | FixEngine follows Phase 2 Engine pattern | ✓ |
| No, leave implicit | Implicit | |

**User's choice:** Yes, formalize pattern

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, formalize | DiagnosisOutput wraps ContextDocument + DiagnosisResult | ✓ |
| No | Leave implicit | |

**User's choice:** Yes, formalize

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, document | Two-layer model design (FixResponse vs FixSuggestion) | ✓ |
| No | Implicit | |

**User's choice:** Yes, document

---

## Deferred Ideas Status

| Option | Description | Selected |
|--------|-------------|----------|
| Keep all as-is | All four deferred ideas still deferred | ✓ |
| Let me specify changes | Some need promotion or removal | |
| Remove all | Delete the deferred section | |

**User's choice:** Keep all as-is

---

## Deferred Ideas (from discussion)

During discussion, the user raised four new capability ideas that were outside Phase 3 scope:
1. **Multiple code repos** — Accept multiple repos as input. Crosses phase boundaries (context building, diagnosis, fix).
2. **Multiple logs / earliest error tracing** — Accept multiple log files, find earliest error, trace from there. Diagnosis enhancement (Phase 2 domain).
3. **Multi-modal file support** — Handle images/screenshots, .log, .txt files. Input processing expansion.
4. **Model selection CLI tool** — Support more models including local deployments, guide user through selection. Cross-cutting infrastructure.

These were noted as deferred — they belong in their own phases.
