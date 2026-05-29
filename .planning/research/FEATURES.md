# Features Research — v1.1 Multi-Provider & Multi-Repo

## Feature Categories

### Provider Abstraction (table stakes)
- Unified interface for all LLM providers
- Per-provider API key management
- Provider-specific configuration (base_url, model names, timeouts)
- Model fallback / retry logic across providers

### Cost-Optimized Routing (differentiator)
- Per-task model tiering: cheap models for simple tasks, capable for complex
- Configurable routing via env vars AND config file
- Auto cost tracking / budget awareness
- Task categories: diagnosis (reasoning), fix generation (precision), test verification (deterministic → cheap)

### Multi-Repo Support (table stakes)
- CLI `--repo` flag to target specific repository
- `ASCEND_TARGET_REPO` env var override
- Per-repo settings (path, SSH config, test timeout)

### Chinese Model Support (table stakes)
- Qwen via DashScope (OpenAI-compatible API)
- DeepSeek via DeepSeek API (OpenAI-compatible)
- Both reuse existing OpenAI SDK with different base_url

## Anti-Features (explicitly NOT building)
- Unified model ranking / benchmarking — out of scope
- Automatic model switching based on latency — deferred
- Provider usage quotas / rate limiting — future
- Multi-model parallel execution — deferred

## Dependencies on Existing Architecture
- ModelRouter is the single integration point — refactor to provider-agnostic interface
- CLI commands need `--repo` flag pattern
- All existing Engine classes accept `router` param — compatible with new ModelRouter
- Settings class needs API keys for new providers
