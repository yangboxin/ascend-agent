# Phase 4: Reproduction Capability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 4-Reproduction Capability
**Areas discussed:** Orchestration approach, Local vs SSH switching, SSH library & config, Shell execution scope, Credential handling, Output format & Phase 5 contract, Environment setup

---

## Orchestration Approach

| Option | Description | Selected |
|--------|-------------|----------|
| ReproductionEngine class (Recommended) | Follows the established Engine pattern from Phase 2/3 — constructor takes repo_path + config, public reproduce() method returns structured result. Testable, clean separation. | ✓ |
| Lightweight: CLI calls exec_shell directly | No engine class — reproduce CLI command directly calls the exec_shell MCP tool. Simpler but harder to test and extend. | |

**User's choice:** ReproductionEngine class (Recommended)
**Notes:** User wants the Engine pattern because it's consistent with Phase 2/3 and provides clean separation.

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-step: prepare → execute → report | 1) Parse diagnosis, set up environment, 2) Execute reproduction command(s), 3) Capture output and produce structured result | ✓ |
| Single command: just run & capture | Take a command from the user, run it (locally or SSH), capture stdout/stderr/exit code. Simpler, defer orchestration complexity. | |

**User's choice:** Multi-step: prepare → execute → report
**Notes:** User wants the engine to handle the full reproduction workflow, not just raw command execution.

---

## Local vs SSH Switching

| Option | Description | Selected |
|--------|-------------|----------|
| Config-based (Recommended) | Settings object has SSH fields. If SSH host is configured, use SSH; otherwise run locally. Simplest UX — user just sets env vars. | ✓ |
| Explicit subcommands | reproduce run (local) and reproduce ssh (remote) as separate commands. Clear distinction, more typing. | |
| Auto-detect | Check if the diagnosis references a remote repo path (ssh://), if so use SSH. Clever but fragile. | |

**User's choice:** Config-based (Recommended)
**Notes:** Straightforward UX — configure SSH and it works, or don't and it runs locally.

| Option | Description | Selected |
|--------|-------------|----------|
| Same process cwd + env | Run commands in the agent's current working directory with inherited env vars. Simplest. | ✓ |
| Specified working directory + env overrides | Take repo_path from diagnosis, allow env var overrides. More configurable but more complex. | |

**User's choice:** Same process cwd + env
**Notes:** Keep it simple for local execution.

---

## SSH Library & Config

| Option | Description | Selected |
|--------|-------------|----------|
| asyncssh (Recommended) | Async-native, fits the async MCP tool pattern. Connection pooling, SFTP support. Runs naturally with asyncio. | ✓ |
| paramiko | Mature and widely used, but sync-only. Would need to wrap in run_in_executor or asyncio subprocess. | |

**User's choice:** asyncssh (Recommended)
**Notes:** asyncssh fits naturally with the async MCP tool pattern. No sync wrapping needed.

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: host, user, key path | SSH_HOST, SSH_USER, SSH_KEY_PATH env vars. Use SSH agent for key management. Simplest setup. | ✓ |
| Full: host, port, user, key, password | Support port, password auth, key auth, and SSH agent. More flexible but more config surface. | |

**User's choice:** Minimal: host, user, key path
**Notes:** Start with minimal config. Can extend if needed later.

---

## Shell Execution Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Single command + timeout (Recommended) | Run one command string with a configurable timeout. Returns stdout, stderr, exit code. Keep it simple — the Engine handles orchestration. | ✓ |
| Full: script, timeout, env, cwd | Support command strings, scripts, timeout, env var overrides, working directory. More flexible but overlaps with Engine orchestration. | |

**User's choice:** Single command + timeout (Recommended)
**Notes:** The tool stays simple; orchestration complexity lives in the Engine.

| Option | Description | Selected |
|--------|-------------|----------|
| Non-interactive only (Recommended) | Only run commands that don't require TTY interaction. If a command needs interactive input, flag it and return guidance. | ✓ |
| Attempt PTY allocation | Try to allocate a pseudo-terminal for SSH sessions. More complex but supports interactive commands. | |

**User's choice:** Non-interactive only (Recommended)
**Notes:** STDIO transport limitation is respected. Interactive commands get guidance instead.

---

## Credential Handling

| Option | Description | Selected |
|--------|-------------|----------|
| SSH agent forwarding (Recommended) | Use the running SSH agent for key management. No keys stored in config — agent handles auth. Matches DevOps best practices. | ✓ |
| Config env vars | Store key path in ASCEND_SSH_KEY_PATH env var. Simpler but less secure — key path in env. | |
| Both: agent first, key path fallback | Try SSH agent first, fall back to config key path. Most flexible setup. | |

**User's choice:** SSH agent forwarding (Recommended)
**Notes:** SSH agent first, key path fallback as second option.

| Option | Description | Selected |
|--------|-------------|----------|
| Block path traversal (Recommended) | Validate that command cwd and file arguments stay within the repo boundary. Same pattern as edit_file's path traversal check (D-15). | ✓ |
| No restriction | Commands can access any path. Simpler but riskier — reproduction could touch system files. | |

**User's choice:** Block path traversal (Recommended)
**Notes:** Same validation pattern as edit_file for consistency and security.

---

## Output Format & Phase 5 Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Full structured model (Recommended) | Pydantic ReproductionResult with: status (success/fail/error), command, stdout, stderr, exit_code, duration, files_changed[], hypothesis_tested. Feeds Phase 5 verification cleanly. | ✓ |
| Minimal: stdout/stderr/exit_code | Just capture raw output. Phase 5 would need to parse it. Simpler but shifts parsing burden. | |

**User's choice:** Full structured model (Recommended)
**Notes:** A proper Pydantic model ensures Phase 5 has a clean contract to consume.

| Option | Description | Selected |
|--------|-------------|----------|
| Structured contract (Recommended) | ReproductionResult includes tested_hypothesis_id and evidence. Phase 5 can directly map: did the reproduction confirm or refute the hypothesis? | ✓ |
| Raw output pass-through | Phase 5 receives raw stdout/stderr. It decides how to interpret. More flexible but no schema guarantee. | |

**User's choice:** Structured contract (Recommended)
**Notes:** hypothesis_id_tested field directly ties reproduction results to diagnosis hypotheses.

---

## Environment Setup

| Option | Description | Selected |
|--------|-------------|----------|
| Assume ready (Recommended) | Engine assumes the target machine (local or SSH) has the environment ready. Runs the command as-is. Simpler, fewer failure points. | |
| Check + setup | Before the command, check deps exist, install missing packages, set env vars from config. More robust but adds latency and complexity. | ✓ |

**User's choice:** Check + setup
**Notes:** User wants the engine to be more robust and check dependencies before running.

| Option | Description | Selected |
|--------|-------------|----------|
| Respect existing venv | If the repo has an active venv/conda env, use it. Don't create one. Engine doesn't manage venvs. | ✓ |
| Auto-activate | Try to detect and activate the repo's virtualenv before running commands. More setup but ensures consistent Python environment. | |

**User's choice:** Respect existing venv
**Notes:** Use existing venv/conda if present. Don't create or manage virtual environments.

---

## the agent's Discretion

- Exact command construction for the reproduction execution.
- Timeout values and retry strategy for transient SSH failures.
- Test approach and coverage targets.

## Deferred Ideas

- **Multi-repo support** — enhancement to Phase 1 ARCH-01. Currently single-repo only.
- **Multi-log ingestion with earliest-error tracing** — enhancement to Phase 2 DIAG-01/02.
- **Multi-modal file input** (screenshots, .log, .txt, .pdf) — enhancement to Phase 1 ARCH-02.
- **Provider/model setup CLI wizard** — new capability. Currently OpenAI-only via env vars.
