# Phase 2: Diagnosis Engine - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the core diagnosis capability — analyze stack traces from the ContextDocument, use an LLM-driven search strategy to locate relevant source code, and generate ranked hypotheses with evidence.

**Requirements:** DIAG-01 (analyze stack traces → root cause + hypotheses with evidence), DIAG-02 (locate relevant source code from stack trace information)

**Success criteria from roadmap:**
1. Agent parses stack traces and extracts error locations
2. Agent searches codebase to find relevant source files
3. Agent proposes hypotheses with evidence (code snippets, line numbers)
</domain>

<decisions>
## Implementation Decisions

### Diagnosis Workflow
- **D-01:** Orchestration is an LLM-driven search strategy — the LLM reviews parsed trace frames, decides what to search for (function definitions, related patterns, error context), receives search results, and either initiates another search or produces a hypothesis. Not a rigid deterministic pipeline, not a full LangGraph state machine.
- **D-02:** Single-pass analysis with up to 3 LLM-driven search iterations max. The LLM gets 3 search rounds before it must produce a diagnosis.
- **D-03:** The engine works silently — does not ask clarifying questions. Ambiguities are noted in the output diagnosis.
- **D-04:** On failure (can't parse trace, code not found, etc.), report partial results + the specific failure reason. Never return empty/null without explanation.

### Hypothesis Structure
- **D-05:** Each hypothesis contains: root cause statement (what went wrong), evidence list (file:line references with code snippets), and a confidence score.
- **D-06:** Present top 3 hypotheses ranked by confidence. Not just top 1, not all above threshold.
- **D-07:** Evidence format is file:line references with code snippets (5-10 lines of surrounding context per evidence item).
- **D-08:** No explicit error categorization in Phase 2. Each hypothesis is standalone. Error categorization with VectorDB/RAG for Ascend NPU patterns is deferred as a future enhancement.

### Code Exploration
- **D-09:** Per trace frame, read the specific line + the surrounding function body (not just the line, not the entire file).
- **D-10:** The LLM decides which trace frames to search — it reviews the trace and picks exploration targets within the 3-search budget.
- **D-11:** Reading scope is function body ± 5 lines of surrounding context.
- **D-12:** No cross-reference following — only explore code directly referenced in the trace. No following imports, callers, or callees.

### The Agent's Discretion
- Model selection for the LLM calls — the Model Router layer is a thin wrapper; configure which model is used for diagnosis.
- Exact prompt engineering for the LLM search-decision loop and hypothesis generation.
- The data model / Pydantic schema for the diagnosis result (hypothesis list, confidence scoring format).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Definition
- `.planning/PROJECT.md` — Project vision, architecture layers (note Layer 3 Orchestrator and Layer 4 Model Router), constraints
- `.planning/REQUIREMENTS.md` — DIAG-01 and DIAG-02 requirements for Phase 2
- `.planning/ROADMAP.md` — Phase 2 goal, success criteria, full roadmap context (Phase 3 consumes diagnosis output)

### Phase 1 Foundation (Consumed by Phase 2)
- `.planning/phases/01-architecture-foundation/01-CONTEXT.md` — Context schema contract (ContextDocument), MCP tool layer patterns, CLI interface design
- `src/ascend_agent/context/models.py` — ContextDocument Pydantic model (input schema for Phase 2)
- `src/ascend_agent/tools/code_search.py` — code_search MCP tool (primary tool used by the LLM search strategy)
- `src/ascend_agent/tools/server.py` — FastMCP server with tool registration pattern

### Phase 2 Integration Points
- `src/ascend_agent/cli/diagnose.py` — Existing CLI command where diagnosis engine will be connected
- `src/ascend_agent/context/models.py` — ContextDocument consumed as input, diagnosis output schema to be created

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ContextDocument` Pydantic model (`src/ascend_agent/context/models.py`) — input schema contract designed for Phase 2 consumption
- `code_search` MCP tool (`src/ascend_agent/tools/code_search.py`) — ripgrep-based search with Python fallback, used by LLM search strategy
- `TraceParser` (`src/ascend_agent/context/trace.py`) — deterministic trace parsing, already handles file:line extraction
- `RepoScanner` (`src/ascend_agent/context/repo.py`) — repo structure scanning
- `diagnose` CLI command (`src/ascend_agent/cli/diagnose.py`) — one-shot + REPL modes, existing entry point to connect diagnosis engine
- FastMCP server (`src/ascend_agent/tools/server.py`) — tool registration and execution pattern

### Established Patterns
- Typer-based CLI with subcommands and Rich terminal output
- Pydantic v2 models with `ConfigDict(extra="forbid")`
- FastMCP for tool layer (async tools with `ctx.info()` for logging)
- Tests use pytest with conftest fixtures

### Integration Points
- `diagnose run` CLI command connects to the diagnosis engine (replaces current context-building-only behavior)
- Phase 2 diagnosis output (hypotheses with evidence) feeds into Phase 3 fix generation
- Code search MCP tool is the action layer for the LLM-driven search strategy
- REPL mode can become the interactive interface for the diagnosis engine

</code_context>

<specifics>
## Specific Ideas

- The user explicitly wants LLM integration in the diagnosis engine itself (not purely in a separate Model Router layer) — the LLM drives the search strategy and hypothesis generation
- The user wants to err on the side of getting a working diagnosis engine first — deferring categorization complexity (VectorDB/RAG for error patterns) to future iterations
- Starting simple and deferring complexity: this applies to code exploration (no cross-refs) and hypothesis format (no fix suggestions inline)
- The user specifically referenced Ascend NPU error types (dimension mismatch, OOM, dtype, attention) as eventual categorization targets

</specifics>

<deferred>
## Deferred Ideas

- **Error categorization with VectorDB/RAG** — Build a taxonomy of Ascend NPU error patterns (dimension, OOM, dtype, attention, etc.) with a VectorDB for pattern matching and RAG for diagnosis context. Belongs in a future enhancement phase after core diagnosis is proven.
- **Cross-reference following** — Following imports, callers, and callees for deeper code exploration. Deferred until trace-frames-only approach is insufficient.
- **Fix suggestions inline in diagnosis** — Blurs Phase 2/3 boundary. Keep Phase 2 focused on diagnosis, Phase 3 on fix generation.

</deferred>

---

*Phase: 2-Diagnosis Engine*
*Context gathered: 2026-05-21*
