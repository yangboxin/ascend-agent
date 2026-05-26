# Phase 7: Chinese Model Integration - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Integrate DeepSeek and Qwen as selectable `--provider` targets via the existing `create_router()` infrastructure from Phase 6. Both providers use OpenAI-compatible APIs and follow the `ASCEND_{PROVIDER}_*` env var pattern for configuration.

**Requirements (from REQUIREMENTS.md):**
- CHN-01: DeepSeek integration (OpenAI-compatible API at `api.deepseek.com`)
- CHN-02: Qwen integration via DashScope (OpenAI-compatible API at `dashscope.aliyuncs.com`)
- CHN-03: Chinese models configurable via `ASCEND_DIAGNOSIS_MODEL`, `ASCEND_FIX_MODEL` etc.
- CHN-04: Structured output support for Chinese models (`.parse()` via OpenAI-compat)

**Success criteria from roadmap:**
1. `ascend-agent --provider deepseek diagnose run` works with DeepSeek backend
2. `ascend-agent --provider qwen diagnose run` works with Qwen backend
3. Per-provider API key and base URL configurable via env vars
4. Structured output works or gracefully falls back

</domain>

<decisions>
## Implementation Decisions

### DeepSeek Integration
- **D-01:** Default model is `deepseek-v4-flash` as the general-purpose fast option (configurable via `ASCEND_DEEPSEEK_DEFAULT_MODEL` env var). `deepseek-v4-pro` is also available for more capable reasoning tasks.
- **D-02:** DeepSeek structured output support is partial — use OpenAI-compatible `.parse()` with a fallback to `json.loads` on `choices[0].message.content` when `.parse()` is not supported.
- **D-03:** Base URL: `https://api.deepseek.com/v1` (configurable via `ASCEND_DEEPSEEK_BASE_URL`).
- **D-04:** API key via `ASCEND_DEEPSEEK_API_KEY` (no silent fallback per D-09 from Phase 6).

### Qwen Integration
- **D-05:** Default model is `qwen-turbo` for general-purpose use (configurable via `ASCEND_QWEN_DEFAULT_MODEL` env var).
- **D-06:** Qwen structured output support is partial — same strategy as DeepSeek: try `.parse()`, fall back to `json.loads` on message content.
- **D-07:** Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1` (configurable via `ASCEND_QWEN_BASE_URL`). Qwen DashScope requires the `/compatible-mode/v1` path suffix for OpenAI-compatible access.
- **D-08:** API key via `ASCEND_QWEN_API_KEY` (DashScope API key, no silent fallback).

### Structured Output Fallback Strategy
- **D-09:** For both providers, attempt `.parse()` first with `response_format`. If the provider does not support it (raises an error or returns unparsed content), fall back to `json.loads()` on `choices[0].message.content`. The fallback is transparent to callers — the `completion()` method on `ModelRouter` continues returning the same Pydantic model type.
- **D-10:** Detection heuristic: if `.parse()` raises `openai.APIStatusError` or `openai.BadRequestError` with status 400, catch it and retry as a regular chat completion with system prompt requesting JSON output.

### Provider Config Storage
- **D-11:** Follow Phase 6 D-11 pattern: add `deepseek_api_key`, `deepseek_base_url`, `deepseek_default_model`, `qwen_api_key`, `qwen_base_url`, `qwen_default_model` to the `Settings` class in `config.py`. Populated from `ASCEND_DEEPSEEK_*` and `ASCEND_QWEN_*` env vars respectively.
- **D-12:** Per-engine model env vars (`ASCEND_DIAGNOSIS_MODEL`, `ASCEND_FIX_MODEL`, etc.) are separate from provider-specific `default_model`. The `--provider` flag uses the provider's `default_model`. Per-engine overrides (`ASCEND_DEEPSEEK_DIAGNOSIS_MODEL`, `ASCEND_DEEPSEEK_FIX_MODEL`) are discussed but not decided — the agent should implement `ASCEND_DEEPSEEK_DEFAULT_MODEL` as the single model config point and add per-engine overrides as a Phase 9 enhancement if needed.

### The Agent's Discretion
- Whether `create_router` caches `ProviderConfig` instances or re-resolves on each call (follow Phase 6 discretion — re-resolve per call is simpler and matches current behavior).
- Exact error message format for missing API keys (follow existing pattern from Phase 4/6).
- Test coverage targets for provider-specific tests.
- Whether to add `ASCEND_DEEPSEEK_DIAGNOSIS_MODEL` style per-engine overrides alongside `ASCEND_DEEPSEEK_DEFAULT_MODEL` — start with just the default model env var, add per-engine if the user requests it.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Definition
- `.planning/PROJECT.md` — Project vision, architecture layers, constraints (v1.1 multi-provider goal)
- `.planning/REQUIREMENTS.md` — CHN-01 through CHN-04 requirements with full traceability table
- `.planning/ROADMAP.md` — Phase 7 goal, success criteria, v1.1 milestone context

### Phase 6 (Provider Infrastructure — Phase 7 depends on this)
- `.planning/phases/06-provider-routing-foundation/06-CONTEXT.md` — All provider routing decisions (D-01 through D-11), factory pattern, env var convention, two-level --provider flag
- `src/ascend_agent/diagnosis/router.py` — ProviderConfig model, create_router() factory, ModelRouter with base_url support
- `src/ascend_agent/config.py` — Settings class with `ASCEND_` env prefix, pattern for adding provider fields
- `src/ascend_agent/cli/app.py` — Root --provider flag wiring via callback
- `tests/test_diagnosis/test_router.py` — Existing test patterns for create_router with mocked OpenAI client

### Phase 2-5 Patterns (Consumed by Phase 7)
- `.planning/phases/02-diagnosis-engine/02-CONTEXT.md` — Engine pattern, ModelRouter concrete class, .parse() structured output
- `tests/test_diagnosis/test_router.py` — Mock-based test patterns for provider tests

### External References
- DeepSeek API docs: `https://api-docs.deepseek.com/` — OpenAI compatibility reference, available models
- Qwen DashScope docs: `https://help.aliyun.com/zh/model-studio/getting-started/models` — OpenAI-compat mode setup

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `create_router()` factory (`src/ascend_agent/diagnosis/router.py`) — Accepts any provider name, resolves `ASCEND_{PROVIDER}_*` env vars, constructs `ModelRouter` with `ProviderConfig`. Adding DeepSeek and Qwen means these providers will work without changing any engine or CLI code.
- `ModelRouter` with `config: ProviderConfig` path (`src/ascend_agent/diagnosis/router.py`) — Already supports arbitrary `base_url`, `api_key`, and `default_model`. No changes needed to ModelRouter itself.
- `Settings` class (`src/ascend_agent/config.py`) — pydantic-settings with `ASCEND_` env prefix. Add new provider fields following the `openai_api_key` / `openai_base_url` pattern.

### Established Patterns
- Per-provider env var prefix: `ASCEND_{PROVIDER}_API_KEY`, `ASCEND_{PROVIDER}_BASE_URL`, `ASCEND_{PROVIDER}_DEFAULT_MODEL`
- Non-openai providers require specific key env var — no silent fallback to OPENAI_API_KEY (D-09 from Phase 6)
- OpenAI-compatible APIs only — non-OpenAI-compatible providers (Claude, Gemini, Ollama) are v1.2
- Env-var-only configuration (no config file) — deferred to future milestone
- Engine pattern: all 4 engines accept `router: ModelRouter` — provider changes are invisible to engines

### Integration Points
- `src/ascend_agent/diagnosis/router.py` — Add `create_router` logic for "deepseek" and "qwen" provider names (already handled generically via `ASCEND_{PROVIDER}_*` pattern — may need provider-specific defaults for base_url)
- `src/ascend_agent/config.py` — Add `deepseek_api_key`, `deepseek_base_url`, `deepseek_default_model`, `qwen_api_key`, `qwen_base_url`, `qwen_default_model` fields
- `tests/test_diagnosis/test_router.py` — Add `test_create_router_deepseek()`, `test_create_router_qwen()`, missing key tests
- No changes needed to CLI files, engine files, or MCP tools — provider selection is entirely through `create_router()`

</code_context>

<specifics>
## Specific Ideas

- DeepSeek default model: `deepseek-v4-flash` (fast default, can be overridden to `deepseek-v4-pro` via env var)
- Qwen default model: `qwen-turbo` (balanced speed/capability)
- Both providers use partial .parse() support with transparent json.loads fallback on 400 errors
- Follow existing `test_router.py` mock patterns: monkeypatch env vars, mock `openai.OpenAI.__init__`, verify `ModelRouter` construction with correct config

</specifics>

<deferred>
## Deferred Ideas

- **Per-engine model overrides for Chinese providers** — e.g., `ASCEND_DEEPSEEK_DIAGNOSIS_MODEL` overriding the provider default for specific engines. The agent should implement the single `ASCEND_DEEPSEEK_DEFAULT_MODEL` pattern and add per-engine overrides as a Phase 9 enhancement if requested.
- **Provider credential caching** — Re-resolving env vars on each `create_router()` call is simple but repetitive. Deferred until performance matters.
- **Config file for provider routing** — Could add a provider config file (YAML/TOML) for complex setups. Deferred — env vars cover v1.1 needs.
- **Non-OpenAI-compatible providers (Claude, Gemini, Ollama)** — Explicitly out of scope for v1.1 per REQUIREMENTS.md. Deferred to v1.2.

</deferred>

---

*Phase: 7-chinese-model-integration*
*Context gathered: 2026-05-26*
