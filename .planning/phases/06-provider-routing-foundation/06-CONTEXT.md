# Phase 6: Provider Routing Foundation - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend ModelRouter to support multiple OpenAI-compatible LLM providers via environment-variable configuration. This is the foundation phase for v1.1 Multi-Provider — it adds the routing infrastructure (provider config model, env var resolution, factory pattern, `--provider` CLI flag) without adding specific Chinese model integrations (those are Phase 7).

**Requirements (from REQUIREMENTS.md):**
- PROV-01: ModelRouter supports OpenAI-compatible `base_url` override via env var `ASCEND_OPENAI_BASE_URL`
- PROV-02: ModelRouter supports per-provider API key via `ASCEND_*_API_KEY` pattern
- PROV-03: Provider config can be specified per CLI command via `--provider` flag
- PROV-04: All existing providers fall back to `OPENAI_API_KEY` when provider-specific key is unset

**Success criteria from roadmap:**
1. ModelRouter works with OpenAI-compatible base_url override
2. Per-provider API key configuration via env vars
3. Provider selection via CLI `--provider` flag
4. Backward compatible with existing `OPENAI_API_KEY` usage

</domain>

<decisions>
## Implementation Decisions

### Provider Config Model
- **D-01:** Define a `ProviderConfig` Pydantic model with fields: `base_url` (str), `api_key` (str), `default_model` (str). A single `ProviderConfig` instance is resolved per provider.
- **D-02:** Named per-provider config instances loaded from env vars at construction time. Mapping is: provider name → env var prefix (e.g., "openai" → `ASCEND_OPENAI_*`, "deepseek" → `ASCEND_DEEPSEEK_*`).

### Provider Flag Scope
- **D-03:** Two-level `--provider` flag: root `ascend-agent --provider deepseek run` sets the default; per-command `ascend-agent diagnose run --provider deepseek` overrides the root default for that command.
- **D-04:** When `--provider` is set, it completely overrides per-engine model env vars (`ASCEND_DIAGNOSIS_MODEL`, `ASCEND_FIX_MODEL`). Provider's `default_model` from its `ProviderConfig` is used instead.

### ModelRouter API
- **D-05:** Introduce a factory function `create_router(provider: str = "openai") -> ModelRouter` in `router.py`. It reads env vars to build the `ProviderConfig`, then constructs a `ModelRouter` with that config internally.
- **D-06:** `ModelRouter.__init__` accepts a `ProviderConfig` internally. The existing keyword-arg constructor (`model`, `api_key`) is preserved but deprecated — all new code uses `create_router`.
- **D-07:** `create_router` does NOT accept per-engine model overrides. Engines pass the `--provider` value directly.

### API Key & Fallback
- **D-08:** Default "openai" provider checks `ASCEND_OPENAI_API_KEY` first, then falls back to `OPENAI_API_KEY`. This preserves backward compatibility with existing deployments.
- **D-09:** Non-openai providers (e.g., deepseek) require their specific key env var (`ASCEND_DEEPSEEK_API_KEY`). If unset, raise a `ValueError` with the provider name in the message. No silent credential fallback.
- **D-10:** Base URL follows per-provider pattern: `ASCEND_OPENAI_BASE_URL`, `ASCEND_DEEPSEEK_BASE_URL`, etc. Each provider's `base_url` is resolved independently.

### Config Storage
- **D-11:** Add provider configuration fields to the `Settings` class (in `config.py`) following the existing `ASCEND_` env prefix convention. New fields: `openai_api_key`, `openai_base_url`, etc., populated from `ASCEND_OPENAI_API_KEY`, `ASCEND_OPENAI_BASE_URL` env vars. Other provider fields added in Phase 7.

### The Agent's Discretion
- Exact `ProviderConfig` Pydantic model schema (field types, defaults, validation).
- `create_router` factory implementation details (env var resolution logic, error message format).
- How the two-level `--provider` flag is wired in the Typer CLI (root callback + per-command option).
- `ModelRouter` internal changes to use `base_url` from `ProviderConfig` when constructing the OpenAI client.
- What `Settings` provider fields look like exactly (field names, env var names, defaults).
- Test approach and coverage targets for provider routing.
- Whether `create_router` caches `ProviderConfig` instances or re-resolves on each call.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Definition
- `.planning/PROJECT.md` — Project vision, architecture layers (ModelRouter layer), constraints (v1.1 goal for multi-provider)
- `.planning/REQUIREMENTS.md` — PROV-01 through PROV-04 requirements with full traceability table
- `.planning/ROADMAP.md` — Phase 6 goal, success criteria, v1.1 milestone context (Phase 7 consumes provider infrastructure)

### Phase 6 Integration Points
- `src/ascend_agent/diagnosis/router.py` — Current ModelRouter (60 lines, hardcoded to OpenAI). Target for factory function and ProviderConfig integration.
- `src/ascend_agent/config.py` — Settings class with `ASCEND_` env prefix. Target for provider config fields (D-11).
- `src/ascend_agent/cli/app.py` — Root Typer app. Target for global `--provider` flag (D-03).
- `src/ascend_agent/cli/diagnose.py` — `ModelRouter()` constructed inline at line 76. Must use `create_router()`.
- `src/ascend_agent/cli/fix.py` — `ModelRouter(model=os.environ.get("ASCEND_FIX_MODEL"))` at line 53. Must use `create_router()`.
- `src/ascend_agent/diagnosis/engine.py` — Engine constructor takes `router: ModelRouter` (line 169). No API change needed.
- `src/ascend_agent/diagnosis/fix_engine.py` — FixEngine constructor takes `router: ModelRouter` (line 97). No API change needed.
- `src/ascend_agent/reproduction/engine.py` — ReproductionEngine constructor takes `router: ModelRouter` (line 32). No API change needed.
- `src/ascend_agent/verification/engine.py` — VerificationEngine constructor takes `router: ModelRouter` (line 34). No API change needed.

### Phase 1-5 Patterns (Consumed by Phase 6)
- `.planning/phases/02-diagnosis-engine/02-CONTEXT.md` — Engine pattern, ModelRouter concrete class decision (not Protocol)
- `src/ascend_agent/diagnosis/router.py` — Current ModelRouter implementation (concrete class, OpenAI client, `.parse()` for structured outputs)
- `src/ascend_agent/config.py` — Settings class pattern (pydantic-settings, `ASCEND_` env prefix)

### Phase 7 (Downstream Consumer of Phase 6)
- `.planning/REQUIREMENTS.md` §Chinese Models — CHN-01 through CHN-04 (DeepSeek, Qwen integration). Phase 6 provider infrastructure must support these.

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ModelRouter` (`src/ascend_agent/diagnosis/router.py`) — 60-line concrete class wrapping OpenAI client with `.parse()` structured outputs. Core target for Phase 6 changes.
- `Settings` class (`src/ascend_agent/config.py`) — pydantic-settings with `ASCEND_` env prefix. Pattern for adding provider config fields.
- Engine pattern (Engine, FixEngine, ReproductionEngine, VerificationEngine) — all accept `router: ModelRouter` in constructor. No downstream changes needed if `create_router()` returns `ModelRouter`.

### Established Patterns
- Pydantic v2 models with `ConfigDict(extra="forbid")` across all phases
- Typer CLI with subcommands and `app.add_typer()` registration (for adding root `--provider` flag)
- Env-var configuration via `ASCEND_` prefix (SSH: `ASCEND_SSH_HOST`, `ASCEND_SSH_USER`; models: `ASCEND_DIAGNOSIS_MODEL`, `ASCEND_FIX_MODEL`)
- Engine pattern: constructor(router, repo_path) → public method → structured Pydantic result

### Integration Points
- `router.py` constructor and `completion()` method — the only file with direct OpenAI SDK import. All provider routing logic must be scoped here.
- `config.py` — add provider fields (api_key, base_url) per D-11, following existing `ASCEND_` convention.
- `app.py` — root Typer app gets `--provider` option (D-03), passed through CLI commands.
- `diagnose.py` line 76, `fix.py` line 53 — replace inline `ModelRouter()` construction with `create_router()` calls.
- All 4 engines accept `router` as constructor param — no structural changes needed to engine code itself.

</code_context>

<specifics>
## Specific Ideas

- The factory function approach (`create_router`) was chosen to keep `ModelRouter.__init__` simple and avoid constructor bloat. Engines don't need to know about providers — they just get a configured `ModelRouter`.
- Two-level `--provider` flag follows Typer's `@app.callback()` convention for root-level options, with per-command override via standard Typer `Option()`.
- Env-var-only configuration matches the existing project pattern (no config file). Extending `Settings` class keeps env var resolution consistent with existing fields.
- The default "openai" provider fallback (`OPENAI_API_KEY`) preserves all existing user workflows and Docker/config setups.

</specifics>

<deferred>
## Deferred Ideas

- **Config file for provider routing** — Could add a provider config file (YAML/TOML) for complex setups. Deferred — env vars cover v1.1 needs.
- **Per-engine model override within provider** — e.g., "use DeepSeek but with gpt-4o for diagnosis". Deferred — provider's default_model covers initial use.
- **Provider credential caching** — Re-resolving env vars on each `create_router()` call is simple but repetitive. Deferred until performance matters.
- **Multiple active providers** — Running diagnose with one provider and fix with another in the same session. Deferred — single provider per session for v1.1.
- **Non-OpenAI-compatible providers (Claude, Gemini, Ollama)** — Explicitly out of scope for v1.1 per REQUIREMENTS.md. Deferred to v1.2.
None — discussion stayed within phase scope.

</deferred>

---

*Phase: 6-Provider Routing Foundation*
*Context gathered: 2026-05-26*
