# Phase 6: Provider Routing Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 6-Provider Routing Foundation
**Areas discussed:** Provider Config Model, Provider Flag Scope, ModelRouter API Changes, Model Routing Strategy, Config vs Env Vars Balance

---

## Provider Config Model

| Option | Description | Selected |
|--------|-------------|----------|
| Simple ProviderKey enum | Just a string key. ModelRouter resolves env vars internally. Minimalist. | |
| ProviderConfig Pydantic model | Pydantic model with base_url, api_key, model fields. One per provider. Structured. | ✓ |
| Settings fields on ModelRouter | Add base_url and api_key directly as constructor params. Keep it simple. | |

**Follow-up: Per-provider named config vs Flat config per request**

| Option | Description | Selected |
|--------|-------------|----------|
| Per-provider named config | Explicit model per provider, each loaded from env vars. | ✓ |
| Flat config per request | Single ProviderConfig rebuilt per request based on active provider name. | |

**User's choice:** ProviderConfig Pydantic model, per-provider named config instances loaded from env vars.

---

## Provider Flag Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Global root flag | Single --provider on ascend-agent root, applied to all commands. | |
| Per-subcommand flag | Each run command gets its own --provider flag. | |
| Both levels | Root sets default, per-command overrides. | ✓ |

**Follow-up: Interaction with ASCEND_DIAGNOSIS_MODEL etc.**

| Option | Description | Selected |
|--------|-------------|----------|
| Provider wins completely | --provider overrides per-engine model env vars. Use provider's default model. | ✓ |
| Model env var overrides provider default | ASCEND_DIAGNOSIS_MODEL still takes priority within the chosen provider. | |

**User's choice:** Both levels (root default + per-command override). Provider completely overrides per-engine model env vars.

---

## ModelRouter API Changes

| Option | Description | Selected |
|--------|-------------|----------|
| Factory function approach | create_router(provider='openai') builds ModelRouter with right ProviderConfig. | ✓ |
| Add provider param to constructor | ModelRouter(provider='openai'). Reads env vars internally. | |
| ProviderConfig injected directly | ModelRouter(config=ProviderConfig(...)). Caller resolves provider first. | |

**Follow-up: Where factory lives and engine overrides?**

| Option | Description | Selected |
|--------|-------------|----------|
| Router module, no engine overrides | create_router in router.py. Provider default model used always. | ✓ |
| Router module + model override param | create_router accepts model_override for per-engine customization. | |

**User's choice:** Factory function `create_router(provider='openai')` in `router.py`. No per-engine model override param.

---

## Model Routing Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Fail with clear error | If provider-specific API key unset, raise ValueError with provider name. | ✓ |
| Fallback to openai provider | Auto-fallback to openai provider if key unset. Transparent. | |
| Fallback key only, not provider | Use OPENAI_API_KEY as credential for the requested provider. | |

**Follow-up: Backward compatibility for default openai provider**

| Option | Description | Selected |
|--------|-------------|----------|
| ASCEND_OPENAI_API_KEY or OPENAI_API_KEY | Both work for default provider. ASCEND_* checked first. ✓ | |
| OPENAI_API_KEY only for default | Default openai uses OPENAI_API_KEY directly. | |

**User's choice:** Non-openai providers fail with clear error if specific key missing. Default "openai" checks ASCEND_OPENAI_API_KEY first, then OPENAI_API_KEY for backward compat.

---

## Config vs Env Vars Balance

| Option | Description | Selected |
|--------|-------------|----------|
| Pure env vars in ModelRouter | No Settings changes. ModelRouter reads env vars directly. | |
| Add to Settings class | Add provider fields to Settings. Consistent with existing pattern. | ✓ |

**Follow-up: Env var naming pattern**

| Option | Description | Selected |
|--------|-------------|----------|
| ASCEND_*_API_KEY per provider | ASCEND_OPENAI_API_KEY, ASCEND_DEEPSEEK_API_KEY etc. | ✓ |
| ASCEND_PROVIDER_* names | ASCEND_PROVIDER_OPENAI_KEY etc. Namespaced. | |

**Follow-up: Base URL naming pattern**

| Option | Description | Selected |
|--------|-------------|----------|
| ASCEND_*_BASE_URL per provider | ASCEND_OPENAI_BASE_URL, ASCEND_DEEPSEEK_BASE_URL. ✓ | |
| Single generic override | ASCEND_OPENAI_BASE_URL applies to whatever provider is active. | |

**User's choice:** Add provider fields to Settings class. `ASCEND_*_API_KEY` and `ASCEND_*_BASE_URL` per provider.

---

## The Agent's Discretion

- Exact ProviderConfig Pydantic model schema (field types, defaults, validation)
- create_router implementation details (env var resolution, error messages)
- How two-level --provider flag is wired in Typer CLI (root callback + per-command)
- ModelRouter internal changes for base_url usage
- Settings provider field definitions (field names, env mappings, defaults)
- Test approach and coverage targets
- Whether create_router caches ProviderConfig instances or re-resolves per call

## Deferred Ideas

- Config file for provider routing — Deferred (env vars cover v1.1)
- Per-engine model override within provider — Deferred (provider default model sufficient)
- Provider credential caching — Deferred until performance matters
- Multiple active providers in one session — Deferred to future
- Non-OpenAI-compatible providers — Deferred to v1.2 per REQUIREMENTS.md
