---
phase: 06-provider-routing-foundation
plan: 01
subsystem: provider-routing
tags: pydantic, openai, modelrouter, provider-config, env-vars, typer-cli

# Dependency graph
requires:
  - phase: 02-diagnosis-engine
    provides: ModelRouter class, OpenAI client integration, completion() API
  - phase: 05-verification
    provides: pydantic-settings pattern, SettingsConfigDict env prefix convention
provides:
  - ProviderConfig Pydantic model (base_url, api_key, default_model)
  - create_router() factory resolving ASCEND_{PROVIDER}_* env vars
  - ModelRouter backward-compatible update accepting ProviderConfig
  - Settings.openai_api_key field for ASCEND_OPENAI_API_KEY
  - Settings.openai_base_url field for ASCEND_OPENAI_BASE_URL
  - Root --provider CLI flag on ascend-agent callback
affects: [07-chinese-model-integration, 08-provider-config-extensions]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ProviderConfig Pydantic model with ConfigDict(extra='forbid')"
    - "create_router() factory resolving provider-specific env vars"
    - "Dual-path ModelRouter constructor (new ProviderConfig path + backward-compat path)"
    - "Root --provider flag via @app.callback with ctx.obj['provider']"

key-files:
  created: []
  modified:
    - src/ascend_agent/diagnosis/router.py
    - tests/test_diagnosis/test_router.py
    - src/ascend_agent/config.py
    - src/ascend_agent/cli/app.py

key-decisions:
  - "ProviderConfig uses explicit Field(description=...) matching project-wide Pydantic v2 convention"
  - "create_router() is a standalone factory function (not method on ModelRouter) to keep ModelRouter.__init__ simple"
  - "Two-level --provider wiring: root flag via callback, per-command override deferred to plan 06-02"
  - "OpenAI key fallback: ASCEND_OPENAI_API_KEY first, then OPENAI_API_KEY (PROV-04 backward compat)"
  - "Non-openai providers reject missing keys with ValueError (no silent fallback — D-09)"
  - "Settings fields default to empty string, populated from ASCEND_ env prefix via SettingsConfigDict"

patterns-established:
  - "Provider config follows same Pydantic v2 pattern as all domain models (extra='forbid', Field descriptions)"
  - "Env var resolution uses provider-specific prefix pattern: ASCEND_{PROVIDER}_KEY"
  - "Factory function pattern for router construction (create_router) separates env logic from model"

requirements-completed: [PROV-01, PROV-02, PROV-04]

# Metrics
duration: 49 min
completed: 2026-05-26
---

# Phase 6 Plan 01: Provider Routing Foundation Summary

**ProviderConfig Pydantic model, create_router() factory with env-var resolution, ModelRouter backward-compatible update with base_url support, Settings provider fields, and root --provider CLI flag**

## Performance

- **Duration:** 49 min
- **Started:** 2026-05-26T02:24:32Z
- **Completed:** 2026-05-26T03:13:28Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- ProviderConfig Pydantic model with base_url, api_key, default_model and `ConfigDict(extra="forbid")`
- create_router() factory that resolves `ASCEND_{PROVIDER}_API_KEY`, `ASCEND_{PROVIDER}_BASE_URL`, and `ASCEND_{PROVIDER}_DEFAULT_MODEL` from env vars
- OpenAI key fallback: `ASCEND_OPENAI_API_KEY` → `OPENAI_API_KEY` for backward compatibility (PROV-04)
- Non-openai providers (e.g., deepseek) raise actionable ValueError when key is missing
- ModelRouter.__init__ accepts optional `config: ProviderConfig` parameter with new code path using `config.api_key`, `config.base_url`, `config.default_model`
- Backward-compatible code path preserved unchanged (config=None)
- Settings class gains `openai_api_key` and `openai_base_url` fields populated from `ASCEND_` env vars
- Root `--provider` flag on `ascend-agent` callback setting `ctx.obj['provider']`
- 7 new unit tests + 4 existing tests — all 11 passing

## Task Commits

Each task was committed atomically:

1. **Task 1: ProviderConfig + create_router + ModelRouter update + tests** - `0a60d14` (feat)
2. **Task 2: Settings provider fields** - `80dc0ae` (feat)
3. **Task 3: Root --provider flag** - `e41800a` (feat)

**Plan metadata:** (committed after SUMMARY)

## Files Created/Modified
- `src/ascend_agent/diagnosis/router.py` - Added ProviderConfig model, create_router() factory, updated ModelRouter.__init__ with config: ProviderConfig parameter and base_url support
- `tests/test_diagnosis/test_router.py` - Added 7 new tests (ProviderConfig defaults, create_router variants, backward compat)
- `src/ascend_agent/config.py` - Added openai_api_key and openai_base_url fields to Settings
- `src/ascend_agent/cli/app.py` - Added from typing import Optional, create_router import, --provider callback option, ctx.obj wiring

## Decisions Made
- ProviderConfig uses explicit Field(description=...) matching project-wide Pydantic v2 convention
- create_router() is a standalone factory (not method on ModelRouter) to keep __init__ simple
- Dual-path ModelRouter constructor: ProviderConfig path (new) + backward-compat path (deprecated)
- OpenAI key fallback follows PROV-04: ASCEND_OPENAI_API_KEY first, OPENAI_API_KEY as fallback
- Non-openai providers require their specific key — no silent credential fallback (D-09)
- Settings fields use empty string defaults, matching pydantic-settings env_prefix pattern

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `from __future__ import annotations` to non-task source files for test execution on Python 3.9**
- **Found during:** Task 1 (test verification)
- **Issue:** Project requires Python 3.10+ but environment has Python 3.9.6. Multiple source files use `str | None`, `Settings | None`, and other union type syntax (Python 3.10+ feature). Tests couldn't import modules due to `TypeError: unsupported operand type(s) for |`.
- **Fix:** Added `from __future__ import annotations` to 13 source files in the test import chain (context/models.py, context/trace.py, diagnosis/engine.py, reproduction/engine.py, tools/*.py, verification/engine.py, cli/*.py, config.py). Reverted from non-task files after verification; config.py retained for Task 2.
- **Files modified:** 13 source files (temporary, reverted)
- **Verification:** All 11 tests pass
- **Committed in:** Not committed (reverted) — testing-only changes

**2. [Rule 3 - Blocking] Monkeypatched OpenAI.__init__ in tests due to httpx compatibility issue on Python 3.9**
- **Found during:** Task 1 (test verification)
- **Issue:** Installed OpenAI SDK (1.35.10) passes `proxies` kwarg to httpx, but Python 3.9's httpx version doesn't accept it. Real OpenAI client construction failed in 5 tests that use backward-compat code path.
- **Fix:** Added `monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)` to affected tests. Tests only verify `_model` attribute, not actual client behavior.
- **Files modified:** tests/test_diagnosis/test_router.py
- **Verification:** All 11 tests pass
- **Committed in:** `0a60d14` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes were necessary for test execution on the available Python 3.9 environment. The project targets Python 3.10+ where neither issue occurs. No scope creep.

## Issues Encountered
- Python 3.9 environment prevented running the full test suite without `from __future__ import annotations` patches to source files. This is a pre-existing environment limitation (project requires Python 3.10+). The patches are harmless in production (PEP 563) but were reverted from non-task files after verification.
- OpenAI SDK 1.35.10 has an httpx compatibility issue on Python 3.9 that prevents real client construction. All tests mock `OpenAI.__init__` to avoid this.

## User Setup Required

None - no external service configuration required. Provider config is env-var driven.

## Next Phase Readiness
- Core provider routing infrastructure is complete (ProviderConfig, create_router, env var resolution)
- ModelRouter accepts ProviderConfig with base_url override (PROV-01) and per-provider API key (PROV-02)
- OpenAI fallback to OPENAI_API_KEY for backward compatibility (PROV-04)
- Settings class has provider config fields
- Root --provider flag wiring is ready for subcommand consumption
- Ready for Plan 06-02: CLI wiring (create_router() in all 4 CLI commands, per-command --provider overrides, CLI integration tests)

---
*Phase: 06-provider-routing-foundation*
*Completed: 2026-05-26*
