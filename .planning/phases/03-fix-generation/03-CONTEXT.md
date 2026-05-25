# Phase 3: Fix Generation - Context

**Gathered:** 2026-05-21 (updated 2026-05-25)
**Status:** Ready for planning

<domain>
## Phase Boundary

Generate code fixes based on Phase 2 diagnosis findings. Takes `DiagnosisResult` with ranked hypotheses and evidence, re-reads relevant code, generates concrete fix suggestions (unified diff patches), and presents them for human review through a sequential accept/skip/reject workflow. Accepted fixes are queued and applied in batch.

**Requirements:** FIX-01 (generate code fixes based on diagnosis), FIX-02 (suggest fixes for review before applying)

**Success criteria from roadmap:**
1. Agent generates fix suggestions based on diagnosis
2. Agent presents fixes for human review (not auto-apply)
3. Agent can explain the reasoning behind each fix

</domain>

<decisions>
## Implementation Decisions

### Fix Representation Format
- **D-01:** Fixes use search-and-replace (old_text → new_text) as the primary internal representation. Unified diff patches are computed from replacements via `difflib.unified_diff()` for human display only. The LLM outputs structured `Replacement` objects (file_path, old_text, new_text), not patch text.
- **D-02:** One fix = one patch over one file. If a fix touches multiple files, produce multiple patches referencing the same hypothesis.
- **D-03:** Patch display uses Rich Syntax with the "diff" lexer and line numbers inside a Rich Panel (reusing the display pattern from Phase 2). Display shows the computed unified diff, not raw patch text.
- **D-04:** Pydantic model: `FixSuggestion` per file (file_path, diff_patch, explanation, hypothesis_id, replacements list). `FixGenerationResult` wraps a list of `FixSuggestion` with errors and total count.

### Fix Engine Design
- **D-05:** Generate fixes for all hypotheses in the diagnosis, not just the top one.
- **D-06:** Multi-turn LLM strategy — the fix engine re-reads relevant code before generating a fix, similar to the diagnosis engine pattern. Not one-shot from evidence alone.
- **D-07:** Reuse the same `ModelRouter` abstraction from Phase 2, with a dedicated system prompt for fix generation. Configurable via `ASCEND_FIX_MODEL` env var (default: `gpt-4o`).
- **D-08:** Single-shot per hypothesis. LLM reads code, generates one fix. If malformed, note the error and move on. No iterative validation/retry initially.

### Human Review Workflow
- **D-09:** Sequential review — show one fix at a time. Focused review per fix, not batch view.
- **D-10:** Actions per fix: Accept / Skip / Reject. Accept queues the fix for later application, Skip leaves it, Reject discards it.
- **D-11:** Diff display uses Rich Panel + Syntax with the "diff" lexer showing line numbers (green for added, red for removed), reusing the approach from Phase 2 diagnosis display.
- **D-12:** Accepted fixes are queued and applied in batch after all fixes are reviewed. User sees a summary of what was applied.

### edit_file Tool Design
- **D-13:** Operation model: search-and-replace. Accepts `old_text` + `new_text`. Finds exact match of `old_text` in the file and replaces it. Precise and verifiable.
- **D-14:** Create `.bak` backup before each edit.
- **D-15:** Apply directly — no preview/dry-run mode in the tool itself. Preview is handled by the fix generation review workflow.
- **D-16:** Accepts multiple replacements in one call (list of `{old_text, new_text}` operations). All validated before any are applied.

### Batch Application (new)
- **D-20:** Batch application groups accepted fix suggestions by file, collapses all replacements per file, calls `edit_file` once per file with the full replacement list.

### Downstream Contracts (new)
- **D-21:** `FixSuggestion` schema is stable/frozen — downstream phases (Phase 4 Reproduction, Phase 5 Verification) can depend on its shape. Agents read `src/ascend_agent/diagnosis/models.py` for the schema. Output-only contract — downstream phases do not depend on Phase 3 internals (FixEngine, edit_file).

### Engineering Patterns (new — graduated from Agent's Discretion)
- **D-22:** FixEngine follows the Phase 2 Engine pattern: constructor takes `router: ModelRouter` + `repo_path`, public `generate_fixes()` method returns `FixGenerationResult` with structured error handling via `PartialFailure`.
- **D-23:** `DiagnosisOutput` wraps `ContextDocument` + `DiagnosisResult` to provide the repo path for FixEngine. Saved by `diagnose --output`.
- **D-24:** Two-layer model design: `FixResponse` is the LLM output model (freeform `replacements` list), `FixSuggestion` is the persisted artifact (validated `replacements` + computed `diff_patch` + metadata).

### Fix Validation Rules (new — graduated from Agent's Discretion)
- **D-25:** FixEngine validates each replacement before producing a FixSuggestion. Checks: (a) exact `old_text` match exists in file, (b) match is unique (includes sufficient surrounding context), (c) resolved file path stays within repo boundary (path traversal protection), (d) target file exists. Invalid replacements are skipped with a warning log.

### Diagnosis Integration
- **D-17:** `ascend-agent fix run [diagnosis.json]` — if argument is a file path, read from file; if no argument, read from stdin.
- **D-18:** Repo path extracted from the diagnosis JSON via a wrapper that includes both `ContextDocument` and `DiagnosisResult`. The `--output` flag on `diagnose run` saves this wrapper.
- **D-19:** `--output fixes.json` saves the list of accepted `FixSuggestion` entries with their diffs for audit/scripting.

### The Agent's Discretion
- Exact prompt engineering for the fix generation LLM calls (system prompt, user prompt format).
- Test approach and coverage targets.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Definition
- `.planning/PROJECT.md` — Project vision, architecture layers, constraints (all fixes require human review)
- `.planning/REQUIREMENTS.md` — FIX-01 and FIX-02 requirements for Phase 3
- `.planning/ROADMAP.md` — Phase 3 goal, success criteria, full roadmap context (Phase 4 consumes fix output)

### Phase 1 & 2 Foundation (Consumed by Phase 3)
- `.planning/phases/01-architecture-foundation/01-CONTEXT.md` — MCP tool patterns, CLI structure, edit_file stub planned for Phase 3
- `.planning/phases/02-diagnosis-engine/02-CONTEXT.md` — Diagnosis engine pattern (multi-turn LLM strategy), ModelRouter design, deferred fix suggestions
- `.planning/phases/02-diagnosis-engine/02-RESEARCH.md` — Research findings that informed diagnosis engine choices

### Phase 3 Implementation (Implemented — consumed by downstream phases)
- `src/ascend_agent/diagnosis/models.py` — FixSuggestion, FixGenerationResult, FixResponse, Replacement, DiagnosisOutput models (stable schema, D-21)
- `src/ascend_agent/diagnosis/fix_engine.py` — FixEngine class implementing fix generation logic (D-22, D-24, D-25)
- `src/ascend_agent/cli/fix.py` — `fix run` CLI command with sequential review and batch apply (D-09 through D-12, D-17, D-19, D-20)
- `src/ascend_agent/tools/file_edit.py` — edit_file MCP tool with search-and-replace, .bak backup, multi-replacement validation (D-13 through D-16)

### Phase 1 & 2 Foundation (Patterns reused by Phase 3)
- `src/ascend_agent/diagnosis/engine.py` — Engine pattern (multi-turn LLM loop, ModelRouter integration)
- `src/ascend_agent/diagnosis/router.py` — ModelRouter abstraction reused for fix generation
- `src/ascend_agent/cli/diagnose.py` — Diagnose command pattern (one-shot + --output, Rich display)
- `src/ascend_agent/tools/server.py` — FastMCP server with tool registration pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ModelRouter` in `src/ascend_agent/diagnosis/router.py` — OpenAI client wrapper with structured outputs via `.parse()`. Reused directly for fix generation LLM calls.
- `Engine` class in `src/ascend_agent/diagnosis/engine.py` — Multi-turn LLM loop pattern with search iterations. FixEngine follows the same architecture.
- `_read_function_body` in `src/ascend_agent/diagnosis/engine.py` — AST-based function extraction. FixEngine uses this to read code before generating fixes.
- `DiagnosisResult` in `src/ascend_agent/diagnosis/models.py` — Input model for fix generation. Contains `hypotheses` with `evidence` (file:line + code snippets).
- `FixSuggestion` in `src/ascend_agent/diagnosis/models.py` — Output model consumed by Phase 4/5. Contains `file_path`, `diff_patch`, `explanation`, `hypothesis_id`, `replacements`. Stable schema (D-21).
- Rich Panel + Syntax display pattern in `src/ascend_agent/cli/fix.py` — Used for diff review display.
- FastMCP server in `src/ascend_agent/tools/server.py` — `edit_file` tool registered and implemented.

### Established Patterns
- Typer-based CLI with subcommands, Rich terminal output.
- Pydantic v2 models with `ConfigDict(extra="forbid")`.
- FastMCP for tool layer (async tools, `ctx.info()` for logging).
- Tests use pytest with conftest fixtures and CliRunner for CLI integration tests.
- Engine pattern: constructor takes `router: ModelRouter` + repo_path, public `fix()` method returns structured result.
- LLM strategy: multi-turn with system prompt + context accumulation, `openai .parse()` for structured outputs.

### Integration Points
- `fix run` CLI command accepts diagnosis JSON file or stdin, produces accepted fix suggestions.
- `edit_file` MCP tool is fully implemented with search-and-replace, .bak backup, multi-replacement validation.
- Fix engine reads the repo via Path to access source files for context.
- Review workflow happens in the CLI process (not MCP) — Rich interactive prompt loop.
- Batch application of accepted fixes groups by file, collapses replacements, calls `edit_file` once per file.
- Phase 4 consumes `FixSuggestion` schema (stable, D-21) from `--output fixes.json` output.

</code_context>

<specifics>
## Specific Ideas

- The user wants to follow the same "start simple, defer complexity" approach as Phase 1 and 2. Everything captured in decisions above starts simple and has clear paths to add complexity later.
- Multi-turn code re-reading before fixing mirrors the Phase 2 engine pattern — consistency across phases.
- Search-and-replace for edit_file was chosen specifically because LLMs can generate matching context blocks reliably, and it avoids the line-number brittleness of position-based edits.

</specifics>

<deferred>
## Deferred Ideas

- **Iterative fix validation with retry** — Could add syntax checking and retry logic for malformed patches in a future maintenance phase after the single-shot approach is proven.
- **Modify-fix during review** — Allowing the user to edit a fix suggestion inline before accepting. Complex UI in terminal. Deferred to a future UX improvement phase.
- **Side-by-side diff view** — Original code next to fixed code. Needs Rich layout experimentation. Deferred until the sequential diff panel approach is proven insufficient.
- **Git-auto-stage before edits** — Auto-staging current state before applying fixes. Deferred — .bak backup approach is sufficient initially.

</deferred>

---

*Phase: 3-Fix Generation*
*Context gathered: 2026-05-21*
