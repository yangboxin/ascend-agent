# Pitfalls Research — v1.1 Multi-Provider & Multi-Repo

## Pitfall 1: OpenAI-Compatible API Inconsistencies

**Issue:** DeepSeek and Qwen claim OpenAI compatibility but differ in:
- Structured output support (DeepSeek: `.parse()` works with `response_format`; Qwen: requires `result_format="message"`)
- Rate limits and error response shapes
- Token counting (different tokenizers → different context windows)

**Mitigation:** Add provider-specific response parsing per backend. Test each provider independently.

## Pitfall 2: Ollama Structured Outputs

**Issue:** Ollama's structured outputs use JSON schema in `format` param, not OpenAI's `response_format`. Pydantic model → JSON schema conversion needed (can use `model.model_json_schema()`).

**Mitigation:** Build a `pydantic_to_json_schema()` utility. Test with `llama3.1:8b` (best structured output support).

## Pitfall 3: Anthropic API Differences

**Issue:** Anthropic Messages API uses different message format:
- `content` is a list of content blocks, not a string
- No native `.parse()` equivalent (use `anthropic.beta.messages` with `tool_use`)
- Tool use pattern required for structured outputs

**Mitigation:** Use Anthropic's `tool_use` beta feature for structured outputs. Wrap in provider backend.

## Pitfall 4: Multi-Repo Scope Creep

**Issue:** "Multi-repo" could mean many things: parallel targeting, repo switching, cross-repo analysis. Scope grows fast.

**Mitigation:** v1.1 multi-repo = `--repo` flag + env var + Settings field. No cross-repo analysis, no parallel targeting. Simple.

## Pitfall 5: API Key Management Complexity

**Issue:** Each provider needs its own API key. Environment variables proliferate.

**Mitigation:** Prefix convention: `ASCEND_ANTHROPIC_API_KEY`, `ASCEND_GEMINI_API_KEY`, `ASCEND_DEEPSEEK_API_KEY`, `ASCEND_QWEN_API_KEY`. All optional. Config file as secondary source.

**Which phase should address each:** All in the provider refactoring phase (Phase 6).
