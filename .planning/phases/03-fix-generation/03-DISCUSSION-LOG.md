# Phase 3: Fix Generation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 3-Fix Generation
**Areas discussed:** Fix representation format, Fix engine design, Human review workflow, edit_file tool design, Diagnosis integration

---

## Fix Representation Format

| Option | Description | Selected |
|--------|-------------|----------|
| Unified diff patch (Recommended) | Standard git diff format. LLMs handle this well, familiar to developers. | ✓ |
| Structured find+replace | Pydantic model with file_path + old_text + new_text. More reliable for exact matches but verbose. | |
| Full file rewrite | LLM outputs entire new file content. Simple but wasteful. | |

**User's choice:** Unified diff patch (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| One fix = one patch over one file (Recommended) | Each hypothesis maps to edits in a single file. Cleaner review. | ✓ |
| One patch can span multiple files | A single fix can produce a multi-file diff. More realistic but harder to review. | |

**User's choice:** One fix = one patch over one file (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Show patch with surrounding context (Recommended) | Rich split-view or interleaved diff showing 5-10 lines of surrounding code. | ✓ |
| Show patch only (minimal) | Just the unified diff. Less noise. | |

**User's choice:** Show patch with surrounding context (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Single FixSuggestion model per patch (Recommended) | file_path + diff_patch + explanation + hypothesis_id. | ✓ |
| Flat list with hypothesis context repeated | Each fix includes the full hypothesis it addresses. Redundant. | |

**User's choice:** Single FixSuggestion model per patch (Recommended)

---

## Fix Engine Design

| Option | Description | Selected |
|--------|-------------|----------|
| Generate fixes for all hypotheses (Recommended) | Engine processes all 3 hypotheses, generates a fix for each. | ✓ |
| Top hypothesis only | Only generate a fix for the highest-confidence hypothesis. | |

**User's choice:** Generate fixes for all hypotheses (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-turn — re-read code before fixing (Recommended) | LLM decides what code to read, then generates a fix. | ✓ |
| One-shot — fix from evidence | LLM generates fix from evidence snippets already in the hypothesis. | |

**User's choice:** Multi-turn — re-read code before fixing (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Same ModelRouter with dedicated system prompt (Recommended) | Reuses Phase 2 ModelRouter. Configurable via ASCEND_FIX_MODEL. | ✓ |
| Dedicated FixModelRouter subclass | Separate router class. More flexible but more code. | |

**User's choice:** Same ModelRouter with dedicated system prompt (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Single-shot per hypothesis (Recommended) | LLM reads code, generates one fix per hypothesis. | ✓ |
| Iterative with validation | LLM generates, validates (syntax check), retries if invalid. | |

**User's choice:** Single-shot per hypothesis (Recommended)

---

## Human Review Workflow

| Option | Description | Selected |
|--------|-------------|----------|
| Sequential — show one fix at a time (Recommended) | Show fix #1 with diff + explanation, prompt accept/skip/reject. | ✓ |
| Batch — show all fixes at once | Display all fixes at once. Better overview but more cognitive load. | |

**User's choice:** Sequential — show one fix at a time (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Accept / Skip / Reject (Recommended) | Accept applies the fix. Skip leaves it. Reject discards it. | ✓ |
| Accept / Reject / Modify | Adds option to modify suggestion before applying. Complex UI. | |
| Just Accept / Reject | Simplest — no in-between. | |

**User's choice:** Accept / Skip / Reject (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Rich Syntax highlighted diff panel (Recommended) | Reuse Rich Panel + Syntax from Phase 2. | ✓ |
| Side-by-side split view | Original code on left, fixed code on right. Harder in terminal. | |

**User's choice:** Rich Syntax highlighted diff panel (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Queue all accepted, apply in batch at end (Recommended) | Collect accepted, apply all at once after review. | ✓ |
| Apply immediately on accept | Apply as soon as user accepts. Harder to undo. | |

**User's choice:** Queue all accepted, apply in batch at end (Recommended)

---

## edit_file Tool Design

| Option | Description | Selected |
|--------|-------------|----------|
| Search-and-replace (Recommended) | Takes old_text + new_text. Precise and verifiable. | ✓ |
| Line-range replacement | Takes start_line, end_line, new_content. Brittle. | |
| Raw patch application | Applies unified diff. Harder for LLMs to generate perfectly. | |

**User's choice:** Search-and-replace (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Create .bak backup before edit (Recommended) | Copy original to file.py.bak before each edit. | ✓ |
| No backup — user has git | Rely on git. Simpler but user might not have staged changes. | |
| Git-auto-stage before edit | git add then edit. Requires git repo. | |

**User's choice:** Create .bak backup before edit (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Apply directly (Recommended) | edit_file applies the change and returns success/failure. | ✓ |
| Preview first, confirm via tool | Dry-run mode returns diff without applying. | |

**User's choice:** Apply directly (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Multiple replacements in one call (Recommended) | List of {old_text, new_text} operations. All validated before apply. | ✓ |
| One replacement per call | Each call does exactly one replacement. Simple but verbose. | |

**User's choice:** Multiple replacements in one call (Recommended)

---

## Diagnosis Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Both — file path or stdin | Support both patterns. Detect whether argument is file path or read stdin. | ✓ |
| JSON file from --output (Recommended) | Explicit file path. Works with scripting. | |
| Pipe via stdin | Chainable but harder to debug. | |

**User's choice:** Both — file path or stdin

---

| Option | Description | Selected |
|--------|-------------|----------|
| Extract from diagnosis JSON (Recommended) | Diagnosis output includes repo path via wrapper. | ✓ |
| Require explicit --repo flag | User provides repo path separately. Redundant. | |

**User's choice:** Extract from diagnosis JSON (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Wrap diagnosis output to include ContextDocument (Recommended) | Save wrapper with ContextDocument (has repo info) + DiagnosisResult. | ✓ |
| Add repo_path field to DiagnosisResult | Modify Phase 2's output model. Cleaner but changes Phase 2. | |
| Require --repo flag on fix run | User passes repo explicitly. Avoids design changes. | |

**User's choice:** Wrap diagnosis output to include ContextDocument (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| `ascend-agent fix run [diagnosis.json]` — file or stdin (Recommended) | If arg is file path read from file, else read from stdin. | ✓ |
| Separate `--diagnosis` flag | `ascend-agent fix run --diagnosis diagnosis.json`. | |

**User's choice:** `ascend-agent fix run [diagnosis.json]` — file or stdin (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Save accepted-fixes summary (Recommended) | --output fixes.json saves accepted FixSuggestions with diffs. | ✓ |
| Auto-apply on accept, no output file | Applied fixes immediately. Simpler but less traceable. | |
| Always save changes log | Always write .fixes-applied.log. Audit trail. | |

**User's choice:** Save accepted-fixes summary (Recommended)

---

## Deferred Ideas

- **Iterative fix validation with retry** — Syntax checking and retry for malformed patches. Future maintenance phase.
- **Modify-fix during review** — Allow user to edit suggestion inline before accepting. Deferred UX improvement.
- **Side-by-side diff view** — Original + fixed code side by side. Needs Rich layout experimentation.
- **Git-auto-stage before edits** — Auto-staging before apply. .bak backup sufficient initially.
