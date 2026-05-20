# Phase 1: Architecture Foundation - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the core infrastructure layers of the Ascend Diagnostic Agent — CLI interaction layer, context builder (code repo ingestion + stack trace ingestion), and MCP-based tool layer foundation.

**Requirements:** ARCH-01 (ingest Python code repos), ARCH-02 (ingest stack traces/logs)

**Success criteria from roadmap:**
1. Agent can accept code repository path as input (local)
2. Agent can accept stack traces/logs as input (file or pasted text)
3. CLI interface exists for running the agent
</domain>

<decisions>
## Implementation Decisions

### CLI Interface Design
- **D-01:** Subcommand structure (`agent diagnose`, `agent reproduce`, `agent fix`) — scales cleanly as capabilities grow
- **D-02:** Use Typer framework (type-hint based, auto-generated help, Rich integration)
- **D-03:** Rich terminal output (colors, tables, syntax-highlighted code) via Rich library
- **D-04:** Both one-shot (scripting/CI) and REPL (interactive debugging) modes
- **D-05:** No-args behavior: show help and available subcommands

### Context Builder — Input Format
- **D-06:** All three input methods supported: file path (`--trace`), stdin pipe, and inline paste (`--trace-text`)
- **D-07:** Local repo path only. SSH remote repo support deferred to Phase 4 (Reproduction)
- **D-08:** No auto-detection of config files (pyproject.toml, setup.cfg) — user specifies explicitly
- **D-09:** One trace at a time per invocation (no batch mode)
- **D-10:** No repo path validation for Python project markers — trust the user's input

### Context Builder — Output Structure
- **D-11:** Pydantic models for structured context output (schema contract for Phase 2)
- **D-12:** Schema includes: repo info (path, language, structure), trace info (lines, error type, file refs), and config env
- **D-13:** No caching — fresh scan each invocation. Diagnosis needs current state

### Tool Layer Foundation
- **D-14:** Use MCP (Model Context Protocol) as the tool layer foundation — tools are MCP servers with JSON Schema inputs and structured results
- **D-15:** Build the MCP server infrastructure in Phase 1 (server framework, tool registration)
- **D-16:** Define MCP tool stubs for all 4 tools (code search, file edit, shell execution, test runner)
- **D-17:** Only code search tool is fully implemented in Phase 1 — remaining 3 tools are stubs to be implemented in their respective phases
- **D-18:** Tool results use MCP's native structured result format (Pydantic-based)

### the agent's Discretion
- No areas explicitly deferred to agent discretion — all decisions made above

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Definition
- `.planning/PROJECT.md` — Project vision, architecture layers, constraints, key decisions
- `.planning/REQUIREMENTS.md` — ARCH-01 and ARCH-02 requirements for Phase 1
- `.planning/ROADMAP.md` — Phase 1 goal, success criteria, full roadmap context

### Technical References
- [MCP Specification](https://modelcontextprotocol.io/) — Model Context Protocol for tool layer

No project-specific external specs or ADRs exist yet — decisions above capture all implementation choices.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- No existing codebase — this is the first phase. All code will be written fresh.

### Established Patterns
- Python project. Config indicates `mode: yolo` in `.planning/config.json`.
- Target codebase is vllm-ascend at `~/vllm-ascend` (Python, Ascend NPU platform)

### Integration Points
- Phase 2 (Diagnosis Engine) consumes context builder output
- Phase 3 (Fix Generation) builds on MCP tool layer (file edit tool)
- Phase 4 (Reproduction) adds SSH remote support + shell execution MCP tool
- Phase 5 (Verification) uses test runner MCP tool

</code_context>

<specifics>
## Specific Ideas

- MCP was raised by the user as the preferred approach for tool communication — tool layer should be MCP-native, not a custom abstraction
- The user explicitly prefers starting simple and deferring complexity to the phase where it's needed (SSH → Phase 4, file edit → Phase 3, etc.)

</specifics>

<deferred>
## Deferred Ideas

- **SSH remote repo support** — belongs in Phase 4 (Reproduction) where remote execution is needed
- **Batch trace input** — could be useful but Phase 2 scope may reveal whether batching is actually needed
- **Config auto-detection** — if manual config becomes cumbersome in practice, revisit in a later phase
- **Context caching** — if repo scanning becomes a performance bottleneck, add TTL-based cache in a maintenance phase

</deferred>

---

*Phase: 1-Architecture Foundation*
*Context gathered: 2026-05-20*
