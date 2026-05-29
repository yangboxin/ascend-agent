# Stack Research — v1.1 Multi-Provider & Multi-Repo

## Provider SDKs

| Provider | SDK | Python Package | Structured Outputs | Notes |
|----------|-----|---------------|-------------------|-------|
| OpenAI (existing) | `openai` >=1.0 | openai | `.parse()` with Pydantic | Already implemented |
| Anthropic Claude | `anthropic` | anthropic | `anthropic/types.py` — beta structured outputs | Needs `anthropic[bedrock]` for AWS |
| Google Gemini | `google-genai` | google-genai | `response_schema` param | Supports Pydantic via `genai.types` |
| Ollama (local) | HTTP API only | requests or ollama-py | JSON schema in `format` param | No official Python SDK needed |
| DeepSeek | OpenAI-compat | openai (base_url) | `.parse()` via OpenAI compat | Drop-in OpenAI SDK with `base_url="https://api.deepseek.com"` |
| Qwen (DashScope) | OpenAI-compat | openai (base_url) | `.parse()` via OpenAI compat | Drop-in OpenAI SDK with `base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"` |

## Key Integration Pattern

All non-OpenAI providers use either:
1. **OpenAI-compatible API** (DeepSeek, Qwen) — reuse existing OpenAI SDK with different `base_url` and `api_key`
2. **Dedicated SDK** (Anthropic, Google Gemini, Ollama) — separate client class per provider

## Multi-Repo Pattern

- Existing `repo_path` in Settings is a single string
- Multi-repo: change to list or add `target_repos` field
- CLI commands need `--repo` flag or `ASCEND_TARGET_REPO` env var
- Verification/Reproduction engines need explicit repo path per operation

## Version Constraints
- `anthropic>=0.30.0` for Messages API
- `google-genai>=1.0.0` for Gemini
- No new deps for DeepSeek/Qwen (reuse OpenAI SDK)
- `ollama` HTTP API — no SDK dependency, just requests (already in deps)
