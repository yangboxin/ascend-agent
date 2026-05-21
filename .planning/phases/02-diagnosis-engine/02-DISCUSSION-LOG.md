# Phase 2: Diagnosis Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 2-Diagnosis Engine
**Areas discussed:** Diagnosis workflow, Hypothesis structure & format, Code exploration strategy

---

## Diagnosis Workflow

| Option | Description | Selected |
|--------|-------------|----------|
| Simple pipeline | Sequential: parse → search → hypothesis | |
| LLM-driven loop | LLM decides actions iteratively | |
| LangGraph state machine | Formal multi-step with branching | |
| LLM drives search strategy | LLM decides searches, iterates up to 3 times | ✓ |
| Single-pass | One analysis pass | ✓ |
| Multi-pass refinement | Initial hypothesis then refine | |
| Silent - note ambiguities | Work with what's given, flag uncertainties | ✓ |
| Ask in REPL mode only | Interactive in REPL, silent in one-shot | |
| Always ask when ambiguous | Prompt user whenever unclear | |
| Report partial results + failure reason | Show successes and failures | ✓ |
| Clear failure message with suggestions | Simple but loses partial work | |
| Fail silently | Clean API but no feedback | |
| 3 searches max | Fixed iteration budget | ✓ |
| LLM decides when done | Flexible but unbounded | |
| 1 search | Fast but narrow | |

**User's choice:** LLM-driven search strategy with up to 3 search iterations, silent with ambiguity notes in output, report partial results on failure
**Notes:** User initially selected Simple pipeline, then revised to LLM-driven search strategy when asked about LLM integration. User wants LLM in the diagnosis engine, not pushed to a separate Model Router layer.

---

## Hypothesis Structure & Format

| Option | Description | Selected |
|--------|-------------|----------|
| Root cause + evidence + confidence | Clean fields | ✓ |
| + fix suggestion | Includes preliminary fix | |
| + error category | Adds taxonomy | |
| Top 1 | Highest confidence only | |
| Top 3 ranked by confidence | Ranked alternatives | ✓ |
| All above threshold | Maximum coverage | |
| File:line + code snippets | Context-rich evidence | ✓ |
| File:line only | Clean but user looks up code | |
| Code snippets + explanation | Most thorough | |
| No explicit categorization | No taxonomy | ✓ |
| Ascend-specific types | Dimension, OOM, dtype, etc. | |
| LLM-assigned dynamic categories | Flexible but inconsistent | |

**User's choice:** Root cause + evidence + confidence fields, top 3 ranked, file:line with code snippets. No error categorization now.
**Notes:** User likes the idea of error categorization with VectorDB/RAG eventually but wants to ship the core diagnosis first.

---

## Code Exploration Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Line + surrounding function | Focused context | ✓ |
| Entire file | Full file read | |
| Function def + called line | Separate reads | |
| Every trace frame | Search all frames | |
| Only error frames (skip stdlib) | Skip deps | |
| LLM decides search targets | LLM picks frames | ✓ |
| Function body ± 5 lines context | Focused function scope | ✓ |
| Fixed window around error | 20 above, 10 below | |
| Full file | Complete file read | |
| Trace frames only | No cross-refs | ✓ |
| Follow imports and defs | Cross-file defs | |
| Follow callers and callees | Full chain | |

**User's choice:** Line + function body per frame, LLM decides search targets within the 3-iteration budget, function body ± context window, no cross-references.
**Notes:** User chose "LLM decides search targets" — consistent with the LLM-driven search strategy from the workflow area.

---

## The Agent's Discretion

- Model selection for the LLM diagnosis calls (Model Router wrapper)
- Exact prompt engineering for search-decision loop and hypothesis generation
- Pydantic schema for the diagnosis result data model

## Deferred Ideas

- Error categorization with VectorDB/RAG for Ascend NPU error patterns
- Cross-reference following for deeper code exploration
- Fix suggestions inline in diagnosis (belongs in Phase 3)
