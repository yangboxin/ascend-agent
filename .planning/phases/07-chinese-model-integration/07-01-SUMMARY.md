---
phase: 07-chinese-model-integration
plan: 01
subsystem: provider-config
tags: deepseek, qwen, create-router, pydantic, settings, env-vars

# Dependency graph
requires:
  - phase: 06-provider-routing-foundation
    provides: ProviderConfig model, create_router() factory, ModelRouter with base_url support
provides:
  - PROVIDER_DEFAULTS dict mapping provider names to default base URLs and models
  - create_router("deepseek") uses https://api.deepseek.com/v1 with deepseek-v4-flash model
  - create_router("qwen") uses https://dashscope.aliyuncs.com/compatible-mode/v1 with qwen-turbo model
  - Settings fields for deepseek_api_key, deepseek_base_url, deepseek_default_model, qwen_api_key, qwen_base_url, qwen_default_model
  - 6 new tests covering DeepSeek and Qwen provider creation paths
affects: [07-02, 09-provider-and-multi-repo-testing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PROVIDER_DEFAULTS dict as single source of truth for provider base URLs and models"
    - "create_router() reads PROVIDER_DEFAULTS for provider-specific fallback values"

key-files:
  created: []
  modified:
    - src/ascend_agent/diagnosis/router.py
    - src/ascend_agent/config.py
    - tests/test_diagnosis/test_router.py

key-decisions:
  - "PROVIDER_DEFAULTS centralizes all provider default configs in one dict"
  - "Settings fields use empty string defaults (matching Phase 6 pattern)"
  - "Non-openai providers raise ValueError with provider-specific key name when key is missing (D-09 from Phase 6)"

requirements-completed: [CHN-01, CHN-02, CHN-03]

# Metrics
duration: 15 min
completed: 2026-05-26
---

# Phase 7 Plan 01: Provider Config + Settings + Tests Summary

**PROVIDER_DEFAULTS dict for DeepSeek/Qwen base URLs and models, Settings provider fields, and 6 provider creation tests**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-26T07:49:00Z
- **Completed:** 2026-05-26T08:04:11Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- PROVIDER_DEFAULTS dict added to router.py with openai, deepseek, qwen entries (base URL + default model)
- create_router() updated to use provider-specific defaults instead of hardcoded OpenAI values
- Settings gained 6 new fields: deepseek_api_key, deepseek_base_url, deepseek_default_model, qwen_api_key, qwen_base_url, qwen_default_model
- 6 new tests: DeepSeek defaults, custom URL, custom model, missing key + Qwen defaults, missing key

## Task Commits

Each task was committed atomically:

1. **Task 1: PROVIDER_DEFAULTS + create_router provider-specific defaults** - `5491a16` (feat)
2. **Task 2: DeepSeek + Qwen Settings fields** - `5491a16` (feat)
3. **Task 3: 6 provider creation tests** - `5491a16` (feat)

**Plan metadata:**

## Files Created/Modified
- `src/ascend_agent/diagnosis/router.py` - Added PROVIDER_DEFAULTS dict; create_router() uses provider-specific base URL and model defaults
- `src/ascend_agent/config.py` - Added 6 Chinese provider config fields following Phase 6 pattern
- `tests/test_diagnosis/test_router.py` - Added 6 tests: deepseek/qwen defaults, custom URL, custom model, missing keys

## Decisions Made
- PROVIDER_DEFAULTS dict is the single source of truth — adding a provider just requires a new entry
- Settings fields use empty string defaults, matching pydantic-settings env_prefix convention from Phase 6
- Non-openai key validation follows D-09: specific key required, no silent fallback to OPENAI_API_KEY
- Default model for deepseek is deepseek-v4-flash; for qwen it's qwen-turbo

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None — provider config is env-var driven.

## Next Phase Readiness
- DeepSeek and Qwen are now fully configurable via `--provider deepseek` / `--provider qwen`
- Both providers work with existing CLI commands without any changes
- Ready for Plan 07-02: structured output fallback for providers without full .parse() support

---
*Phase: 07-chinese-model-integration*
*Completed: 2026-05-26*
