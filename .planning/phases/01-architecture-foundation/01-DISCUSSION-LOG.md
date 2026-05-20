# Phase 1: Architecture Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 1-Architecture Foundation
**Areas discussed:** CLI interface design, Context builder input format, Context builder output structure, Tool layer initial scope

---

## CLI Interface Design

| Option | Description | Selected |
|--------|-------------|----------|
| Subcommands | `agent diagnose`, `agent reproduce`, `agent fix`. Scales cleanly. | ✓ |
| Flags mode | `agent --diagnose --repo path`. Simpler but unwieldy as capabilities grow. | |

| Option | Description | Selected |
|--------|-------------|----------|
| Typer | Modern, type-hint based, Rich integration | ✓ |
| Click | Mature, widely used, more boilerplate | |
| Argparse | Standard library, most boilerplate | |

| Option | Description | Selected |
|--------|-------------|----------|
| Both REPL and one-shot | REPL for interactive, one-shot for scripting/CI | ✓ |
| One-shot only | Simpler, re-run for new diagnoses | |

| Option | Description | Selected |
|--------|-------------|----------|
| Rich terminal | Colors, tables, progress bars, syntax highlighting | ✓ |
| Plain structured text | Simple stdout, easy to parse/pipe | |
| JSON + --pretty flag | Machine-readable primary, human-friendly optional | |

| Option | Description | Selected |
|--------|-------------|----------|
| Show help + available commands | `agent` prints usage | ✓ |
| Launch REPL mode | `agent` drops into interactive session | |
| Prompt to diagnose | Interactive guided prompt | |

**User's choice:** Subcommands, Typer, both modes, Rich output, help on no-args
**Notes:** User favored scalability and developer experience

---

## Context Builder Input Format

| Option | Description | Selected |
|--------|-------------|----------|
| All three methods | File path, stdin pipe, inline paste | ✓ |
| File + stdin only | No inline paste | |
| File path only | Simplest | |

| Option | Description | Selected |
|--------|-------------|----------|
| Local path + SSH remote | Full ARCH-01 coverage | |
| Local path only initially | SSH deferred to Phase 4 | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, auto-detect | Read pyproject.toml, setup.cfg, .env | |
| No, explicit only | User specifies manually | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Multiple, comma-separated | Batch mode for related failures | |
| One at a time | Simpler internals | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, warn on mismatch | Validate Python project markers | |
| No, trust the user | Accept any path | ✓ |

**User's choice:** All three input methods, local only (SSR deferred), no auto-detect, one at a time, no validation
**Notes:** User prefers simplicity — defer complexity to the phase that needs it

---

## Context Builder Output Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic models | Type-validated, clear schema contract | ✓ |
| Plain dataclasses | Simpler, no external dep | |
| TypedDict | Lightest, no validation | |

| Option | Description | Selected |
|--------|-------------|----------|
| Repo + trace + config | Rich context for comprehensive diagnosis | ✓ |
| Repo path + trace only | Minimal schema | |

| Option | Description | Selected |
|--------|-------------|----------|
| No cache | Fresh scan each invocation | ✓ |
| Cache with TTL | Faster repeated runs, risk of stale data | |

**User's choice:** Pydantic models, repo+trace+config schema, no caching
**Notes:** Freshness prioritized over speed for diagnosis accuracy

---

## Tool Layer Initial Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Code search only | Tool interface + code search. Others deferred | |
| All four tool interfaces (stubs) | Define interface for all 4, implement code search fully | ✓ |
| Code search + file edit | Both needed for fix generation (premature) | |

| Option | Description | Selected |
|--------|-------------|----------|
| ABC + per-tool impl | BaseTool with run/validate/describe | |
| Protocol/interface | Python Protocol, structural subtyping | |
| Function registry | Dict of name -> callable | |

(Note: MCP decision superseded this — MCP provides the tool interface natively)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, use MCP | Tools are MCP servers. Standard protocol. | ✓ |
| No, custom abstraction | Build our own BaseTool ABC | |
| Need to explore MCP first | Not sure how MCP would work | |

| Option | Description | Selected |
|--------|-------------|----------|
| Build MCP server infra | Server framework + code search MCP tool | ✓ |
| Define stubs as MCP schemas | Write JSON Schema definitions only | |

**User's choice:** All 4 tools as MCP stubs, build MCP server infra, code search implemented fully
**Notes:** User introduced MCP — this is a significant architectural decision. MCP provides the tool interface, making custom BaseTool ABC unnecessary.

---

## Deferred Ideas

- SSH remote repo support → Phase 4 (Reproduction)
- Batch trace input → revisit if Phase 2 needs it
- Config auto-detection → revisit if manual config is cumbersome
- Context caching → revisit if repo scanning is a performance bottleneck

---

*Discussion captured: 2026-05-20*
