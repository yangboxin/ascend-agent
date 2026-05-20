# Ascend Diagnostic Agent

## What This Is

An AI agentic system for the Ascend maintenance team to diagnose and fix issues in Python codebases (starting with vllm-ascend). The agent analyzes code and stack traces, proposes hypotheses, suggests fixes, reproduces issues on test machines, and verifies solutions.

## Core Value

Enable the Ascend maintenance team to diagnose and fix production issues 10x faster by automating the investigation, reproduction, and verification loop.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **ARCH-01**: Agent can ingest Python code repositories (local clone or remote via SSH)
- [ ] **ARCH-02**: Agent can ingest stack traces and log files (file upload or pasted text)
- [ ] **DIAG-01**: Agent can analyze stack traces to identify root cause and propose hypotheses with evidence
- [ ] **DIAG-02**: Agent can locate relevant source code from stack trace information
- [ ] **FIX-01**: Agent can generate code fixes based on diagnosis
- [ ] **FIX-02**: Agent can suggest fixes for review before applying (not auto-apply)
- [ ] **REPRO-01**: Agent can reproduce issues locally or via SSH using provided configuration
- [ ] **VERIF-01**: Agent can run tests to verify fixes
- [ ] **VERIF-02**: Agent can report verification results

### Out of Scope

- [Agent auto-applies fixes without review] — User must review suggestions
- [Support for non-Python languages] — Focus on Python first
- [Real-time monitoring] — This is a diagnostic tool, not a monitoring system

## Architecture Layers

The agent uses a layered architecture that can evolve:

1. **CLI Interaction Layer** — How users interact with the agent (commands, args)
2. **Context Builder** — Gathers and structures problem context (code + logs + config)
3. **Orchestrator** — Coordinates the diagnostic workflow (LangGraph state machine + memory)
4. **Model Router** — Routes requests to appropriate models (quality vs speed vs cost)
5. **Tool Layer** — Capabilities (code search, file edit, shell execution, test runner)

## Context

- **Primary codebase**: vllm-ascend (located at ~/vllm-ascend)
- **Initial use case**: Analyze runtime errors, logic bugs, performance issues, and test failures
- **Target environment**: Internal Ascend test machines (SSH accessible)
- **Problem types**: Runtime errors, logic bugs, performance issues, test failures

## Constraints

- **Tech Stack**: Configurable — initial implementation may use LangChain/LangGraph, but can evolve
- **Execution**: Must support both local and remote (SSH) execution for reproduction
- **Review**: All code fixes must be reviewed by human before application
- **Verification**: All fixes must be verified by running relevant tests

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Agent output: Suggest and review | Safety critical — fixes must be reviewed | — Pending |
| Target: vllm-ascend first | Real production use case to validate | — Pending |
| Problem types: All (runtime, logic, performance, tests) | Comprehensive coverage needed | — Pending |

---

*Last updated: 2025-05-20 after initialization*
