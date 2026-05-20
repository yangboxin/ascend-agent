# Roadmap: Ascend Diagnostic Agent

**Created:** 2025-05-20

---

## Phase 1: Architecture Foundation
**Goal:** Build the core infrastructure layers — CLI interaction, context builder, and tool layer foundation.

**Requirements:** ARCH-01, ARCH-02

**Success Criteria:**
1. Agent can accept code repository path as input (local)
2. Agent can accept stack traces/logs as input (file or pasted text)
3. CLI interface exists for running the agent

**Plans (4 in 3 waves):**

**Wave 1 *(foundation)* — Plan 01-01** ✅
- Project scaffold, pyproject.toml, Pydantic models (RepoInfo, TraceInfo, ConfigEnv, ContextDocument), config/settings, test infrastructure

**Wave 2 *(parallel — context builder + MCP server)* — Plans 01-02, 01-04**
- 01-02: RepoScanner (pathlib + .gitignore), TraceParser (regex), 7 unit tests
- 01-04: FastMCP server, code search tool (rg + Python fallback), 3 tool stubs

**Wave 3 *(CLI integration)* — Plan 01-03**
- Typer app, diagnose command, Rich output, three input methods, visual verify checkpoint

**Cross-cutting constraints:**
- `print()` must never be used in MCP tools — use `ctx.info()` or `stderr`
- No SSH/remote support (Phase 4)
- Code search restricted to `.py` files in Phase 1

---

## Phase 2: Diagnosis Engine
**Goal:** Implement the core diagnosis capability — analyze stack traces, locate source code, generate hypotheses.

**Requirements:** DIAG-01, DIAG-02

**Success Criteria:**
1. Agent parses stack traces and extracts error locations
2. Agent searches codebase to find relevant source files
3. Agent proposes hypotheses with evidence (code snippets, line numbers)

---

## Phase 3: Fix Generation
**Goal:** Generate code fixes based on diagnosis findings.

**Requirements:** FIX-01, FIX-02

**Success Criteria:**
1. Agent generates fix suggestions based on diagnosis
2. Agent presents fixes for human review (not auto-apply)
3. Agent can explain the reasoning behind each fix

---

## Phase 4: Reproduction Capability
**Goal:** Reproduce issues on test machines using provided configuration.

**Requirements:** REPRO-01

**Success Criteria:**
1. Agent can execute commands locally to reproduce issues
2. Agent can connect via SSH to remote test machines
3. Agent uses provided configuration (or defaults) for reproduction

---

## Phase 5: Verification &闭环
**Goal:** Verify fixes by running tests and reporting results.

**Requirements:** VERIF-01, VERIF-02

**Success Criteria:**
1. Agent runs relevant tests to verify fixes
2. Agent reports pass/fail status with details
3. Agent provides summary of what was verified

---

## Summary

| Phase | Name | Requirements | Success Criteria |
|-------|------|--------------|------------------|
| 1 | Architecture Foundation | ARCH-01, ARCH-02 | 3 |
| 2 | Diagnosis Engine | DIAG-01, DIAG-02 | 3 |
| 3 | Fix Generation | FIX-01, FIX-02 | 3 |
| 4 | Reproduction Capability | REPRO-01 | 3 |
| 5 | Verification &闭环 | VERIF-01, VERIF-02 | 3 |

**Total: 5 phases | 9 requirements | 15 success criteria**

---

*Roadmap created: 2025-05-20*
