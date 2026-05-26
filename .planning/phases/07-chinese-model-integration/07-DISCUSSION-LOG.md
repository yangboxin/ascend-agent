# Phase 7: Chinese Model Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 7-chinese-model-integration
**Areas discussed:** DeepSeek model config & defaults, Qwen model config & defaults

---

## DeepSeek Model Config & Defaults

| Option | Description | Selected |
|--------|-------------|----------|
| deepseek-chat | Latest general-purpose chat model (recommended by DeepSeek for most use cases) | |
| deepseek-coder | Specialized for code generation — relevant for fix engine | |
| deepseek-reasoner | DeepSeek-R1 reasoning model — better for diagnosis but slower/expensive | |
| deepseek-v4-flash | Fast, cost-effective default (user-specified) | ✓ |
| deepseek-v4-pro | More capable reasoning model (user-specified alternative) | |

**User's choice:** `deepseek-v4-flash` as primary default, `deepseek-v4-pro` also available

**Structured output:**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, fully compatible | .parse() works — no fallback needed | |
| Partial / needs testing | Use it, but have a json.loads fallback for non-OpenAI-compat modes | ✓ |
| No, use manual parsing | Use .choices[0].message.content + json.loads fallback always | |

**User's choice:** Partial — try .parse() first, fall back to json.loads

---

## Qwen Model Config & Defaults

| Option | Description | Selected |
|--------|-------------|----------|
| qwen-turbo | Fast, cost-effective for simpler tasks | ✓ |
| qwen-plus | Balanced capability/speed — general purpose | |
| qwen-max | Most capable Qwen model — complex reasoning | |
| qwen2.5-72b-instruct | Specific Qwen 2.5 72B instruct model | |

**User's choice:** `qwen-turbo`

**Structured output:**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, fully compatible | .parse() works with OpenAI-compat mode | |
| Partial / needs testing | Use it, but have json.loads fallback | ✓ |
| No, use manual parsing | Always use .choices[0].message.content + json.loads | |

**User's choice:** Partial — same fallback strategy as DeepSeek

---

## The Agent's Discretion

- Exact `ProviderConfig` model schema — follow Phase 6 pattern (no changes needed)
- Test coverage targets — follow existing `test_router.py` mock patterns
- Whether to include per-engine model overrides (`ASCEND_DEEPSEEK_DIAGNOSIS_MODEL`) — start with just `default_model` env var, add per-engine if requested
- Whether `create_router` caches `ProviderConfig` instances — re-resolve per call (current behavior)

## Deferred Ideas

- Per-engine model overrides for Chinese providers — possible Phase 9 enhancement
- Provider credential caching — deferred until performance matters
