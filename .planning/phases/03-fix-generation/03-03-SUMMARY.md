---
phase: 03-fix-generation
plan: 03
subsystem: tools
tags: [mcp, file-edit, search-and-replace, backup, pytest]

# Dependency graph
requires:
  - phase: 01-architecture-foundation
    provides: MCP tool pattern, server.py registration, code_search.py analog
  - phase: 02-diagnosis-engine
    provides: Engine pattern, Path.resolve() pattern
provides:
  - edit_file MCP tool with search-and-replace and .bak backup
  - Atomic validation of all operations before any application
  - Path traversal prevention for filesystem safety
affects: [03-fix-generation Plan 04 (fix_cli), Plan 05 (batch_apply)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "MCP tool with search-and-replace operations"
    - "Atomic validation (validate all before applying any)"
    - ".bak backup before file modification"
    - "Path traversal prevention via resolved path prefix check"

key-files:
  created:
    - tests/test_tools/test_file_edit.py
  modified:
    - src/ascend_agent/tools/file_edit.py
    - src/ascend_agent/tools/server.py

key-decisions:
  - "edit_file accepts list[dict] operations (not single content string) per D-13"
  - ".bak backup with path.rename() before writes per D-14"
  - "All operations validated before any applied per D-16"
  - "String 'in' operator for old_text matching (not regex) per threat model T-03-03-02"
  - "Backup file collision check before rename per T-03-03-05"

patterns-established:
  - "edit_file: validate all -> .bak -> apply all in sequence"
  - "Error responses as json.dumps({'status': 'error', 'error': ...})"
  - "ctx.info logging at key steps using if ctx: await ctx.info(...)"
  - "8 async pytest test cases with tmp_path fixtures following code_search pattern"

requirements-completed: [FIX-02]

# Metrics
duration: 1 min
completed: 2026-05-21
---

# Phase 3 Plan 3: Implement edit_file with search-and-replace, .bak backup, and validation

**Search-and-replace edit_file MCP tool with atomic validation, .bak backup, path traversal protection, and 8 unit tests**

## Performance

- **Duration:** 1 min
- **Started:** 2026-05-21T07:42:44Z
- **Completed:** 2026-05-21T07:44:10Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Replaced [STUB] edit_file with full implementation: accepts `list[dict]` operations, validates all before applying any (D-16), creates .bak backup (D-14), prevents path traversal
- EditOperation Pydantic model with `ConfigDict(extra="forbid")` validates old_text/new_text structure
- All operations validated atomically — if any fails validation, nothing is applied and no backup is created
- Created 8 comprehensive async unit tests covering success, error, duplicate, atomic, rollback, traversal, nonexistent, and empty edge cases
- Updated server.py description to reflect real functionality (no longer [STUB])
- Zero new dependencies — all imports from stdlib (pathlib, json), pydantic, and mcp

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement edit_file** — `37ccbff` (feat)
2. **Task 2: Update server.py + create tests** — `b99ef3e` (feat)

**Plan metadata:** `pending` (docs: complete plan)

## Files Created/Modified

- `src/ascend_agent/tools/file_edit.py` - Full edit_file implementation with EditOperation, .bak backup, path traversal prevention, and atomic validation
- `src/ascend_agent/tools/server.py` - Updated edit_file tool description (no more [STUB])
- `tests/test_tools/test_file_edit.py` - 8 async unit tests for edit_file

## Decisions Made

- **Parameter signature**: `edit_file(file_path, operations, repo_path, ctx)` — `operations: list[dict]` allows multiple replacements in one call, `repo_path` is optional for path traversal prevention
- **Backup strategy**: `path.rename(backup_path)` → `write_text(modified)` — rename renames the file inode so the backup holds the original name with .bak suffix
- **Validation failure**: No .bak created if validation fails — avoids creating orphan .bak files when nothing was applied
- **Backup collision**: Check if .bak already exists before rename — prevents overwriting existing backups per T-03-03-05
- **Error return format**: Always `json.dumps({"status": "error", "error": "message"})` for consistent caller handling

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all verifications passed first attempt.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes at trust boundaries. Threat model mitigations (T-03-03-01 through T-03-03-05) are all implemented in the code.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Phase 3 Plan 4 (fix_cli) — the edit_file tool is now fully implemented and tested. Phase 3 Plan 4 will consume it for batch fix application during the review workflow.

---

*Phase: 03-fix-generation*
*Completed: 2026-05-21*
