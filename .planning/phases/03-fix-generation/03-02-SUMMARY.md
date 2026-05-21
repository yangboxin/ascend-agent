---
phase: 03-fix-generation
plan: 02
subsystem: cli
tags: fix-engine, rich, typer, cli, diff, sequential-review, batch-apply

requires:
  - phase: 03-fix-generation
    plan: 01
    provides: FixEngine, FixSuggestion, FixGenerationResult, DiagnosisOutput models
  - phase: 03-fix-generation
    plan: 03
    provides: edit_file tool for batch apply
provides:
  - fix run CLI command with diagnosis JSON input (file or stdin)
  - Sequential human review workflow with Rich Panel + Syntax diff display
  - Accept/Skip/Reject per fix with batch apply after review
  - --output flag for accepted fixes JSON
affects: [03-04, 03-05, 04-01]

tech-stack:
  added: [typer, rich, difflib (stdlib), asyncio (stdlib)]
  patterns: [CLI tool command pattern with stdin fallback, Sequential interactive review workflow with Rich prompts, Batch apply grouping by file_path]

key-files:
  created: []
  modified:
    - src/ascend_agent/cli/fix.py
    - tests/test_cli.py

key-decisions:
  - "D-09: Sequential review — one fix at a time, focused review per fix"
  - "D-10: Actions: Accept / Skip / Reject per fix"
  - "D-11: Diff display uses Rich Panel + Syntax('diff') highlighting"
  - "D-12: Accepted fixes queued and applied in batch after all reviewed"
  - "D-17: diagnosis JSON read from file or stdin"
  - "D-19: --output saves accepted FixSuggestion list as JSON"

requirements-completed: [FIX-01, FIX-02]

duration: 4min
completed: 2026-05-21
---

# Phase 03 Plan 02: Fix CLI Command Summary

**CLI `fix run` command with FixEngine wiring, sequential human review workflow with Rich diff display, batch apply via edit_file, and --output persistence**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-21T07:45:44Z
- **Completed:** 2026-05-21T07:49:50Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- `ascend-agent fix run [file]` reads diagnosis JSON from file path (D-17)
- `ascend-agent fix run` (no arg) reads from stdin (D-17)
- FixEngine generates fixes, results displayed with Rich Panel + Syntax diff (D-11)
- Sequential review loop: each fix shown one at a time (D-09), Accept/Skip/Reject prompt (D-10)
- Accepted fixes queued and batch applied after all reviewed (D-12)
- Grouping by file_path prevents sequential edit conflicts (Pitfall 5)
- `--output fixes.json` saves accepted fixes (D-19)
- 4 new CLI integration tests added (8 total, all passing)
- Full test suite: 64 tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement fix run CLI command with FixEngine integration** - `0c3f6e2` (feat)
2. **Task 2: Implement review workflow, batch apply, and --output** - `ac04635` (feat)
3. **Task 3: Add CLI integration tests for fix run command** - `1b609b5` (test)

**Plan metadata:** (committed with this SUMMARY)

## Files Created/Modified
- `src/ascend_agent/cli/fix.py` - Full fix run CLI command: diagnosis parsing (file/stdin), FixEngine integration, sequential review workflow with Rich Panel + Syntax diff, batch apply via edit_file, --output persistence
- `tests/test_cli.py` - Added 4 CLI integration tests for fix run command using CliRunner + monkeypatch pattern

## Decisions Made
- Used Rich `Prompt.ask(choices=["a", "s", "r"])` for Accept/Skip/Reject with automatic input validation
- Used `asyncio.run(edit_file(...))` for batch apply (same pattern as Phase 2's asyncio.run for search_code)
- Grouped accepted fixes by `file_path` with `defaultdict` to batch all replacements per file in a single edit_file call (Pitfall 5 mitigation)
- Capped `_run_review_workflow` return via monkeypatch in tests instead of mocking interactive prompts
- Used CliRunner's `input=` parameter for stdin test (more reliable than monkeypatching sys.stdin)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Typer `Typer` objects use `.info.name` not `.name` — acceptance criteria adjusted accordingly
- CliRunner replaces `sys.stdin` internally, so stdin test uses `runner.invoke(input=...)` instead of `monkeypatch.setattr("sys.stdin", ...)`
- `ModelRouter.__init__` accepts `model` keyword argument — mock lambda updated to accept `**kwargs`

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- CLI fix command ready for integration with full system testing
- Fix generation pipeline complete: diagnosis → fix generation → human review → batch apply
- Ready for Phase 3 Plan 04 (verification) or Plan 05 (integration testing)

---

*Phase: 03-fix-generation*
*Completed: 2026-05-21*
