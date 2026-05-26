# Requirements: Ascend Diagnostic Agent

**Defined:** 2026-05-25
**Core Value:** Enable the Ascend maintenance team to diagnose and fix production issues 10x faster by automating the investigation, reproduction, and verification loop.

**Milestone:** v1.1 Multi-Provider & Multi-Repo

## v1 Requirements

### Provider Routing

- [ ] **PROV-01**: ModelRouter supports OpenAI-compatible `base_url` override via env var `ASCEND_OPENAI_BASE_URL`
- [ ] **PROV-02**: ModelRouter supports per-provider API key via `ASCEND_*_API_KEY` pattern
- [ ] **PROV-03**: Provider config can be specified per CLI command via `--provider` flag
- [ ] **PROV-04**: All existing providers fall back to `OPENAI_API_KEY` when provider-specific key is unset

### Chinese Models

- [ ] **CHN-01**: DeepSeek integration (OpenAI-compatible API at `api.deepseek.com`)
- [ ] **CHN-02**: Qwen integration via DashScope (OpenAI-compatible API at `dashscope.aliyuncs.com`)
- [ ] **CHN-03**: Chinese models configurable via `ASCEND_DIAGNOSIS_MODEL`, `ASCEND_FIX_MODEL` etc.
- [ ] **CHN-04**: Structured output support for Chinese models (`.parse()` via OpenAI-compat)

### Multi-Repo

- [ ] **REPO-01**: CLI `--repo` flag on `diagnose`, `fix`, `reproduce`, `verify` commands
- [ ] **REPO-02**: `ASCEND_TARGET_REPO` env var as default repo override
- [ ] **REPO-03**: `Settings.target_repos` field (list) for multiple repo configuration
- [ ] **REPO-04**: All existing commands work with `--repo` without breaking existing behavior

### Testing

- [ ] **TEST-01**: Provider routing tests with mocked OpenAI-compatible endpoints
- [ ] **TEST-02**: DeepSeek integration tests (mocked)
- [ ] **TEST-03**: Qwen integration tests (mocked)
- [ ] **TEST-04**: Multi-repo CLI tests (`--repo` flag behavior)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Provider Expansion

- **PROV-05**: Anthropic Claude backend via anthropic SDK
- **PROV-06**: Google Gemini backend via google-genai SDK
- **PROV-07**: Ollama local model backend via HTTP API

### Cost Optimization

- **COST-01**: Per-task model routing via config file
- **COST-02**: Task-tiered model selection (cheap vs capable)
- **COST-03**: Token usage tracking and cost estimates

## Out of Scope

| Feature | Reason |
|---------|--------|
| Non-OpenAI-compatible providers (Claude, Gemini, Ollama) | Deferred to v1.2 — scoped to OpenAI-compat only for v1.1 |
| Provider-native structured outputs for non-OpenAI | Deferred — OpenAI-compat `.parse()` sufficient for Qwen/DeepSeek |
| Multi-repo parallel execution | Deferred — --repo flag switches target, doesn't run in parallel |
| Provider benchmarking | Not required for v1.1 scope |
| Cross-repo analysis | Out of scope — repo-per-operation only |

---

*Requirements defined: 2026-05-25*
*Last updated: 2026-05-25 after initial definition*
