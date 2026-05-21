# Phase 2: Diagnosis Engine - Research

**Researched:** 2026-05-21
**Domain:** LLM-driven code diagnosis engine — stack trace analysis, iterative code search, hypothesis generation
**Confidence:** MEDIUM

## Summary

Phase 2 implements the core diagnosis capability: ingest a `ContextDocument` (built in Phase 1), use an LLM-driven search strategy to locate relevant source code, and produce ranked hypotheses with evidence. The engine follows a **silent, iterative loop** with up to 3 search iterations — the LLM reviews parsed trace frames, decides what to search for, receives results, and either initiates another search or produces a final diagnosis.

The architecture is intentionally simple: an `Engine` class orchestrates the loop, a thin `ModelRouter` abstraction wraps the LLM client, and Pydantic v2 models define the diagnosis output schema. The existing `code_search` MCP tool provides the action layer. No LangGraph, no VectorDB, no cross-references — just an LLM driving a focused search with structured output guarantees.

**Primary recommendation:** Use the `openai` SDK (≥2.37.0) for LLM calls with structured outputs via `client.chat.completions.parse(response_format=PydanticModel)`. Implement the diagnosis engine as a synchronous `Engine` class in a new `src/ascend_agent/diagnosis/` package. Wire it into the existing CLI `diagnose run` command.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Orchestration is an LLM-driven search strategy — the LLM reviews parsed trace frames, decides what to search for (function definitions, related patterns, error context), receives search results, and either initiates another search or produces a hypothesis. Not a rigid deterministic pipeline, not a full LangGraph state machine.
- **D-02:** Single-pass analysis with up to 3 LLM-driven search iterations max. The LLM gets 3 search rounds before it must produce a diagnosis.
- **D-03:** The engine works silently — does not ask clarifying questions. Ambiguities are noted in the output diagnosis.
- **D-04:** On failure (can't parse trace, code not found, etc.), report partial results + the specific failure reason. Never return empty/null without explanation.
- **D-05:** Each hypothesis contains: root cause statement (what went wrong), evidence list (file:line references with code snippets), and a confidence score.
- **D-06:** Present top 3 hypotheses ranked by confidence. Not just top 1, not all above threshold.
- **D-07:** Evidence format is file:line references with code snippets (5-10 lines of surrounding context per evidence item).
- **D-08:** No explicit error categorization in Phase 2. Each hypothesis is standalone. Error categorization with VectorDB/RAG for Ascend NPU patterns is deferred as a future enhancement.
- **D-09:** Per trace frame, read the specific line + the surrounding function body (not just the line, not the entire file).
- **D-10:** The LLM decides which trace frames to search — it reviews the trace and picks exploration targets within the 3-search budget.
- **D-11:** Reading scope is function body ± 5 lines of surrounding context.
- **D-12:** No cross-reference following — only explore code directly referenced in the trace. No following imports, callers, or callees.

### The Agent's Discretion

- Model selection for the LLM calls — the Model Router layer is a thin wrapper; configure which model is used for diagnosis.
- Exact prompt engineering for the LLM search-decision loop and hypothesis generation.
- The data model / Pydantic schema for the diagnosis result (hypothesis list, confidence scoring format).

### Deferred Ideas (OUT OF SCOPE)

- Error categorization with VectorDB/RAG for Ascend NPU error patterns (dimension, OOM, dtype, attention, etc.)
- Cross-reference following (imports, callers, callees)
- Fix suggestions inline in diagnosis (blurs Phase 2/3 boundary)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DIAG-01 | Analyze stack traces to identify root cause and propose hypotheses with evidence | LLM-driven search loop with structured output guarantees. Pydantic models for Hypothesis (root_cause, evidence list, confidence). Up to 3 search iterations. Silent mode. |
| DIAG-02 | Locate relevant source code from stack trace information | LLM reviews trace frames (D-10), issues code_search MCP tool calls with function names/pattern hints. Code snippets extracted at function body ±5 lines scope. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Search strategy (what to search for) | Diagnosis Engine (Orchestrator) | — | LLM decides based on trace frames — this is the core orchestration logic |
| Source code search execution | Diagnosis Engine | Tool Layer | calls `code_search` MCP tool (already exists in tool layer) |
| Code reading / snippet extraction | Diagnosis Engine | — | needs to read file:line + surrounding function body — custom utility, not a tool |
| LLM inference | Model Router | — | Thin wrapper around OpenAI client. Engine depends on abstract interface |
| Hypothesis generation | Diagnosis Engine | — | LLM produces structured hypothesis via response_format |
| CLI output (Rich display) | CLI Layer | — | Already established pattern in `diagnose run` command |
| Input schema (ContextDocument) | Context Builder | — | Consumed from Phase 1, no changes needed |
| Output schema (DiagnosisResult) | Diagnosis Engine | — | New Pydantic models for DIAG-01/DIAG-02 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openai | >=2.37.0 | LLM client for structured outputs | Industry standard SDK. `.parse()` method auto-converts Pydantic models to JSON schema and parses responses back. Supports all OpenAI-compatible APIs including local models, Azure, and proxy services. |
| Pydantic | 2.13.4 (installed) | Data models for hypotheses, evidence, diagnosis result | Already in project. v2 with `ConfigDict(extra="forbid")` pattern established in Phase 1. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| mcp | 1.27.1 (installed) | Tool layer (code_search) | Already installed. Engine calls `search_code` directly, not via MCP server transport. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| openai SDK direct | LiteLLM (1.85.1) | LiteLLM provides unified interface across 100+ providers but adds 60MB dependency, has its own error handling patterns, and introduces an extra abstraction layer. The openai SDK is simpler if only using OpenAI-compatible APIs. LiteLLM is the right choice if multi-provider routing is needed in Phase 4/5 (Model Router). |
| openai SDK direct | Anthropic SDK (0.103.1) | If Claude is the target model, the Anthropic SDK has its own structured output support (tools with `input_schema`). Less ecosystem integration than openai SDK. |
| openai SDK direct | Custom HTTP calls to API | No SDK handles retries, streaming, structured output parsing. Hallucination vector. |

**Installation:**
```bash
pip install 'openai>=2.37.0'
pip install 'pydantic>=2.13.0'  # already installed
```

**Version verification:**
```bash
pip index versions openai       # 2.37.0 (verified)
pip index versions pydantic     # 2.13.4 (verified)
```

## Package Legitimacy Audit

> Protocol: slopcheck 0.6.1 installed and run. All packages verified on PyPI registry.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| openai | PyPI | ~4 yrs (since 0.0.2 in 2023) | Very high | github.com/openai/openai-python | [OK] | Approved |
| pydantic | PyPI | ~5 yrs | Very high | github.com/pydantic/pydantic | [OK] (pre-installed) | Approved |
| mcp | PyPI | ~1 yr | Moderate | github.com/modelcontextprotocol/python-sdk | [OK] (pre-installed) | Approved |
| typer | PyPI | ~5 yrs | High | github.com/fastapi/typer | [OK] (pre-installed) | Approved |
| rich | PyPI | ~4 yrs | Very high | github.com/Textualize/rich | [OK] (pre-installed) | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
**Note:** Depending on model choice, the Anthropic SDK (`anthropic`) was also verified [OK]. If multi-provider routing becomes necessary, LiteLLM (`litellm`) is the standard choice but could not be verified due to PyPI registry timeout — mark as `[ASSUMED]` if used later.

## Architecture Patterns

### System Architecture Diagram

```
User Input (--trace / --trace-text / stdin)
         │
         ▼
┌──────────────────┐
│  CLI (diagnose   │  Phase 1: Entry Point
│  run command)    │  builds ContextDocument
└────────┬─────────┘
         │ ContextDocument (already built)
         ▼
┌──────────────────┐
│  Engine.diagnose │  Phase 2 Core: LLM-driven search loop
│  (ContextDocument│
│   → DiagnosisResult)
└────────┬─────────┘
         │
         ├────Iteration 1────► LLM reviews trace → decides search(es)
         │                         │
         │                    ┌────▼────┐
         │                    │  code   │  (existing MCP tool)
         │                    │  search │
         │                    └────┬────┘
         │                         │ results
         ├────Iteration 2────► LLM reviews + decides next search
         │                         │
         │                    ┌────▼────┐
         │                    │  code   │
         │                    │  search │
         │                    └────┬────┘
         │                         │ results
         ├────Iteration 3────► LLM reviews + produces hypothesis
         │                         │
         ▼                         ▼
┌─────────────────────────────────────────┐
│  DiagnosisResult                        │  Output Models
│  ├── hypotheses: list[Hypothesis]       │  top 3, ranked by confidence
│  └── error (if partial failure)         │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌──────────────────┐
│  CLI (Rich       │  Display: ranked hypotheses
│  display)        │  with evidence snippets
└──────────────────┘
```

### Recommended Project Structure
```
src/ascend_agent/
├── diagnosis/                # NEW: Phase 2 package
│   ├── __init__.py
│   ├── engine.py             # Engine class — orchestrates the LLM search loop
│   ├── models.py             # Hypothesis, Evidence, DiagnosisResult Pydantic models
│   └── router.py             # ModelRouter — thin wrapper around OpenAI client
├── context/                  # Phase 1 (unchanged)
│   ├── models.py             # ContextDocument — input schema
│   └── trace.py              # TraceParser — already handles file:line extraction
├── tools/
│   ├── code_search.py        # Phase 1 (unchanged) — LLM calls this
│   └── server.py             # Phase 1 (unchanged)
└── cli/
    ├── app.py                # Phase 1 (unchanged)
    └── diagnose.py           # Phase 1 — wire Engine in
```

### Pattern 1: LLM-Driven Search Loop

**What:** A loop where the LLM controls what to search for, how deeply, and when to produce a hypothesis. The engine provides the loop structure, tool access, and iteration budget.

**When to use:** This is the primary pattern for Phase 2. Required by D-01 and D-02.

**Example:**

```python
# Source: openai SDK structured outputs pattern + D-01/D-02 design
# This is a recommended implementation approach

from openai import OpenAI
from ascend_agent.diagnosis.models import DiagnosisResult, SearchDecision, Hypothesis

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def diagnose(client: OpenAI, context: ContextDocument, repo_path: str) -> DiagnosisResult:
    """LLM-driven search loop — max 3 search iterations."""
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE},
        {"role": "user", "content": _build_initial_prompt(context)},
    ]
    search_results = []
    
    for iteration in range(3):
        # Step 1: LLM decides what to do (search or produce diagnosis)
        response = client.chat.completions.parse(
            model="gpt-4o",  # or configured model
            messages=messages + _format_search_results(search_results),
            response_format=SearchDecision,
        )
        
        decision = response.choices[0].message.parsed
        
        if decision.action == "hypothesize":
            # Produce final diagnosis
            final = client.chat.completions.parse(
                model="gpt-4o",
                messages=messages + _format_search_results(search_results) + [
                    {"role": "assistant", "content": "Producing final diagnosis..."},
                    {"role": "user", "content": "Generate your top 3 hypotheses with evidence."},
                ],
                response_format=DiagnosisResult,
            )
            return final.choices[0].message.parsed
        
        # Step 2: Execute the search
        for search in decision.searches:
            result = await search_code(search.pattern, repo_path, ctx=None)
            search_results.append({
                "search": search,
                "result": result,
            })
    
    # Fallback: exhausted budget, force hypothesis
    final = client.chat.completions.parse(
        model="gpt-4o",
        messages=messages + _format_search_results(search_results) + [
            {"role": "user", "content": "Search budget exhausted. Generate best hypotheses with available information."},
        ],
        response_format=DiagnosisResult,
    )
    return final.choices[0].message.parsed
```

### Pattern 2: Model Router Abstraction

**What:** A Protocol-based abstraction for the LLM client, so the diagnosis engine doesn't depend on the OpenAI SDK directly. Allows swapping models/providers without changing engine code.

**When to use:** Required by PROJECT.md Layer 4 (Model Router). Keep it thin — just enough to decouple.

```python
# Source: inferred from PROJECT.md Layer 4 + discretion area
from typing import Protocol, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LLMClient(Protocol):
    """Abstract LLM interface — engine depends on this, not concrete SDK."""
    
    def chat_completion(
        self,
        messages: list[dict],
        response_model: type[T],
        **kwargs,
    ) -> T:
        """Send messages, return parsed response_model instance."""
        ...
```

### Anti-Patterns to Avoid

- **LangGraph for Phase 2:** D-01 explicitly rejects "full LangGraph state machine." The engine is a simple Python loop with 3 max iterations. LangGraph only becomes relevant in Phase 4/5 when multi-step orchestration with branching is needed.
- **VectorDB/RAG for error categorization:** D-08 defers this. Do not add ChromaDB, FAISS, or embedding logic in Phase 2.
- **Cross-reference following in code reading:** D-12 forbids following imports/callers/callees. Reading scope is strictly trace frames + function body ±5 lines.
- **Asking clarifying questions:** D-03 mandates silent mode. Ambiguities go into the output diagnosis notes, not to the user.
- **Hardcoding the model name in engine code:** Use the Model Router abstraction. The model choice is a configuration concern (discretion area), not an engine concern.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM client with retries, auth, streaming | Custom HTTP wrapper | `openai` SDK | Standard SDK handles connection pooling, rate limiting, retries, structured output parsing. Custom HTTP would need to implement all of this. |
| JSON response schema enforcement | Manual JSON parsing with validation | OpenAI `.parse()` with Pydantic | `.parse()` auto-converts Pydantic models to JSON schema, sends as `response_format`, and parses the response back into the model. Handles refusals and truncation. |
| Code search / regex search | Custom `os.walk` + grep | Existing `code_search` MCP tool | Phase 1 already built this. It handles ripgrep with Python-native fallback, respects `.gitignore`, limits to `.py` files, and truncates long output. |
| Trace parsing / regex for file:line extraction | Custom regex | Existing `TraceParser` | Phase 1 already built this. It parses `File "X", line Y, in Z` format and extracts error type/message. |

**Key insight:** The hard parts of this phase are the **prompt design** and the **loop orchestration logic**, not the infrastructure. Use existing tools and standard SDKs.

## Common Pitfalls

### Pitfall 1: Response Truncation
**What goes wrong:** The LLM's structured output response exceeds the `max_tokens` limit, producing truncated JSON that fails parsing.
**Why it happens:** The diagnosis result with 3 hypotheses + code snippets comfortably fits in 4K tokens, but if the LLM generates very verbose evidence descriptions, it can exceed 8K.
**How to avoid:** Set `max_tokens=4096` for search decisions (small output) and `max_tokens=8192` for hypothesis generation. Check `finish_reason == "length"` and retry with reduced expectations.
**Warning signs:** `openai.LengthFinishReasonError` is raised when using `.parse()`.

### Pitfall 2: LLM Over-Searching
**What goes wrong:** The LLM uses all 3 search iterations on the same trace frame, never moving on to hypothesis generation.
**Why it happens:** The prompt doesn't clearly instruct the LLM to move on when sufficient information is gathered.
**How to avoid:** Structure the SearchDecision model to require a clear reason for additional search vs. hypothesis generation. Include explicit instructions: "If you have enough information, output `hypothesize`."
**Warning signs:** Code search results show the same function being queried in multiple iterations.

### Pitfall 3: Code Snippet Extraction Off-by-One
**What goes wrong:** The function body ±5 lines context window misses the actual error line or captures the wrong function when functions are closely stacked.
**Why it happens:** Python AST or naive line counting doesn't properly handle nested functions, decorators, or class methods.
**How to avoid:** Read the file, then use Python's `ast` module to locate function boundaries precisely. The `ast` module handles nested functions and decorators correctly.
**Warning signs:** Evidence snippets show `def` of a parent function but not the inner function containing the error.

### Pitfall 4: OpenAI API Key Not Set
**What goes wrong:** The diagnosis engine crashes on first LLM call because `OPENAI_API_KEY` is missing.
**Why it happens:** The existing code has no LLM dependency, so there's no API key configuration yet.
**How to avoid:** Add explicit validation in `ModelRouter.__init__()` that raises a clear error (not `AuthenticationError` from SDK). Document the env var requirement in the CLI help text.
**Warning signs:** Engine fails immediately when starting diagnosis.

## Code Examples

### Pydantic Models for Diagnosis Output

```python
# Source: openai SDK structured outputs + D-05/D-06/D-07 requirements
from pydantic import BaseModel, Field, ConfigDict


class Evidence(BaseModel):
    """A single piece of evidence supporting a hypothesis."""
    model_config = ConfigDict(extra="forbid")
    
    file_path: str = Field(description="Absolute or repo-relative path to the source file")
    line_number: int = Field(ge=1, description="Line number where the evidence is found")
    code_snippet: str = Field(description="5-10 lines of surrounding code context")
    relevance: str = Field(description="Why this evidence is relevant to the hypothesis")


class Hypothesis(BaseModel):
    """A single diagnosis hypothesis with supporting evidence."""
    model_config = ConfigDict(extra="forbid")
    
    root_cause: str = Field(description="What went wrong — concise statement of the root cause")
    evidence: list[Evidence] = Field(description="Supporting evidence items (file:line + code snippets)")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0 to 1.0")


class SearchAction(BaseModel):
    """A single search the LLM wants to perform."""
    model_config = ConfigDict(extra="forbid")
    
    pattern: str = Field(description="Regex or function name to search for")
    rationale: str = Field(description="Why this search will help the diagnosis")


class SearchDecision(BaseModel):
    """LLM decides: perform more searches or produce final diagnosis."""
    model_config = ConfigDict(extra="forbid")
    
    action: str = Field(pattern=r"^(search|hypothesize)$", description="'search' to continue, 'hypothesize' to produce final diagnosis")
    searches: list[SearchAction] = Field(
        default_factory=list,
        description="Searches to perform. Only set when action='search'. Max 3 searches per iteration.",
    )
    reasoning: str = Field(description="Brief explanation of the decision")


class PartialFailure(BaseModel):
    """Information about a partial failure during diagnosis."""
    model_config = ConfigDict(extra="forbid")
    
    stage: str = Field(description="Where the failure occurred (e.g., 'search', 'code_read', 'llm_call')")
    reason: str = Field(description="Specific failure reason")
    details: str | None = Field(default=None, description="Additional details (error message, etc.)")


class DiagnosisResult(BaseModel):
    """Final output of the diagnosis engine."""
    model_config = ConfigDict(extra="forbid")
    
    hypotheses: list[Hypothesis] = Field(
        default_factory=list,
        description="Top 3 hypotheses ranked by confidence (highest first)",
    )
    errors: list[PartialFailure] = Field(
        default_factory=list,
        description="Partial failures encountered. Never empty without explanation (D-04).",
    )
    iterations_used: int = Field(ge=0, le=3, description="Number of search iterations actually used")
```

### LLM-Driven Search Loop — Engine Core

```python
# Source: openai SDK .parse() + D-01/D-02 loop design
# This shows the recommended implementation pattern

import logging
from ascend_agent.diagnosis.models import DiagnosisResult, SearchDecision, Hypothesis
from ascend_agent.diagnosis.router import ModelRouter

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3

class Engine:
    """Orchestrates the LLM-driven diagnosis search loop."""
    
    def __init__(self, router: ModelRouter, repo_path: str):
        self._router = router
        self._repo_path = repo_path
    
    def diagnose(self, context_doc: "ContextDocument") -> DiagnosisResult:
        """Run the diagnosis loop. Returns structured result."""
        ctx = _build_initial_context(context_doc, self._repo_path)
        messages = [ctx.system_prompt, ctx.user_message]
        search_history = []
        
        for iteration in range(1, MAX_ITERATIONS + 1):
            logger.info("Diagnosis iteration %d/%d", iteration, MAX_ITERATIONS)
            search_context = _format_search_history(search_history)
            
            decision = self._router.completion(
                messages=messages + search_context,
                response_model=SearchDecision,
            )
            
            if decision.action == "hypothesize":
                logger.info("LLM decided to produce diagnosis after %d iterations", iteration)
                return self._generate_hypotheses(messages + search_context)
            
            for search in decision.searches[:3]:  # safety limit per iteration
                result = self._execute_search(search.pattern)
                search_history.append({"pattern": search.pattern, "result": result})
        
        # Budget exhausted — force hypothesis with available data
        logger.info("Search budget exhausted, producing final diagnosis")
        full_context = messages + _format_search_history(search_history)
        return self._generate_hypotheses(full_context, exhausted=True)
    
    def _generate_hypotheses(
        self, messages: list[dict], exhausted: bool = False
    ) -> DiagnosisResult:
        extra = "Generate your top 3 hypotheses even with limited information." if exhausted else ""
        result = self._router.completion(
            messages=messages + [
                {"role": "user", "content": f"Generate top 3 ranked hypotheses with evidence. {extra}".strip()},
            ],
            response_model=DiagnosisResult,
        )
        result.iterations_used = ...  # tracked during loop
        return result
    
    def _execute_search(self, pattern: str) -> str:
        """Execute a code search in the repo."""
        from ascend_agent.tools.code_search import search_code
        import asyncio
        try:
            return asyncio.run(search_code(pattern, self._repo_path))
        except Exception as e:
            logger.warning("Search failed for '%s': %s", pattern, e)
            return f"Search failed: {e}"
```

### Model Router

```python
# Source: PROJECT.md Layer 4 + discretion area
import os
from openai import OpenAI
from pydantic import BaseModel

class ModelRouter:
    """Thin wrapper around the LLM client for diagnosis calls."""
    
    _DEFAULT_MODEL = "gpt-4o"
    
    def __init__(self, model: str | None = None, api_key: str | None = None):
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is required for diagnosis. "
                "Set the OPENAI_API_KEY environment variable."
            )
        self._client = OpenAI(api_key=api_key)
        self._model = model or os.environ.get("ASCEND_DIAGNOSIS_MODEL", self._DEFAULT_MODEL)
    
    def completion(
        self,
        messages: list[dict],
        response_model: type[BaseModel],
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> BaseModel:
        """Send messages and return structured response."""
        completion = self._client.chat.completions.parse(
            model=self._model,
            messages=messages,
            response_format=response_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return completion.choices[0].message.parsed
```

### Reading Function Body with AST

```python
# Source: Python ast module for accurate function boundary detection
# Required by D-09/D-11: read function body ±5 lines

import ast

def read_function_body(file_path: str, target_line: int, context_lines: int = 5) -> str | None:
    """Read a function body ±N lines of surrounding context.
    
    Uses Python AST to find the exact function containing target_line,
    then extracts source lines for that function's body plus context_lines
    of surrounding context above and below.
    """
    with open(file_path, "r") as f:
        source = f.read()
        lines = source.splitlines()
    
    tree = ast.parse(source)
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= target_line <= node.end_lineno:
                start = max(0, node.lineno - 1 - context_lines)
                end = min(len(lines), node.end_lineno + context_lines)
                return "\n".join(
                    f"{i + 1}:{lines[i]}"
                    for i in range(start, end)
                )
    
    # Fallback: return ±5 lines around target
    start = max(0, target_line - 1 - context_lines)
    end = min(len(lines), target_line + context_lines)
    return "\n".join(
        f"{i + 1}:{lines[i]}"
        for i in range(start, end)
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JSON mode (response_format={"type": "json_object"}) | Structured Outputs (strict JSON schema via Pydantic) | Aug 2024 (OpenAI) | JSON mode produces valid JSON but structure may vary. Structured Outputs guarantee schema adherence. The `openai` SDK `.parse()` method with Pydantic is the recommended path. |
| Custom tool/function call parsing for structured output | `.parse()` with `response_format` | OpenAI SDK 1.47+ (late 2024) | No more manual tool call extraction. The SDK handles schema conversion, response parsing, and refusal detection. |
| Use `openai.ChatCompletion.create()` then parse response | `client.chat.completions.parse()` | OpenAI SDK 2.x | Starting from 2.x, `.parse()` is the standard method for structured outputs. The `.beta` prefix has been removed. |

**Deprecated/outdated:**
- `openai.ChatCompletion.create()` (v1 SDK): Replaced by `client.chat.completions.create()` in v2. Don't import from `openai` package directly — use the client instance pattern.
- Loose JSON parsing from `response_format="json_object"`: This does not guarantee schema compliance. Use `response_format` with a Pydantic model + `.parse()` instead.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The diagnosis engine should depend on the `openai` SDK as the primary LLM client | Standard Stack | If the team uses a non-OpenAI-compatible API (e.g., Anthropic Claude directly), the SDK abstraction will need to be swapped. The ModelRouter Protocol mitigates this. |
| A2 | `client.chat.completions.parse()` handles structured output correctly with Pydantic models | Code Examples | If using Anthropic or other non-OpenAI models, `.parse()` won't work. Mitigation: ModelRouter abstraction allows swapping. |
| A3 | Python's `ast` module can accurately locate function boundaries | Code Examples | `ast` can fail on dynamically generated/compiled code, files with syntax errors, or unusual encodings. Mitigation: fallback to line-based window. |
| A4 | The `code_search` tool's interface (`search_code(pattern, path)`) is sufficient for the LLM search strategy | Architecture | The LLM may need to search with context (e.g., "find function definition of X in file Y"). If the tool doesn't support file-scoped search, the LLM may get too many results. The `code_search` tool accepts any `path`, so the engine can restrict to specific subdirectories. |
| A5 | The diagnosis engine can be synchronous (not async) inside the CLI command | Architecture | If the LLM call takes > 30 seconds (large model, many iterations), a synchronous call will block the CLI. The existing code uses `asyncio.run()` for tool calls. Consider making `Engine.diagnose()` async if latency is a concern. |

## Open Questions (RESOLVED)

1. **Which model should the Model Router use by default?**
   - RESOLVED: Default to `gpt-4o` for quality. Configure via `ASCEND_DIAGNOSIS_MODEL` env var. Document that gpt-4o-mini is an alternative for cost-sensitive or quick diagnoses. The model choice remains in the agent's discretion area.
   - What we know: gpt-4o supports structured outputs, is widely available, and has good code analysis capabilities. gpt-4o-mini is cheaper but may produce lower quality diagnosis. The model choice is in the agent's discretion area.
   - What's unclear: Whether the team has API access to specific models, whether they want a local model, and whether cost or quality is the priority.

2. **Should the `search_code` tool be called via the MCP server transport or as a direct Python function call?**
   - RESOLVED: Call `search_code` directly as an async function. No need to start the MCP server during CLI diagnosis. This keeps the architecture simple and avoids the `asyncio.run()` nesting issues that could arise from running a server and calling the tool.
   - What we know: The MCP server runs on STDIO transport. The CLI command already runs in a Python process. Calling the tool directly as an async function (`await search_code(...)`) is simpler and avoids starting a separate MCP server.
   - What's unclear: The `search_code` function is designed for MCP tool context (accepts `ctx: Context | None`). As a direct call, `ctx` would be `None`, which is already handled.

3. **How should code snippet extraction handle files outside the repo?**
   - RESOLVED: Skip frames where the file path doesn't exist in the repo. Log a warning and continue. The partial results pattern (D-04) can note this. Per D-10, the LLM decides which frames to search — it may choose to skip or pursue based on file paths.
   - What we know: Stack trace frames may reference files in site-packages, stdlib, or other non-repo paths. D-09/D-11 only specify reading scope, not what to do when the file doesn't exist in the repo.
   - What's unclear: Should the engine skip non-repo frames? Try to find the file in site-packages?

4. **How strict should the confidence score format be?**
   - RESOLVED: Use relative confidence. Instruct the LLM to assign scores such that the ranking is meaningful. Absolute calibration is a future improvement when error categorization is added (VectorDB/RAG phase).
   - What we know: D-05 requires a confidence score. D-06 requires ranking by confidence. The `Hypothesis` model uses `float 0.0-1.0`.
   - What's unclear: Should confidence be calibrated (e.g., 0.9 = "almost certain") or relative (top is always the best guess)?

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | All code | ✓ | 3.10.8 | — |
| openai SDK | LLM calls | ✗ (not installed) | — | Install via `pip install openai` |
| Pydantic 2.x | Data models | ✓ | 2.13.4 | — |
| MCP 1.x | Tool layer | ✓ | 1.27.1 | — |
| Typer/Rich | CLI | ✓ | 0.25.1 / 15.0.0 | — |
| pytest | Testing | ✓ | (via pip) | — |

**Missing dependencies with no fallback:**
- `openai` SDK — must be installed. No viable alternative for structured LLM output.

**Missing dependencies with fallback:**
- (none)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7+ with pytest-asyncio |
| Config file | `pyproject.toml` under `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIAG-01 | Engine produces DiagnosisResult with top-3 ranked hypotheses | integration | `pytest tests/test_diagnosis/test_engine.py -x` | ❌ Wave 0 |
| DIAG-01 | Engine silently reports partial results on failure (no crash) | unit | `pytest tests/test_diagnosis/test_engine.py::test_partial_failure -x` | ❌ Wave 0 |
| DIAG-02 | LLM-driven search loop executes code_search tool calls | integration | `pytest tests/test_diagnosis/test_engine.py::test_search_loop -x` | ❌ Wave 0 |
| DIAG-02 | Function body extraction reads correct scope (body ±5 lines) | unit | `pytest tests/test_diagnosis/test_engine.py::test_function_body_extraction -x` | ❌ Wave 0 |
| — | DiagnosisResult Pydantic schema validation | unit | `pytest tests/test_diagnosis/test_models.py -x` | ❌ Wave 0 |
| — | ModelRouter abstract interface + openai implementation | unit | `pytest tests/test_diagnosis/test_router.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_diagnosis/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_diagnosis/__init__.py` — package for test discovery
- [ ] `tests/test_diagnosis/conftest.py` — shared fixtures (mock LLM responses, sample traces, sample repos)
- [ ] `tests/test_diagnosis/test_models.py` — covers DiagnosisResult/Hypothesis/Evidence schema validation
- [ ] `tests/test_diagnosis/test_router.py` — covers ModelRouter abstraction and openai provider
- [ ] `tests/test_diagnosis/test_engine.py` — covers search loop, partial failure, function body extraction
- [ ] Framework install: `pip install openai` — if not already present
- [ ] Framework install: `pip install pytest pytest-asyncio` — if not already present

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | API key via env var (OPENAI_API_KEY) — never hardcoded or logged |
| V5 Input Validation | yes | Repo path validation to prevent directory traversal. Code search pattern validation (reject too-broad patterns). |
| V6 Cryptography | no | No encryption — API key transmitted over TLS by SDK |
| V8 Data Protection | yes | Stack trace content may contain sensitive info — don't log raw traces at INFO level (use DEBUG with explicit opt-in) |
| V20 API Security | yes | OpenAI API key management — standard env var pattern, no key rotation needed for CLI tool |

### Known Threat Patterns for Python/OpenAI Stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key leakage in logs | Information Disclosure | Filter `Authorization` header from log output. Sanitize `openai` SDK error messages before logging. |
| Prompt injection via stack trace | Spoofing | Stack traces are user-provided input. The system prompt should assert authority: "You are a Python debugging expert. Analyze the following stack trace..." The LLM output is constrained by `response_format` Pydantic schema. |
| Directory traversal in repo path | Tampering | Validate `repo_path` resolves within expected directory. The `RepoScanner` already uses `pathlib.Path.resolve()`. |
| Broad regex pattern DoS in code_search | Denial of Service | The `search_code` tool has a 30-second timeout. Engine should validate patterns are not overly broad (e.g., reject patterns matching everything). |

### API Key Handling
- Store in environment variable: `OPENAI_API_KEY`
- Optional model selection: `ASCEND_DIAGNOSIS_MODEL` (default: `gpt-4o`)
- The `ModelRouter` validates the key exists at construction time, before any LLM call
- Never log the key value — log `"OpenAI client initialized (model: ...)"` instead
- Never serialize the key into DiagnosisResult or any output

## Sources

### Primary (HIGH confidence)
- **OpenAI SDK documentation** — structured outputs, `.parse()` method, Pydantic integration [CITED: developers.openai.com/api/docs/guides/structured-outputs]
- **OpenAI SDK helpers README** — `parse()` usage with Pydantic models [CITED: github.com/openai/openai-python/blob/main/helpers.md]
- **PyPI registry** — openai 2.37.0, pydantic 2.13.4, mcp 1.27.1, typer 0.25.1 [VERIFIED: pip index versions]
- **slopcheck** — all packages validated [OK] [VERIFIED: slopcheck install]
- **Project code (Phase 1)** — ContextDocument, TraceParser, code_search tool, CLI patterns [VERIFIED: codebase grep]

### Secondary (MEDIUM confidence)
- **G-Research code review LLM patterns** — validates separate recall/precision prompts, Pydantic cross-validation pattern [CITED: gresearch.com/news/building-a-code-review-tool]
- **OpenAI Structured Outputs introduction** — confirms recommended pattern of Pydantic models with `.parse()` [CITED: openai.com/index/introducing-structured-outputs-in-the-api]

### Tertiary (LOW confidence)
- **LLM-driven code analysis research** — general pattern of iterative LLM refinement loops [ASSUMED: training knowledge]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — LLM client SDK choice is well-established for structured outputs
- Architecture: MEDIUM — loop design matches locked decisions but hasn't been tested on real diagnostics
- Pitfalls: MEDIUM — based on documented LLM integration patterns, not specific to this codebase

**Research date:** 2026-05-21
**Valid until:** 2026-06-21 (openai SDK may have minor version bumps; structured output pattern is stable)
