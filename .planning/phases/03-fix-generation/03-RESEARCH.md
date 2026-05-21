# Phase 3: Fix Generation — Research

**Researched:** 2026-05-21
**Domain:** LLM-driven code fix generation — code re-reading, unified diff generation, human review workflow, search-and-replace file editing
**Confidence:** HIGH

## Summary

Phase 3 implements the fix generation capability: take a `DiagnosisResult` (from Phase 2) with ranked hypotheses and evidence, re-read relevant code (following the Engine pattern from Phase 2), generate concrete fix suggestions as unified diff patches with search-and-replace operations, and present them for human review through a sequential accept/skip/reject workflow in the CLI. Accepted fixes are queued and applied in batch via the `edit_file` MCP tool.

**Key architecture insight:** The LLM is NOT asked to generate unified diff patches directly (line numbers in `@@` hunks are notoriously error-prone for LLMs). Instead, the LLM outputs structured search-and-replace operations (`old_text` → `new_text` blocks), and the FixEngine computes the canonical unified diff using Python's `difflib.unified_diff()` for human display. This is the same proven approach used by tools like Aider and GPT-Engineer.

**Primary recommendation:** Implement FixEngine as a direct follow of the Engine class pattern. Reuse ModelRouter with a dedicated system prompt. The LLM output model includes `replacements: list[Replacement]` where each Replacement has `old_text` and `new_text`. The engine reads the file, verifies old_text exists (single match), computes the unified diff, and creates FixSuggestion objects. The review workflow uses Rich interactive prompts (Confirm/Prompt with choices). The `edit_file` tool validates and applies replacements with `.bak` backup.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Fixes are represented as unified diff patches (git diff format). LLMs handle this well, familiar to developers, previewable with Rich Syntax highlighting.
- **D-02:** One fix = one patch over one file. If a fix touches multiple files, produce multiple patches referencing the same hypothesis.
- **D-03:** Patch display includes surrounding code context (5-10 lines around changes) as interleaved diff, not just the raw patch.
- **D-04:** Pydantic model: `FixSuggestion` per patch (file_path, diff_patch, explanation, hypothesis_id). `FixGenerationResult` wraps a list of `FixSuggestion` with metadata.
- **D-05:** Generate fixes for all hypotheses in the diagnosis, not just the top one.
- **D-06:** Multi-turn LLM strategy — the fix engine re-reads relevant code before generating a fix, similar to the diagnosis engine pattern. Not one-shot from evidence alone.
- **D-07:** Reuse the same `ModelRouter` abstraction from Phase 2, with a dedicated system prompt for fix generation. Configurable via `ASCEND_FIX_MODEL` env var (default: `gpt-4o`).
- **D-08:** Single-shot per hypothesis. LLM reads code, generates one fix. If malformed, note the error and move on. No iterative validation/retry initially.
- **D-09:** Sequential review — show one fix at a time. Focused review per fix, not batch view.
- **D-10:** Actions per fix: Accept / Skip / Reject. Accept queues the fix for later application, Skip leaves it, Reject discards it.
- **D-11:** Diff display uses Rich Panel + Syntax highlighting (green/red for added/removed lines), reusing the approach from Phase 2 diagnosis display.
- **D-12:** Accepted fixes are queued and applied in batch after all fixes are reviewed. User sees a summary of what was applied.
- **D-13:** Operation model: search-and-replace. Accepts `old_text` + `new_text`. Finds exact match of `old_text` in the file and replaces it. Precise and verifiable.
- **D-14:** Create `.bak` backup before each edit.
- **D-15:** Apply directly — no preview/dry-run mode in the tool itself. Preview is handled by the fix generation review workflow.
- **D-16:** Accepts multiple replacements in one call (list of `{old_text, new_text}` operations). All validated before any are applied.
- **D-17:** `ascend-agent fix run [diagnosis.json]` — if argument is a file path, read from file; if no argument, read from stdin.
- **D-18:** Repo path extracted from the diagnosis JSON via a wrapper that includes both `ContextDocument` and `DiagnosisResult`. The `--output` flag on `diagnose run` saves this wrapper.
- **D-19:** `--output fixes.json` saves the list of accepted `FixSuggestion` entries with their diffs for audit/scripting.

### The Agent's Discretion

- Exact prompt engineering for the fix generation LLM calls.
- The FixEngine class design (constructor, public API, internal helpers) — follow the Engine pattern from Phase 2.
- The DiagnosisOutput wrapper model shape (ContextDocument + DiagnosisResult).
- The FixSuggestion and FixGenerationResult Pydantic models, including exact diff_patch format within the unified diff standard.
- Test approach and coverage targets.

### Deferred Ideas (OUT OF SCOPE)

- **Iterative fix validation with retry** — Could add syntax checking and retry logic for malformed patches in a future maintenance phase after the single-shot approach is proven.
- **Modify-fix during review** — Allowing the user to edit a fix suggestion inline before accepting. Complex UI in terminal. Deferred to a future UX improvement phase.
- **Side-by-side diff view** — Original code next to fixed code. Needs Rich layout experimentation. Deferred until the sequential diff panel approach is proven insufficient.
- **Git-auto-stage before edits** — Auto-staging current state before applying fixes. Deferred — .bak backup approach is sufficient initially.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FIX-01 | Generate code fixes based on diagnosis | FixEngine re-reads code via multi-turn LLM strategy (D-06), generates search-and-replace operations, produces unified diff patches using `difflib.unified_diff()` |
| FIX-02 | Suggest fixes for review before applying (not auto-apply) | Sequential human review workflow (D-09/D-10) with Accept/Skip/Reject per fix. Batch apply only after all reviewed (D-12). |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fix generation strategy (what to fix and how) | FixEngine (Orchestrator) | — | LLM decides based on hypothesis evidence + code re-reading |
| Code re-reading for context | FixEngine | — | Uses `_read_function_body` from Phase 2 to read relevant code before generating fix |
| LLM inference | ModelRouter | — | Same ModelRouter from Phase 2, dedicated system prompt, configurable via `ASCEND_FIX_MODEL` |
| Unified diff computation | FixEngine | — | Uses `difflib.unified_diff()` on original vs. modified code — not LLM-generated |
| File editing (search-and-replace) | Tool Layer (edit_file MCP tool) | — | Validates and applies replacements with .bak backup. Tool concern. |
| Fix review UI (sequential prompts) | CLI Layer (fix run command) | — | Rich interactive prompts. User-facing review workflow. Accept/Skip/Reject per fix. |
| Batch application summary | CLI Layer | FixEngine | Collection of accepted fixes, iterated for batch apply after all reviewed |
| Input parsing (diagnosis JSON) | CLI Layer | — | Reads DiagnosisOutput wrapper from file or stdin (D-17/D-18) |
| Output serialization (fixes JSON) | CLI Layer | — | Saves accepted FixSuggestion list to file (D-19) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| difflib (stdlib) | — | Unified diff generation | Part of Python standard library. `difflib.unified_diff()` produces canonical unified diff format that matches `git diff`. No additional dependency. |
| openai | >=2.37.0 | LLM client for structured outputs | Already installed. Same as Phase 2. |
| Pydantic | 2.13.4 | Data models for fix suggestions | Already installed. v2 with `ConfigDict(extra="forbid")` pattern established. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Rich | 15.0.0 | Interactive prompts + diff display | Already installed. `Prompt.ask(choices=...)` for Accept/Skip/Reject. `Syntax(code, "diff")` for diff highlighting. `Panel` for wrapping. |
| pathlib (stdlib) | — | File I/O, .bak backup, path resolution | Already used throughout codebase. `Path.read_bytes()`/`Path.write_bytes()` for backup. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| difflib.unified_diff (compute from LLM output) | LLM generating raw diff patch directly | LLMs are bad at `@@` hunk line numbers. Errors on line offsets are the #1 failure mode in code-editing LLM tools. Computing diff programmatically from verified search-and-replace is vastly more reliable. |
| difflib.unified_diff | subprocess `git diff` | `git diff` requires a git repo, adds subprocess overhead, and couples to git workflow. `difflib.unified_diff()` works on any file. |
| Rich Confirm.ask | Custom input() loop | Confirm is built for yes/no. 3-choice prompt needs `Prompt.ask(choices=...)`. Rich handles validation, retry, and display. |

**No new dependencies required.** All packages (openai, pydantic, rich, typer) are already installed from Phases 1 and 2.

**Version verification:**
```bash
pip show openai      # 2.37.0 — confirmed installed
pip show rich        # 15.0.0 — confirmed installed
pip show pydantic    # 2.13.4 — confirmed installed
```

## Package Legitimacy Audit

**No new packages introduced in this phase.** All dependencies are already installed and verified in Phases 1 and 2. The `difflib` module is part of Python standard library — no PyPI package needed.

## Architecture Patterns

### System Architecture Diagram

```
DiagnosisResult JSON (from Phase 2 --output)
         │
         ▼
┌──────────────────────────────────────┐
│  CLI: fix run [diagnosis.json]       │  Entry: reads DiagnosisOutput wrapper
│  - reads JSON from file or stdin     │  contains ContextDocument + DiagnosisResult
│  - instantiates FixEngine            │
└──────────┬───────────────────────────┘
           │ repo_path + hypotheses
           ▼
┌──────────────────────────────────────┐
│  FixEngine.generate_fixes()          │  Core: multi-turn fix generation
│                                      │
│  For each hypothesis:                │
│    ┌──────────────────────────────┐  │
│    │ 1. Read relevant code        │  │  _read_function_body at evidence file:line
│    │    (function body ±5 lines)  │  │
│    └──────────┬───────────────────┘  │
│               ▼                     │
│    ┌──────────────────────────────┐  │
│    │ 2. LLM call: generate fix    │  │  ModelRouter.completion() with
│    │    Output: structured         │  │  FixResponse model containing
│    │    replacements + explanation │  │  file_path + replacements list + explanation
│    └──────────┬───────────────────┘  │
│               ▼                     │
│    ┌──────────────────────────────┐  │
│    │ 3. Verify & compute diff     │  │  Read file, verify old_text exists
│    │    difflib.unified_diff()    │  │  Compute diff_patch from original vs modified
│    └──────────┬───────────────────┘  │
│               ▼                     │
│    ┌──────────────────────────────┐  │
│    │ 4. Assemble FixSuggestion    │  │  Pack file_path, diff_patch (unified diff
│    │    Append to results list    │  │  string), explanation, hypothesis_id
│    └──────────────────────────────┘  │
└──────────┬───────────────────────────┘
           │ list[FixSuggestion]
           ▼
┌──────────────────────────────────────┐
│  CLI: Sequential Review Workflow     │  Human review loop
│                                      │
│  For each FixSuggestion:             │
│    ┌──────────────────────────────┐  │
│    │ Show diff_patch in Panel     │  │  Rich Panel + Syntax("diff")
│    │ Show explanation             │  │  green/red highlighting
│    │ Prompt: [A]ccept [S]kip [R] │  │  Prompt.ask(choices=...)
│    └──────────┬───────────────────┘  │
│               ▼ action               │
│    Accept → queue for batch apply    │
│    Skip   → leave (not in output)    │
│    Reject → discard (not in output)  │
└──────────┬───────────────────────────┘
           │ list[FixSuggestion] (accepted only)
           ▼
┌──────────────────────────────────────┐
│  CLI: Batch Apply                    │  Apply all accepted fixes
│                                      │
│  For each accepted FixSuggestion:    │
│    ┌──────────────────────────────┐  │
│    │ Call edit_file MCP tool      │  │  search-and-replace with .bak
│    │ with replacements list       │  │
│    └──────────────────────────────┘  │
│  Show apply summary                  │
│  Save accepted fixes to JSON         │
└──────────────────────────────────────┘
```

### Recommended Project Structure
```
src/ascend_agent/
├── diagnosis/
│   ├── __init__.py            # Phase 2 (unchanged) — add FixSuggestion etc. to exports
│   ├── models.py              # ADD FixSuggestion, FixGenerationResult, DiagnosisOutput
│   ├── engine.py              # Phase 2 (unchanged)
│   └── router.py              # Phase 2 (unchanged — reused directly)
├── tools/
│   ├── file_edit.py           # REPLACE stub with search-and-replace implementation
│   └── server.py              # UPDATE edit_file description, remove [STUB] tag
├── cli/
│   ├── fix.py                 # REPLACE stub with full fix run command + review workflow
│   └── app.py                 # Unchanged (fix_app already registered)
```

**New/Modified Files:**

| File | Action | Purpose |
|------|--------|---------|
| `src/ascend_agent/diagnosis/models.py` | MODIFY | Add FixSuggestion, FixGenerationResult, DiagnosisOutput, FixResponse (LLM output model), Replacement |
| `src/ascend_agent/diagnosis/__init__.py` | MODIFY | Add new model exports |
| `src/ascend_agent/diagnosis/fix_engine.py` | CREATE | New FixEngine class following Engine pattern |
| `src/ascend_agent/tools/file_edit.py` | REPLACE | Implement search-and-replace with .bak validation |
| `src/ascend_agent/tools/server.py` | MODIFY | Update edit_file tool description, remove [STUB] tag |
| `src/ascend_agent/cli/fix.py` | REPLACE | Full fix run command + review workflow + batch apply + --output |
| `tests/test_diagnosis/test_fix_engine.py` | CREATE | FixEngine unit tests (similar pattern to test_engine.py) |
| `tests/test_tools/test_file_edit.py` | CREATE | edit_file unit tests |
| `tests/test_cli.py` | MODIFY | Add fix CLI integration tests |

### Pattern 1: FixEngine (follows Engine pattern from Phase 2)

**What:** A class that orchestrates fix generation. Takes `ModelRouter` + repo path + `DiagnosisResult`, iterates over hypotheses, re-reads relevant code, calls LLM for each fix, validates output, computes unified diffs, and returns `FixGenerationResult`.

**When to use:** The primary orchestration pattern for Phase 3. Required by D-05/D-06/D-07.

**Recommended design:**

```python
# Source: Engine class pattern from Phase 2 + D-06 design
# This shows the recommended implementation structure

import difflib
import logging
from pathlib import Path
from typing import Optional

from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    FixGenerationResult,
    FixSuggestion,
    FixResponse,     # LLM output model: replacements + explanation
    Replacement,     # {old_text, new_text}
)
from ascend_agent.diagnosis.router import ModelRouter

logger = logging.getLogger(__name__)


class FixEngine:
    """Generates fix suggestions for diagnosis hypotheses.

    Follows the Engine pattern from Phase 2: constructor takes
    router + repo_path, public method returns structured result.
    """

    def __init__(self, router: ModelRouter, repo_path: str):
        self._router = router
        self._repo_path = Path(repo_path).resolve()

    def generate_fixes(self, diagnosis: DiagnosisResult) -> FixGenerationResult:
        """Generate fix suggestions for all hypotheses in the diagnosis.

        For each hypothesis with evidence, re-read the relevant code,
        call the LLM to generate a fix, validate, and produce a FixSuggestion
        with a unified diff patch.
        """
        suggestions: list[FixSuggestion] = []
        errors: list[PartialFailure] = []

        for hypothesis in diagnosis.hypotheses:
            try:
                suggestion = self._generate_for_hypothesis(hypothesis)
                if suggestion is not None:
                    suggestions.append(suggestion)
            except Exception as exc:
                logger.warning("Fix generation failed for hypothesis: %s", exc)
                errors.append(PartialFailure(
                    stage="fix_generation",
                    reason=str(exc),
                    details=f"Hypothesis: {hypothesis.root_cause[:100]}",
                ))

        return FixGenerationResult(
            suggestions=suggestions,
            errors=errors,
            total_hypotheses=len(diagnosis.hypotheses),
        )

    def _generate_for_hypothesis(self, hypothesis) -> Optional[FixSuggestion]:
        """Generate a fix for a single hypothesis.

        1. Read relevant code from evidence file:line references
        2. Call LLM with code context + hypothesis
        3. Validate LLM output (old_text exists, unique match)
        4. Compute unified diff from original → modified
        5. Return FixSuggestion
        """
        # Step 1: Read code context from evidence
        code_context = self._read_code_context(hypothesis)
        if not code_context:
            logger.info("No code context available for hypothesis, skipping")
            return None

        # Step 2: LLM generates fix
        llm_response: FixResponse = self._router.completion(
            messages=[
                {"role": "system", "content": _build_fix_prompt()},
                {"role": "user", "content": _build_fix_user_prompt(
                    hypothesis=hypothesis,
                    code_context=code_context,
                )},
            ],
            response_model=FixResponse,
            max_tokens=4096,
            temperature=0.1,
        )

        # Step 3: Validate — read the file and verify old_text exists
        for hypothesis_id, replacement in enumerate(llm_response.replacements):
            file_path = self._repo_path / replacement.file_path
            if not file_path.exists():
                logger.warning("File not found: %s", file_path)
                continue
            original = file_path.read_text()
            if replacement.old_text not in original:
                logger.warning(
                    "old_text not found in %s — skipping replacement",
                    replacement.file_path,
                )
                continue
            if original.count(replacement.old_text) > 1:
                logger.warning(
                    "old_text appears multiple times in %s — skipping",
                    replacement.file_path,
                )
                continue

        # Step 4: Compute unified diff for human display
        # Apply replacements in-memory to compute the final text, then diff
        modified = original
        for rep in llm_response.replacements:
            modified = modified.replace(rep.old_text, rep.new_text, 1)

        diff_lines = difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=rep.file_path,
            tofile=rep.file_path,
        )
        diff_patch = "".join(diff_lines)

        return FixSuggestion(
            file_path=rep.file_path,
            diff_patch=diff_patch,
            explanation=llm_response.explanation,
            hypothesis_id=hypothesis_id,  # index or stored ID
            replacements=llm_response.replacements,
        )

    def _read_code_context(self, hypothesis) -> str:
        """Read code context from hypothesis evidence using _read_function_body."""
        from ascend_agent.diagnosis.engine import _read_function_body

        context_parts = []
        for evidence in hypothesis.evidence:
            full_path = self._repo_path / evidence.file_path
            snippet = _read_function_body(
                str(full_path), evidence.line_number, context_lines=5
            )
            if snippet:
                context_parts.append(
                    f"--- {evidence.file_path}:{evidence.line_number} ---\n{snippet}"
                )
        return "\n\n".join(context_parts)
```

### Pattern 2: LLM Output Model (structured output for fix generation)

**What:** The Pydantic model that the LLM fills in to describe a fix. The LLM outputs search-and-replace operations, NOT raw diff patches. The engine computes the diff.

**When to use:** This is the LLM response format for fix generation. Avoids LLM making errors on diff line numbers.

```python
# Source: D-13 (search-and-replace) + reliability research on LLM code editing
# LLMs are reliable at search-and-replace, unreliable at @@ line numbering

class Replacement(BaseModel):
    """A single search-and-replace operation on a file."""
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(
        description="Repo-relative path to the file being edited"
    )
    old_text: str = Field(
        description="Exact text to find in the file. Must match uniquely."
    )
    new_text: str = Field(
        description="Text to replace old_text with"
    )


class FixResponse(BaseModel):
    """Structured output from the LLM for a single hypothesis fix."""
    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(
        description="Clear explanation of what the fix does and why it addresses the root cause"
    )
    replacements: list[Replacement] = Field(
        min_length=1,
        description="One or more search-and-replace operations to fix the issue. "
                    "Multiple replacements in the same file are allowed. "
                    "If the fix touches multiple files, include one Replacement per file.",
    )
```

**Why this pattern matters:** By having the LLM output search-and-replace pairs instead of raw diff patches, we eliminate the #1 source of LLM code editing errors: incorrect `@@` line numbers in unified diffs. The LLM only needs to identify which code block to change and what to change it to — the engine computes accurate diffs.

### Pattern 3: Sequential Fix Review (Rich interactive workflow)

**What:** A CLI loop that shows each fix suggestion one at a time with Rich Panel + Syntax highlighting, then prompts the user for Accept [a], Skip [s], or Reject [r].

**When to use:** Required by D-09/D-10/D-11. After all fixes are reviewed, the accepted ones are applied in batch (D-12).

```python
# Source: Rich Prompt.ask documentation + D-09/D-10/D-11
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax

console = Console()

def run_review_workflow(suggestions: list[FixSuggestion]) -> list[FixSuggestion]:
    """Present fix suggestions for sequential human review.

    Returns: list of accepted FixSuggestion items (applied in batch later).
    """
    accepted: list[FixSuggestion] = []
    total = len(suggestions)

    for idx, suggestion in enumerate(suggestions, 1):
        # ── Header ──
        console.print(f"\n[bold cyan]Fix {idx}/{total}[/bold cyan] — [bold]{suggestion.file_path}[/bold]")

        # ── Explanation ──
        console.print(f"\n[bold]Explanation:[/bold] {suggestion.explanation}")

        # ── Diff display ──
        diff_syntax = Syntax(
            suggestion.diff_patch,
            "diff",
            theme="monokai",
            line_numbers=True,
        )
        console.print(Panel(
            diff_syntax,
            title=f"Suggested Changes — {suggestion.file_path}",
            border_style="blue",
        ))

        # ── Prompt ──
        action = Prompt.ask(
            "[bold]Action[/bold]",
            choices=["a", "s", "r"],
            default="s",
            show_choices=False,
        )
        console.print()  # blank line for spacing

        if action == "a":
            accepted.append(suggestion)
            console.print("[green]✓ Accepted[/green]")
        elif action == "s":
            console.print("[yellow]→ Skipped[/yellow]")
        elif action == "r":
            console.print("[red]✗ Rejected[/red]")

    return accepted
```

### Anti-Patterns to Avoid

- **LLM generating raw diff patches:** LLMs consistently produce incorrect `@@` line numbers when the surrounding context shifts. Always have the LLM output search-and-replace pairs and compute the diff programmatically.
- **Applying fixes during review:** D-15 explicitly says no dry-run preview mode in the tool. The fix engine produces the diff_patch, the review workflow shows it, and application happens only in the batch apply step. Mixing these concerns creates bugs.
- **Nested loops for multi-file fixes:** D-02 says one fix = one patch per file. If a fix touches 3 files, produce 3 FixSuggestion items all referencing the same hypothesis_id. Don't lump them into one.
- **Calling edit_file via MCP server from CLI:** The CLI process calls `edit_file` directly as a Python function (same pattern as Phase 2 calling `search_code` directly). No need to start the MCP server during CLI fix apply.
- **Interactive prompts after applying:** The review workflow is synchronous and sequential within the CLI. No async/await needed for the review loop itself.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Unified diff generation | Hand-rolled line comparison | `difflib.unified_diff()` | Standard library. Handles edge cases: file headers, @@ hunks, context lines, trailing newlines. Same format as `git diff`. |
| Diff syntax highlighting | Terminal color codes | Rich `Syntax(code, "diff")` | Uses Pygments DiffLexer. Correct green/red for +/- lines. Handles @@ headers, file headers. Consistent with Phase 2 diagnosis display. |
| Interactive prompt with validation | Custom `input()` loop with manual validation | Rich `Prompt.ask(choices=...)` | Built-in validation loop, handles edge cases (Ctrl+C, empty input, retry). Consistent with Rich usage pattern. |
| File backup before edit | Manual `.bak` manual copy | `Path.read_bytes()` + `Path.write_bytes()` | Simple: read original bytes, write `.bak`, then apply edit. No need for `shutil.copy2`. |
| JSON reading (file or stdin) | Separate file and stdin code paths | Check `sys.stdin.isatty()` | Already established in Phase 1 (diagnose CLI pattern). Reuse the same approach. |

**Key insight:** The hard parts of Phase 3 are the **prompt design for search-and-replace output** and the **validate → diff → display → review → apply pipeline orchestration**, not any individual component. Every sub-problem has a straightforward, existing solution.

## Common Pitfalls

### Pitfall 1: LLM Generates Imprecise Search Text
**What goes wrong:** The LLM's `old_text` doesn't exactly match any text in the file (whitespace differences, wrong indentation, trailing spaces).
**Why it happens:** LLMs approximate code. They may drop indentation, change spacing, or paraphrase code slightly.
**How to avoid:** In the system prompt, emphasize that `old_text` must be an **exact byte-for-byte match** of the original file content. Include explicit examples: "Copy the exact code block from the file, including all whitespace and indentation." On validation failure, log a clear error and skip the replacement (per D-08 single-shot approach).
**Warning signs:** `edit_file` validation rejects many replacements in early testing.

### Pitfall 2: old_text Matches Multiple Locations
**What goes wrong:** The search text appears in multiple places in the file (e.g., a common variable name or pattern).
**Why it happens:** The LLM copied a short code snippet that matches multiple locations. The tool doesn't know which one to replace.
**How to avoid:** Instruct the LLM to include sufficient surrounding context for uniqueness — not just the changed line but 2-3 lines around it. Validate uniqueness before applying: `original.count(old_text) == 1`.
**Warning signs:** `edit_file` validation reports multiple matches.

### Pitfall 3: Diff Display Shows Wrong Colors
**What goes wrong:** The unified diff displayed with Rich `Syntax(code, "diff")` doesn't show green/red correctly for +/- lines.
**Why it happens:** Pygments DiffLexer expects a specific format. If the diff is malformed (e.g., missing newlines or @@ headers), highlighting may be incorrect.
**How to avoid:** Always generate diffs through `difflib.unified_diff()` which produces correct format. Verify that the diff starts with `---` and `+++` headers followed by `@@` hunks.
**Warning signs:** Lines appear in wrong color or all one color.

### Pitfall 4: DiagnosisOutput Wrapper Missing Repo Path
**What goes wrong:** The diagnosis JSON loaded by `fix run` doesn't contain the repo path, so FixEngine can't read source files.
**Why it happens:** Phase 2's `--output` flag currently writes only the `ContextDocument` (no `DiagnosisResult`). Phase 3 needs a wrapper that includes both.
**How to avoid:** Before Phase 3's review workflow, the `diagnose run --output` must be updated to write the `DiagnosisOutput` wrapper (ContextDocument + DiagnosisResult). This is a required prerequisite — either included in Phase 3 or done as a Phase 2 patch.
**Warning signs:** FixEngine's `_read_code_context` returns empty for all hypotheses.

### Pitfall 5: Batch Apply Failure Mid-Stream
**What goes wrong:** The first fix applies successfully, the second fix fails because the first fix changed a file the second also targets.
**Why it happens:** Sequential application means earlier edits change the file state. If two FixSuggestions target the same file, the second one's `old_text` may no longer match.
**How to avoid:** Group accepted FixSuggestions by file_path. For each file, collapse replacements into a single batch call (edit_file accepts multiple replacements). Or apply one file at a time with all its replacements in one call. If a single file has multiple FixSuggestions referencing different hypotheses, apply all replacements for that file in one edit_file call.
**Warning signs:** edit_file returns "old_text not found" for second fix on same file.

### Pitfall 6: ModelRouter Not Reusable as-is
**What goes wrong:** `ModelRouter.__init__()` reads `ASCEND_DIAGNOSIS_MODEL` env var. Fix generation needs `ASCEND_FIX_MODEL`.
**Why it happens:** The ModelRouter's model selection logic looks at one env var (D-07 requires a separate one for fix).
**How to avoid:** Pass the model explicitly to ModelRouter constructor: `ModelRouter(model=os.environ.get("ASCEND_FIX_MODEL", "gpt-4o"))`. The ModelRouter already supports an explicit `model` parameter. Tests confirm this works: `ModelRouter(model="gpt-4o-2024-08-06")`.

## Code Examples

### Verification: difflib.unified_diff() format

```python
# Source: Python 3.14 stdlib difflib documentation
# Verified at: docs.python.org/3/library/difflib.html

import difflib

original = ["def foo():\n", "    return x + 1\n"]
modified = ["def foo():\n", "    return x + 2\n"]

diff = "".join(difflib.unified_diff(
    original, modified,
    fromfile="path/to/file.py",
    tofile="path/to/file.py",
))
print(diff)
# --- path/to/file.py
# +++ path/to/file.py
# @@ -1,2 +1,2 @@
#  def foo():
# -    return x + 1
# +    return x + 2
```

### Verification: Rich Syntax highlighting for diffs

```python
# Source: Pygments DiffLexer documentation
# Syntax("code", "diff") uses the DiffLexer from Pygments
# which correctly highlights:
#   - Lines starting with --- or +++ as file headers
#   - @@ lines as chunk headers
#   - Lines starting with - as diff.deleted (red)
#   - Lines starting with + as diff.inserted (green)
#   - Lines starting with space as context

from rich.syntax import Syntax
from rich.panel import Panel

diff_text = """--- path/to/file.py
+++ path/to/file.py
@@ -1,2 +1,2 @@
 def foo():
-    return x + 1
+    return x + 2"""

syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
panel = Panel(syntax, title="Suggested Changes", border_style="blue")
```

### Verification: Rich Prompt with choices for Accept/Skip/Reject

```python
# Source: Rich Prompt documentation
# rich.readthedocs.io/en/stable/prompt.html

from rich.prompt import Prompt

# 3-choice prompt with default
action = Prompt.ask(
    "[bold]Action[/bold] ([green]A[/green]ccept / [yellow]S[/yellow]kip / [red]R[/red]eject)",
    choices=["a", "s", "r"],
    default="s",
)
# Returns "a", "s", or "r" — validates input, loops on invalid

# Alternatively, use Confirm for yes/no questions:
from rich.prompt import Confirm
confirmed = Confirm.ask("Apply this fix?")
```

### Verification: edit_file tool with search-and-replace

```python
# Source: D-13/D-14/D-15/D-16 tool design
# Recommended implementation pattern

from pathlib import Path
from typing import Sequence


class EditOperation(BaseModel):
    """A single search-and-replace operation."""
    model_config = ConfigDict(extra="forbid")
    
    old_text: str
    new_text: str


def apply_replacements(
    file_path: str,
    operations: Sequence[EditOperation],
    create_backup: bool = True,
) -> dict:
    """Apply search-and-replace operations to a file.
    
    Args:
        file_path: Absolute path to the file to edit.
        operations: List of {old_text, new_text} operations.
        create_backup: If True, create file_path.bak before editing.
    
    Returns:
        Dict with "status": "ok" | "error" and "message" or "error" key.
    """
    path = Path(file_path)
    
    if not path.exists():
        return {"status": "error", "error": f"File not found: {file_path}"}
    
    original = path.read_text()
    
    # Validate all operations before applying any
    for op in operations:
        if op.old_text not in original:
            return {
                "status": "error",
                "error": f"old_text not found in file: {op.old_text[:60]}...",
            }
        if original.count(op.old_text) > 1:
            return {
                "status": "error",
                "error": f"old_text appears {original.count(op.old_text)} times in file. "
                          f"Include more surrounding context for uniqueness.",
            }
    
    # Create backup
    if create_backup:
        path.rename(path.with_suffix(path.suffix + ".bak"))
    
    # Apply all replacements (in order)
    result = original
    for op in operations:
        result = result.replace(op.old_text, op.new_text, 1)
    
    path.write_text(result)
    return {
        "status": "ok",
        "message": f"Applied {len(operations)} replacement(s) to {file_path}",
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LLM generates raw unified diff patch | LLM generates search-and-replace, engine computes diff | 2024-2025 (aider, codegen tools) | Eliminates @@ line number errors. Drastically improves reliability of LLM code edits. |
| Manual .bak via shutils | `Path.read_bytes()`/`write_bytes()` | Python 3.4+ | Simpler. Every pathlib user knows this pattern. No import needed beyond pathlib. |
| `input()` for interactive prompts | Rich `Prompt.ask(choices=...)` with validation | Rich 13.0+ (2023) | Built-in retry loop, case sensitivity options, type-answer options (first letter shortcuts). |

**Deprecated/outdated:**
- **Raw `input()` loops** in CLI: Use Rich prompts. They handle Ctrl+C gracefully, validate input, and retry automatically.
- **StringIO-based diff computation**: `difflib.unified_diff()` works directly with lists of strings. No need for intermediate StringIO objects.
- **LLM generating JSON with line numbers for edits**: Search-and-replace is more reliable. Line numbers shift when code is modified.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `diagnose run --output` flag will be updated to write `DiagnosisOutput` (ContextDocument + DiagnosisResult) before or during Phase 3 | Architecture | If the output wrapper doesn't include DiagnosisResult, fix run can't consume Phase 2 output directly. Mitigation: either modify Phase 2's `_one_shot_mode` to wrap both, or have fix run accept a separate diagnosis JSON. |
| A2 | The LLM's `FixResponse` output model can reliably produce valid search-and-replace `old_text` blocks | Patterm 1 | If LLM cannot copy text exactly (whitespace changes, truncation), validation fails. Mitigation: clear prompting + the single-shot skip-on-failure approach. |
| A3 | Multiple FixSuggestions for the same file can be safely collapsed | Pitfall 5 | If replacements overlap or conflict, batch apply may fail. Mitigation: validate all replacements before any apply. |
| A4 | `difflib.unified_diff()` output matches `git diff` format for display purposes | Code Examples | The visual format is nearly identical. If minor differences matter, use `subprocess.run(["git", "diff"])` instead. |

## Open Questions

1. **How should the `--output` flag in `diagnose run` be updated to include DiagnosisResult?**
   - What we know: Currently `_one_shot_mode` writes only the `ContextDocument` to the output file. Phase 3 needs both `ContextDocument` (for repo path) and `DiagnosisResult` (for hypotheses). D-18 calls this wrapper `DiagnosisOutput`.
   - What's unclear: Is this a Phase 2 modification (add after `engine.diagnose()`) or done within Phase 3 itself? Either way, the fix task in Phase 3 will need this to exist.
   - Recommendation: Include a small precursor task in Phase 3 Wave 1 to:
     1. Create `DiagnosisOutput` model in `diagnosis/models.py`
     2. Modify `cli/diagnose.py` `_one_shot_mode` to wrap both doc and result in `DiagnosisOutput`

2. **Should the `fix run` command call `edit_file` directly as a Python function or via the MCP server?**
   - What we know: Phase 2 calls `search_code` directly as `asyncio.run(search_code(...))` — no MCP server needed for CLI-internal calls. This pattern avoids starting a separate server process.
   - What's unclear: The `edit_file` signature currently has `ctx: Context | None = None`. As a direct call, ctx is None — which is fine since the full implementation doesn't use ctx for logging.
   - Recommendation: Follow Phase 2 pattern — call `edit_file` directly as a Python function via `asyncio.run()`. No need to start the MCP server for fix application during CLI batch apply.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | All code | ✓ | 3.10.8 | — |
| openai SDK | LLM calls | ✓ | 2.37.0 | — |
| Pydantic 2.x | Data models | ✓ | 2.13.4 | — |
| Rich | CLI display + prompts | ✓ | 15.0.0 | — |
| Typer | CLI framework | ✓ | (installed) | — |
| difflib (stdlib) | Unified diff computation | ✓ | — | — |
| pytest | Testing | ✓ | (via pip) | — |

**Missing dependencies with no fallback:** None — all dependencies already installed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7+ with pytest-asyncio |
| Config file | `pyproject.toml` under `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_diagnosis/test_fix_engine.py tests/test_tools/test_file_edit.py -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FIX-01 | FixEngine generates FixGenerationResult with suggestions for hypotheses | integration | `pytest tests/test_diagnosis/test_fix_engine.py -x` | ❌ Wave 0 |
| FIX-01 | FixEngine re-reads code before generating fix (multi-turn) | integration | `pytest tests/test_diagnosis/test_fix_engine.py::test_code_reread -x` | ❌ Wave 0 |
| FIX-01 | FixEngine skips hypotheses with malformed LLM output (no crash) | unit | `pytest tests/test_diagnosis/test_fix_engine.py::test_malformed_fix -x` | ❌ Wave 0 |
| FIX-01 | difflib.unified_diff produces correct patch format | unit | `pytest tests/test_diagnosis/test_fix_engine.py::test_diff_computation -x` | ❌ Wave 0 |
| FIX-02 | Review workflow accepts/skips/rejects fixes sequentially | integration | `pytest tests/test_cli.py::test_fix_review_workflow -x` | ❌ Wave 0 |
| FIX-02 | Accepted fixes are applied in batch after review | integration | `pytest tests/test_cli.py::test_fix_batch_apply -x` | ❌ Wave 0 |
| — | edit_file validates old_text existence | unit | `pytest tests/test_tools/test_file_edit.py::test_validate_old_text -x` | ❌ Wave 0 |
| — | edit_file creates .bak backup | unit | `pytest tests/test_tools/test_file_edit.py::test_backup_creation -x` | ❌ Wave 0 |
| — | edit_file rejects multiple matches | unit | `pytest tests/test_tools/test_file_edit.py::test_duplicate_old_text -x` | ❌ Wave 0 |
| — | FixSuggestion/FixGenerationResult Pydantic schema | unit | `pytest tests/test_diagnosis/test_models.py::test_fix_suggestion -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_diagnosis/test_fix_engine.py tests/test_tools/test_file_edit.py -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_diagnosis/test_fix_engine.py` — covers FixEngine class, code re-reading, diff computation, error handling
- [ ] `tests/test_tools/test_file_edit.py` — covers edit_file validation, backup, replacement application
- [ ] Update `tests/test_cli.py` — add fix CLI integration tests with CliRunner
- [ ] `tests/test_diagnosis/test_models.py` — add FixSuggestion, FixGenerationResult, FixResponse, Replacement schema tests
- [ ] No new framework installs needed — all dependencies already present

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | API key via env var (OPENAI_API_KEY) — already handled by ModelRouter |
| V5 Input Validation | yes | **File path validation** — `file_path` in FixSuggestion must resolve within repo dir. Prevent path traversal (e.g., `../../etc/passwd`). The `_repo_path_resolved / file_path` join and `.resolve()` step protects against this. Also: **old_text validation** — prevent regex injection by using plain string `in` not `re.search`. |
| V8 Data Protection | yes | `.bak` files contain code with potential secrets. Ensure they're cleaned up or gitignored. |
| V12 File and Resources | yes | `edit_file` writes to filesystem — validate file path is within repo boundary, not in `.git/` or protected system dirs. |

### Known Threat Patterns for Python Code Editing Stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Directory traversal via file_path | Tampering | Validate resolved path starts with repo_path. Use `Path.resolve()` and check `.startswith()`. |
| Overwriting .git/ files | Tampering | Block paths containing `/../` or resolved paths inside `.git/` directory. |
| .bak file leakage | Information Disclosure | Add `*.bak` to `.gitignore`. Clean up .bak files on successful apply (or leave for safety with message). |
| Large file write DoS | Denial of Service | Limit file size to 10MB in edit_file. Already handled by file open/read — OSError on huge files is caught. |

## Sources

### Primary (HIGH confidence)
- **Python stdlib difflib docs** — `unified_diff()` API, format, and examples [CITED: docs.python.org/3/library/difflib.html]
- **Rich Prompt documentation** — `Prompt.ask(choices=...)`, `Confirm.ask()` [CITED: rich.readthedocs.io/en/stable/prompt.html]
- **Rich Syntax documentation** — `Syntax(code, "diff", ...)` for diff highlighting [CITED: rich.readthedocs.io/en/stable/syntax.html]
- **Pygments DiffLexer** — Confirms "diff" is a supported lexer for unified diffs [CITED: pygments.org/docs/lexers/#lexers-for-diff-patch-formats]
- **Existing codebase (Phase 1 + Phase 2)** — Engine pattern, ModelRouter, _read_function_body, CLI patterns, test fixtures [VERIFIED: codebase grep]
- **Installed packages** — openai 2.37.0, rich 15.0.0, pydantic 2.13.4 [VERIFIED: pip show]

### Secondary (MEDIUM confidence)
- **Aider/edit formats** — Search-and-replace editing approach validated by Aider code editing tool [ASSUMED: training knowledge — Aider uses a "search/replace" edit block format that inspired this design]
- **GPT-Engineer file editing** — Similar search-and-replace pattern for LLM code editing [ASSUMED: training knowledge]

### Tertiary (LOW confidence)
- No tertiary sources needed — all technical claims verified against stdlib docs or existing codebase patterns.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed, verified, and used in prior phases
- Architecture: HIGH — FixEngine follows proven Engine pattern, difflib is stdlib, Rich prompt is verified
- Pitfalls: MEDIUM — search-and-replace edge cases (whitespace differences, duplicate matches) are documented by Aider and other LLM editing tools but need empirical validation in this codebase

**Research date:** 2026-05-21
**Valid until:** 2026-06-21 (no new external dependencies — only stdlib + existing libraries)
