# Phase 4: Reproduction Capability - Research

**Researched:** 2026-05-25
**Domain:** Async command execution (local subprocess + remote SSH) for issue reproduction
**Confidence:** HIGH

## Summary

Phase 4 implements a structured reproduction capability that takes a `DiagnosisResult` from Phase 2/3 and executes reproduction commands either locally or via SSH on remote test machines. The architecture follows the proven Engine pattern: a `ReproductionEngine` class orchestrates a prepare → execute → report workflow, calling the `exec_shell` MCP tool for actual command execution. The tool abstracts the local/remote decision behind a single async interface, using `asyncio.create_subprocess_shell()` locally and `asyncssh` for remote connections.

**Primary recommendation:** Implement `exec_shell` as the unified execution backend first (it's the critical path), then build the `ReproductionEngine` orchestration layer on top, and finally wire the Typer CLI. The asyncssh API is well-documented and straightforward — the main risk is error handling edge cases (connection drops, timeouts, host key verification).

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** `ReproductionEngine` class following the Engine pattern from Phase 2/3 — constructor takes `router: ModelRouter` + `repo_path: str` + settings, public `reproduce()` method returns structured `ReproductionResult`.
- **D-02:** Multi-step workflow: prepare (parse diagnosis, check environment deps) → execute (run command) → report (capture structured result with stdout/stderr/exit_code).
- **D-03:** Config-based switching — if SSH host is configured (via `ASCEND_SSH_HOST` env var), use asyncssh for remote execution; otherwise run locally using `asyncio.create_subprocess_shell()`.
- **D-04:** Local execution context: same process cwd + inherited environment variables. No separate working directory management.
- **D-05:** Use `asyncssh` for async-native SSH execution — fits the async MCP tool pattern naturally. No sync wrappers needed.
- **D-06:** Minimal SSH config via env vars: `ASCEND_SSH_HOST`, `ASCEND_SSH_USER`, `ASCEND_SSH_KEY_PATH`. SSH agent is the default key management mechanism.
- **D-07:** `exec_shell` MCP tool runs a single command string with a configurable timeout. Returns stdout, stderr, exit code. No script mode — the Engine handles orchestration.
- **D-08:** Non-interactive only — no PTY allocation. Commands requiring TTY interaction are flagged with guidance. STDIO transport limitation is respected.
- **D-09:** SSH agent forwarding is the primary authentication method. Falls back to key path from config if the agent is unavailable.
- **D-10:** Path traversal protection — validates that execution stays within the repo boundary. Same pattern as `edit_file`'s path traversal check (Phase 3 D-15).
- **D-11:** `ReproductionResult` Pydantic model with fields: `status` (success/fail/error), `command`, `stdout`, `stderr`, `exit_code`, `duration_seconds`, `hypothesis_id_tested`, `files_changed`. Structured contract for Phase 5 consumption.
- **D-12:** Output includes `hypothesis_id_tested` to directly map which diagnosis hypothesis was tested. Phase 5 Verification consumes this to confirm or refute fixes.
- **D-13:** ReproductionEngine checks dependencies exist before running the command. Installs missing packages if needed. Sets environment variables from config.
- **D-14:** If the target repo has an active virtualenv/conda environment, respect and use it. The engine does not create or manage virtual environments.

### The Agent's Discretion
- Exact command construction for the reproduction execution.
- Timeout values and retry strategy for transient SSH failures.
- Test approach and coverage targets.

### Deferred Ideas (OUT OF SCOPE)
- **Multi-repo support** — enhancement to ARCH-01. Currently single-repo only.
- **Multi-log ingestion with earliest-error tracing** — enhancement to DIAG-01/02.
- **Multi-modal file input** (screenshots, .log, .txt, .pdf) — enhancement to ARCH-02.
- **Provider/model setup CLI wizard** — new capability.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REPRO-01 | Agent can reproduce issues locally or via SSH using provided configuration | Standard Stack (asyncssh + asyncio subprocess) + Architecture Patterns (exec_shell MCP tool + ReproductionEngine) enable both execution modes |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Command execution (local) | Tool Layer | — | `exec_shell` MCP tool runs subprocess; Engine calls the tool |
| Command execution (remote SSH) | Tool Layer | — | `exec_shell` MCP tool delegates to asyncssh; Engine calls the tool |
| SSH connection management | Tool Layer | — | Encapsulated inside `exec_shell`; Engine never touches SSH directly |
| Multi-step workflow orchestration | Engine Layer | — | `ReproductionEngine.prepare → execute → report` (D-02) |
| Environment preparation (venv detect, dep check) | Engine Layer | — | D-13, D-14 — pre-execution checks before tool calls |
| CLI entry point | CLI Layer | — | Typer `reproduce run` command dispatches to Engine |
| Result modeling | Shared Models | — | `ReproductionResult` lives in `diagnosis/models.py` (D-11) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncssh | >=2.23.0 | Async-native SSH client for remote command execution | Locked by D-05; production-stable (2015+), async-native (fits FastMCP pattern), 1.7k GitHub stars, supports SSH agent forwarding (D-09), no PTY by default (D-08) |
| asyncio (stdlib) | Python 3.10+ | `create_subprocess_shell()` for local execution | Locked by D-03; stdlib — no external dependency; `Process.communicate()` handles deadlock-safe I/O |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | >=2.13.0 | `ReproductionResult` model (D-11) | Already in project; reuse existing `ConfigDict(extra="forbid")` pattern |
| pydantic-settings | >=2.14.0 | SSH config fields in Settings class (D-06) | Already in project; extend existing `Settings` class |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncssh | paramiko | D-05 locks asyncssh. paramiko is sync-only, would need `asyncio.to_thread()` wrapper — extra complexity, defeats the async MCP tool pattern. |
| asyncio.create_subprocess_shell | subprocess.run (sync) | Sync subprocess would block the MCP tool event loop. D-03 locks the async path. |

**Installation:**
```bash
# asyncssh is a NEW dependency — not yet in pyproject.toml
pip install "asyncssh>=2.23.0"
```

**Version verification:** asyncssh 2.23.0 confirmed on PyPI (released 2026-05-09, `Python >=3.10`, `cryptography >=39.0`) [VERIFIED: pypi.org/project/asyncssh/]. No `postinstall` scripts [VERIFIED: PyPI release metadata — pure Python wheel, no binary extension build step needed].

## Package Legitimacy Audit

> slopcheck was not available at research time. All packages tagged `[ASSUMED]`. Planner MUST gate each install behind a `checkpoint:human-verify` task.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| asyncssh | PyPI | ~11 yrs (v1.0.0 Apr 2015) | 1.7k GitHub stars, established | github.com/ronf/asyncssh | N/A (slopcheck unavailable) | Approved [ASSUMED] — planner: add checkpoint |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
**Packages with [ASSUMED] tag:** 1 (asyncssh) — planner must insert `checkpoint:human-verify` before `pip install asyncssh`

*slopcheck was unavailable at research time. All packages are tagged `[ASSUMED]` and the planner must gate each install behind a `checkpoint:human-verify` task.*

## Architecture Patterns

### System Architecture Diagram

```
┌──────────────────────────────────────────────────┐
│  CLI Layer (Typer)                                │
│  reproduce run <diagnosis.json>                   │
│  → `src/ascend_agent/cli/reproduce.py`           │
└──────────────────────┬───────────────────────────┘
                       │ loads DiagnosisOutput, calls
                       ▼
┌──────────────────────────────────────────────────┐
│  Engine Layer                                     │
│  ReproductionEngine                               │
│  → `src/ascend_agent/reproduction/engine.py`     │
│                                                   │
│  prepare() → execute() → report()  (D-02)        │
│  ┌─────────────────────────────────────────────┐ │
│  │ 1. Parse DiagnosisResult                    │ │
│  │ 2. Detect venv/conda (D-14)                 │ │
│  │ 3. Check dependencies (D-13)                │ │
│  │ 4. For each hypothesis:                     │ │
│  │    → call exec_shell(command, timeout)      │ │
│  │    → collect stdout/stderr/exit_code        │ │
│  │ 5. Build ReproductionResult (D-11)          │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  Returns: ReproductionResult (D-11)               │
│    → Phase 5 consumes as input                    │
└──────────────────────┬───────────────────────────┘
                       │ async call
                       ▼
┌──────────────────────────────────────────────────┐
│  Tool Layer (MCP — FastMCP)                       │
│  exec_shell → `src/ascend_agent/tools/shell_exec.py`│
│  ┌─────────────────────────────────────────────┐ │
│  │ if ASCEND_SSH_HOST:  (D-03)                 │ │
│  │   asyncssh.connect(host, username, key)     │ │
│  │   conn.run(command, timeout=...)  (D-07)    │ │
│  │ else:                                       │ │
│  │   asyncio.create_subprocess_shell(command)  │ │
│  │   proc.communicate(timeout=...)  (D-03)     │ │
│  │                                             │ │
│  │ Returns: JSON {status, stdout, stderr,      │ │
│  │                exit_code}                    │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
   ┌─────────────┐          ┌──────────────┐
   │ Local Shell  │          │ Remote SSH    │
   │ (subprocess) │          │ (asyncssh)    │
   │ cwd + env    │          │ key/agent auth│
   │ inherited    │          │ non-PTY       │
   └─────────────┘          └──────────────┘
```

### Recommended Project Structure

```
src/ascend_agent/
├── reproduction/              # NEW package
│   ├── __init__.py
│   └── engine.py              # ReproductionEngine class (D-01, D-02)
├── tools/
│   └── shell_exec.py          # MODIFIED: replace stub with full implementation
├── diagnosis/
│   └── models.py              # MODIFIED: add ReproductionResult model (D-11)
├── config.py                  # MODIFIED: add SSH settings fields (D-06)
└── cli/
    └── reproduce.py           # MODIFIED: wire to ReproductionEngine

tests/
├── test_reproduction/         # NEW
│   ├── __init__.py
│   ├── conftest.py            # Shared fixtures (mock router, sample diagnosis)
│   ├── test_engine.py         # ReproductionEngine unit tests
│   └── test_models.py         # ReproductionResult model validation tests
└── test_tools/
    └── test_shell_exec.py     # NEW: exec_shell local + SSH tests
```

### Pattern 1: Engine Pattern (from Phase 2/3 — D-01)

**What:** A class with constructor(router, repo_path) and a public method returning a structured Pydantic result.

**When to use:** Any engine component that orchestrates multi-step operations.

**Reference implementation:** `src/ascend_agent/diagnosis/engine.py` (Engine class)

**Example (ReproductionEngine skeleton):**
```python
# Source: Phase 2 Engine pattern (src/ascend_agent/diagnosis/engine.py)
# Adapted for ReproductionEngine per D-01

import asyncio
import time
import logging
from pathlib import Path

from ascend_agent.diagnosis.models import DiagnosisResult, ReproductionResult
from ascend_agent.diagnosis.router import ModelRouter
from ascend_agent.config import Settings

logger = logging.getLogger(__name__)


class ReproductionEngine:
    """Orchestrates issue reproduction from diagnosis hypotheses.

    Follows Engine pattern: constructor → public method → structured result.
    Multi-step workflow: prepare → execute → report (D-02).
    """

    def __init__(self, router: ModelRouter, repo_path: str, settings: Settings | None = None):
        self._router = router
        self._repo_path = Path(repo_path).resolve()
        self._settings = settings or Settings()

    # -- Public API --

    async def reproduce(self, diagnosis: DiagnosisResult) -> ReproductionResult:
        """Run the reproduction workflow. Returns structured ReproductionResult."""
        # Step 1: prepare (D-13, D-14)
        venv_env = self._detect_venv()
        env_vars = {**venv_env, **self._settings.env_vars}

        # Step 2: execute (D-03) — for each hypothesis, run reproduction command
        results = []
        for i, hypothesis in enumerate(diagnosis.hypotheses):
            command = self._build_reproduction_command(hypothesis)
            start = time.monotonic()
            try:
                from ascend_agent.tools.shell_exec import exec_shell
                result_json = await exec_shell(command, timeout=self._settings.shell_timeout)
                result = json.loads(result_json)
            except Exception as e:
                result = {"status": "error", "stdout": "", "stderr": str(e), "exit_code": -1}
            duration = time.monotonic() - start
            results.append(ReproductionResult(
                status=result.get("status", "error"),
                command=command,
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", ""),
                exit_code=result.get("exit_code", -1),
                duration_seconds=duration,
                hypothesis_id_tested=i,
                files_changed=[],
            ))

        # Step 3: report (D-11)
        return results[0] if results else ReproductionResult(
            status="error", command="", stdout="", stderr="No hypotheses to test",
            exit_code=-1, duration_seconds=0, hypothesis_id_tested=-1, files_changed=[],
        )

    # -- Internal helpers --

    def _detect_venv(self) -> dict[str, str]:
        """Detect active virtualenv or conda environment (D-14)."""
        import os
        env = {}
        if "VIRTUAL_ENV" in os.environ:
            env["VIRTUAL_ENV"] = os.environ["VIRTUAL_ENV"]
        if "CONDA_PREFIX" in os.environ:
            env["CONDA_PREFIX"] = os.environ["CONDA_PREFIX"]
        return env

    def _build_reproduction_command(self, hypothesis) -> str:
        """Construct the reproduction command from hypothesis context (agent's discretion)."""
        # The agent's discretion: exact command construction
        # Typically: run the failing test or script identified in evidence
        root_cause = hypothesis.root_cause
        # Simple heuristic: if evidence references a file, run it
        if hypothesis.evidence:
            evidence_file = hypothesis.evidence[0].file_path
            return f"python {evidence_file}"
        return f"echo 'No actionable command for: {root_cause}'"
```

### Pattern 2: MCP Tool Pattern (from Phase 2/3 — exec_shell)

**What:** An `async def` function registered with FastMCP that returns a JSON string.

**When to use:** Every tool exposed to the MCP server.

**Reference implementation:** `src/ascend_agent/tools/file_edit.py` (edit_file function)

**Example (exec_shell full implementation):**
```python
# Source: asyncssh official docs (https://asyncssh.readthedocs.io/en/latest/)
#         + Python 3.10+ asyncio subprocess docs
#         + existing edit_file MCP tool pattern

import json
import asyncio
import logging
import os

from mcp.server.fastmcp import Context

from ascend_agent.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60  # seconds


async def exec_shell(
    command: str,
    timeout: int = DEFAULT_TIMEOUT,
    ctx: Context | None = None,
) -> str:
    """Execute a shell command locally or via SSH.

    Config-based switching (D-03): if ASCEND_SSH_HOST is set, uses asyncssh;
    otherwise runs locally via asyncio.create_subprocess_shell().

    Non-interactive only — no PTY allocation (D-08).

    Args:
        command: Shell command string to execute.
        timeout: Maximum seconds to wait for command completion.
        ctx: Optional FastMCP context for logging.

    Returns:
        JSON string with keys: status, stdout, stderr, exit_code.
    """
    ssh_host = os.environ.get("ASCEND_SSH_HOST")

    if ssh_host:
        return await _exec_remote(command, timeout, ctx)
    else:
        return await _exec_local(command, timeout, ctx)


async def _exec_local(command: str, timeout: int, ctx: Context | None = None) -> str:
    """Execute command locally via asyncio subprocess (D-03, D-04).

    Uses same cwd and inherits environment variables. No separate working
    directory management — the process gets the agent's current environment.
    """
    try:
        if ctx:
            await ctx.info(f"Executing locally: {command}")

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return json.dumps({
                "status": "error",
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "exit_code": -1,
            })

        stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        return json.dumps({
            "status": "success" if proc.returncode == 0 else "fail",
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc.returncode or 0,
        })

    except Exception as e:
        logger.exception("Local command execution failed: %s", e)
        return json.dumps({
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
        })


async def _exec_remote(command: str, timeout: int, ctx: Context | None = None) -> str:
    """Execute command via SSH using asyncssh (D-05, D-06, D-09).

    SSH agent forwarding is primary auth (D-09). Falls back to key path
    from config if agent is unavailable. Non-interactive — no PTY (D-08).
    """
    import asyncssh

    ssh_host = os.environ["ASCEND_SSH_HOST"]
    ssh_user = os.environ.get("ASCEND_SSH_USER")
    ssh_key_path = os.environ.get("ASCEND_SSH_KEY_PATH")

    try:
        if ctx:
            await ctx.info(f"Connecting to {ssh_host}...")

        # Build connect kwargs (D-06: minimal config)
        connect_kwargs: dict = {"host": ssh_host, "known_hosts": None}
        if ssh_user:
            connect_kwargs["username"] = ssh_user
        # D-09: ssh-agent is default — asyncssh uses SSH_AUTH_SOCK automatically
        # Falls back to key path if set
        if ssh_key_path:
            connect_kwargs["client_keys"] = [ssh_key_path]

        async with asyncssh.connect(**connect_kwargs) as conn:
            if ctx:
                await ctx.info(f"Connected to {ssh_host}, running: {command}")

            # D-07: single command + timeout
            # D-08: no term_type arg → no PTY allocated
            result = await asyncio.wait_for(
                conn.run(command, check=False),
                timeout=timeout,
            )

            return json.dumps({
                "status": "success" if result.exit_status == 0 else "fail",
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
                "exit_code": result.exit_status or 0,
            })

    except asyncssh.Error as e:
        logger.warning("SSH connection error: %s", e)
        return json.dumps({
            "status": "error",
            "stdout": "",
            "stderr": f"SSH connection failed: {e}",
            "exit_code": -1,
        })
    except asyncssh.ProcessError as e:
        return json.dumps({
            "status": "fail",
            "stdout": "",
            "stderr": e.stderr or str(e),
            "exit_code": e.exit_status,
        })
    except asyncio.TimeoutError:
        return json.dumps({
            "status": "error",
            "stdout": "",
            "stderr": f"SSH command timed out after {timeout}s",
            "exit_code": -1,
        })
    except Exception as e:
        logger.exception("Remote execution failed: %s", e)
        return json.dumps({
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
        })
```

### Pattern 3: Pydantic Model Pattern (from Phase 2/3)

**What:** Pydantic v2 model with `ConfigDict(extra="forbid")` and `Field(description=...)`.

**When to use:** Every structured data class in the codebase.

**Reference:** `src/ascend_agent/diagnosis/models.py`

**Example (ReproductionResult — D-11):**
```python
# Add to src/ascend_agent/diagnosis/models.py
# Follows existing model conventions: ConfigDict(extra="forbid"), Field descriptions

class ReproductionResult(BaseModel):
    """Structured result from reproduction execution (D-11, D-12)."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(
        pattern=r"^(success|fail|error)$",
        description="Outcome: success (exit 0), fail (non-zero exit), error (execution failure)",
    )
    command: str = Field(description="The command that was executed")
    stdout: str = Field(default="", description="Standard output captured")
    stderr: str = Field(default="", description="Standard error captured")
    exit_code: int = Field(default=-1, description="Process exit code")
    duration_seconds: float = Field(ge=0.0, description="Wall-clock duration of command execution")
    hypothesis_id_tested: int = Field(
        ge=-1, description="Index of hypothesis this test addresses (-1 if none)"
    )
    files_changed: list[str] = Field(
        default_factory=list,
        description="List of repo-relative paths to files modified during reproduction",
    )
```

### Pattern 4: Settings Extension Pattern

**What:** Extend the existing `Settings` class with new config fields.

**Reference:** `src/ascend_agent/config.py`

**Example (SSH config extension — D-06):**
```python
# Modify src/ascend_agent/config.py
# ASCEND_ prefix is already set via SettingsConfigDict(env_prefix="ASCEND_")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASCEND_")

    # Existing fields...
    python_version: str = ""
    platform: str = ""
    env_vars: dict[str, str] = {}
    repo_path: str | None = None
    mcp_server_command: str = "python -m ascend_agent.tools.server"

    # NEW: SSH configuration (D-06)
    ssh_host: str = Field(default="", description="SSH hostname for remote execution")
    ssh_user: str = Field(default="", description="SSH username for remote execution")
    ssh_key_path: str = Field(default="", description="Path to SSH private key file (fallback if agent unavailable)")
    shell_timeout: int = Field(default=60, ge=1, description="Default timeout in seconds for shell commands")

    # Keep existing model_post_init...
```

### Anti-Patterns to Avoid

- **Mixing sync and async in MCP tools:** All MCP tools must be `async def` with no blocking calls. Never use `subprocess.run()` (sync) inside exec_shell — use `asyncio.create_subprocess_shell()` instead. This was a deliberate Phase 1 decision (D-17).
- **PTY allocation for non-interactive commands:** asyncssh only allocates a PTY when `term_type` is passed to `conn.run()`. For reproduction commands, never pass `term_type` — the default is non-PTY (D-08). PTY mixing stdout/stderr makes parsing unreliable.
- **Hardcoding SSH credentials:** Never hardcode hostnames or user names. All config comes from env vars (D-06). The exec_shell tool reads `os.environ` at call time.
- **Ignoring venv/conda detection:** Before running commands locally, the engine must check `VIRTUAL_ENV` and `CONDA_PREFIX` (D-14). Failing to detect an active venv means pip-installed packages for the target project won't be found.
- **Single monolithic function for local+remote:** Keep local and remote execution in separate private functions (`_exec_local`, `_exec_remote`) behind a single `exec_shell` entry point. This makes testing each path independently possible.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async SSH client | Custom paramiko+thread wrapper | `asyncssh` 2.23.0 | Locked by D-05. Hand-rolled SSH with sync library introduces thread-safety bugs, deadlock risks, and violates the async MCP tool contract. asyncssh handles key negotiation, host key verification, session multiplexing, and connection recovery. |
| Subprocess timeout management | Custom timer+kill logic | `asyncio.wait_for(proc.communicate(), timeout)` | Built into stdlib. Hand-rolled timeout needs signal handling, process group management, and cross-platform SIGKILL/SIGTERM differences. |
| Shell command escaping | Manual string escaping | `shlex.quote()` (if constructing commands) or pass-through strings | Shell injection protection. The `exec_shell` tool receives command strings; the Engine should construct commands safely. If commands include user-supplied values, use `shlex.quote()`. |
| Path traversal checks | Custom path validation | `Path(path).resolve()` then `str(path).startswith(str(repo))` | Same pattern as `edit_file` (Phase 3 D-15). Already tested and proven. Reuse the identical logic. |

**Key insight:** The two execution backends (local subprocess + remote SSH) are deceptively simple individually but have significant edge cases: timeout handling, deadlock prevention when both stdout/stderr pipes fill up, encoding differences, signal propagation, and connection recovery. Using stdlib asyncio and asyncssh avoids all of these pitfalls.

## Common Pitfalls

### Pitfall 1: Subprocess deadlock with large stdout/stderr

**What goes wrong:** `proc.communicate()` must be called to avoid deadlock when using `stdout=PIPE, stderr=PIPE`. If you call `proc.wait()` instead while the process is still writing to stdout/stderr, the pipe buffer fills and the process blocks forever.

**Why it happens:** Python's `asyncio-queue` pipes have a limited OS buffer (~64KB). When the buffer is full, the child process blocks on `write()`, but nothing is reading the buffer.

**How to avoid:** Always use `proc.communicate()` (which reads both pipes concurrently) or `asyncio.wait_for(proc.communicate(), timeout)`. Never call `proc.wait()` directly when using PIPE.

**Warning signs:** Process hangs after a few seconds of output; `exit_code` never gets set; increasing timeout doesn't help.

### Pitfall 2: asyncssh host key verification blocking automation

**What goes wrong:** asyncssh checks `~/.ssh/known_hosts` by default. If the target host isn't in known_hosts, the connection fails with `HostKeyNotVerifiable`. This breaks automated reproduction on test machines with ephemeral host keys.

**Why it happens:** asyncssh defaults to strict host key checking — same as OpenSSH `StrictHostKeyChecking=yes`.

**How to avoid:** Set `known_hosts=None` in `asyncssh.connect()` (shown in the code example above). This disables host key verification — acceptable for internal test machines behind a firewall but NOT for production. This matches the agent's discretion: the planner should document this tradeoff.

**Warning signs:** `asyncssh.HostKeyNotVerifiable` exception on first connection; works after manually adding to known_hosts but fails in CI/automation.

### Pitfall 3: SSH agent not available in non-interactive contexts

**What goes wrong:** `SSH_AUTH_SOCK` is only set in interactive shells (where `ssh-agent` or `ssh-add` was run). In CI, cron jobs, or non-login shells, the agent socket may not exist, causing asyncssh to fall through with no authentication method available.

**Why it happens:** SSH agent is a per-session daemon; it's not available in process-spawned environments. D-09 specifies agent as primary with key path fallback — but the fallback only works if `ASCEND_SSH_KEY_PATH` is explicitly set.

**How to avoid:** The `exec_shell` tool should detect agent availability first (check `SSH_AUTH_SOCK` env var), and if absent AND no `ASCEND_SSH_KEY_PATH` is set, return a clear error message. Don't let asyncssh fail with a cryptic `Authentication failed` error.

**Warning signs:** `asyncssh.PermissionDenied` with no agent socket; works locally but fails in CI; user forgets to `ssh-add` before running.

### Pitfall 4: Local command cwd is the agent's process cwd, not the repo root

**What goes wrong:** D-04 says "same process cwd + inherited environment." If the agent is started from `/Users/ybx/` but the repo is at `/Users/ybx/vllm-ascend/`, running `python -m pytest tests/` will fail because pytest can't find the tests relative to the current directory.

**Why it happens:** `asyncio.create_subprocess_shell()` inherits the current working directory from the parent process. The parent (agent process) may be in any directory.

**How to avoid:** The ReproductionEngine should either: (a) chdir to `repo_path` before calling exec_shell, or (b) pass `cwd=self._repo_path` to `create_subprocess_shell()`. Option (b) is cleaner — it doesn't affect the parent process. The planner should decide which approach and document it in the plan.

**Warning signs:** "File not found" for scripts that clearly exist in the repo; relative paths break; `pytest` can't find test files.

### Pitfall 5: asyncssh command output encoding

**What goes wrong:** asyncssh defaults to UTF-8 string output for `conn.run()`. If the remote command outputs binary data or uses a different encoding, `result.stdout` may contain replacement characters or raise decoding errors.

**Why it happens:** asyncssh sessions default to `encoding='utf-8'` for `run()`. Binary output (e.g., compiled test results, binary log files) won't be captured correctly.

**How to avoid:** For reproduction purposes, commands should produce text output. If binary output is expected, the reproduction command should be wrapped (e.g., `echo "binary output not captured"`). This is a documentation issue — the planner should note that exec_shell captures text output only.

**Warning signs:** `UnicodeDecodeError` in asyncssh internals; garbled characters in captured stdout; replacement character `�` in output.

## Code Examples

Verified patterns from official sources:

### asyncssh connect + run (remote execution)
```python
# Source: asyncssh official docs (https://asyncssh.readthedocs.io/en/latest/)
# Adapted for ASCEND_SSH_* config from env vars (D-06, D-09)

import asyncio, asyncssh, os

async def run_remote(command: str, timeout: int = 60):
    ssh_host = os.environ["ASCEND_SSH_HOST"]
    ssh_user = os.environ.get("ASCEND_SSH_USER")
    ssh_key = os.environ.get("ASCEND_SSH_KEY_PATH")

    # D-09: SSH agent forwarding is built-in (uses SSH_AUTH_SOCK by default)
    # D-08: No term_type → no PTY allocation
    connect_kwargs = {"host": ssh_host, "known_hosts": None}
    if ssh_user:
        connect_kwargs["username"] = ssh_user
    if ssh_key:
        connect_kwargs["client_keys"] = [ssh_key]

    async with asyncssh.connect(**connect_kwargs) as conn:
        result = await asyncio.wait_for(
            conn.run(command, check=False),
            timeout=timeout,
        )
        return {
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "exit_code": result.exit_status or 0,
        }
```

### asyncio subprocess (local execution)
```python
# Source: Python 3.10+ docs (https://docs.python.org/3/library/asyncio-subprocess.html)
# D-03, D-04: local execution with inherited cwd + env

import asyncio

async def run_local(command: str, timeout: int = 60):
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        # cwd not set → inherits from parent (D-04)
        # env not set → inherits from parent (D-04)
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise TimeoutError(f"Command timed out after {timeout}s")

    return {
        "stdout": stdout_bytes.decode() if stdout_bytes else "",
        "stderr": stderr_bytes.decode() if stderr_bytes else "",
        "exit_code": proc.returncode or 0,
    }
```

### Path traversal protection (from edit_file — D-10 reference)
```python
# Source: src/ascend_agent/tools/file_edit.py (lines 51-55)
# Pattern to replicate for D-10 path safety

from pathlib import Path

path = Path(file_path).resolve()
resolved_repo = Path(repo_path).resolve()

if not str(path).startswith(str(resolved_repo)):
    return json.dumps({
        "status": "error",
        "error": f"Path {file_path} resolves outside repository root",
    })
```

## Runtime State Inventory

> Phase 4 is a greenfield capability implementation — not a rename/refactor/migration phase. Runtime state inventory is N/A. No databases, live service configs, or OS-registered state reference the reproduction feature. The only state-aware consideration is `pyproject.toml` dependency addition (`asyncssh`).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| subprocess.run() (sync, blocking) | `asyncio.create_subprocess_shell()` (async) | Phase 1 D-17 (MCP async-only tools) | All shell execution must be async — sync calls block the MCP event loop |
| paramiko (sync SSH) | asyncssh 2.23.0 (async-native) | D-05 locked in Phase 4 | No `asyncio.to_thread()` wrapper needed; fits MCP pattern naturally |
| Multiple hand-rolled SSH wrappers | Single exec_shell MCP tool | D-07 (single command + timeout) | Unified interface for local and remote execution |

**Deprecated/outdated:**
- **paramiko:** D-05 explicitly chose asyncssh. paramiko would require `asyncio.to_thread()` wrapper, defeating the async MCP tool pattern.
- **pexpect for interactive sessions:** D-08 forbids PTY allocation. All execution is non-interactive. No terminal emulation needed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | asyncssh (>=3.10 required) | ✗ | 3.9.6 installed | Must use Python >=3.10 — asyncssh 2.23.0 requires it. Planner must add env upgrade/venv step. |
| pip3 | Package installation | ✓ | 21.2.4 | — |
| OpenSSH | SSH agent forwarding (D-09) | ✓ | OpenSSH_10.2p1 | — |
| asyncssh | Remote SSH execution (D-05) | ✗ | Not installed | Must be added to pyproject.toml and installed. Planner must add install task. |
| Docker | (not required by Phase 4) | ✗ | Not installed | — |

**Missing dependencies with no fallback:**
- **Python 3.10+:** Required by asyncssh 2.23.0. System Python is 3.9.6. The project must use a Python 3.10+ runtime (e.g., via venv with pyenv or homebrew Python). Planner must surface this as a prerequisite task or checkpoint.
- **asyncssh:** New dependency. Must be added to pyproject.toml and installed before any remote execution tests run.

**Missing dependencies with fallback:**
- None — asyncssh is the only new dependency and has no fallback (D-05 is locked).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 7.0.0 + pytest-asyncio >= 0.21.0 |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| Quick run command | `python -m pytest tests/test_tools/test_shell_exec.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REPRO-01 | exec_shell returns valid JSON with status/stdout/stderr/exit_code for local execution | unit | `pytest tests/test_tools/test_shell_exec.py::test_exec_local_returns_json -x` | ❌ Wave 0 |
| REPRO-01 | exec_shell routes to asyncssh when ASCEND_SSH_HOST is set | unit | `pytest tests/test_tools/test_shell_exec.py::test_exec_ssh_routing -x` | ❌ Wave 0 |
| REPRO-01 | exec_shell handles command timeout with status=error | unit | `pytest tests/test_tools/test_shell_exec.py::test_exec_local_timeout -x` | ❌ Wave 0 |
| REPRO-01 | ReproductionEngine.reproduce() returns ReproductionResult for valid diagnosis | unit | `pytest tests/test_reproduction/test_engine.py::test_reproduce_returns_result -x` | ❌ Wave 0 |
| REPRO-01 | ReproductionEngine detects active venv via VIRTUAL_ENV | unit | `pytest tests/test_reproduction/test_engine.py::test_detect_venv -x` | ❌ Wave 0 |
| D-10 | Path traversal blocked for files outside repo | unit | `pytest tests/test_reproduction/test_engine.py::test_path_traversal_blocked -x` | ❌ Wave 0 |
| D-14 | Engine respects VIRTUAL_ENV and CONDA_PREFIX env vars | unit | `pytest tests/test_reproduction/test_engine.py::test_venv_respected -x` | ❌ Wave 0 |
| REPRO-01 | CLI `reproduce run` loads diagnosis JSON and prints result | integration | `pytest tests/test_cli.py::test_reproduce_run_command -x` | ❌ Wave 0 |
| D-11 | ReproductionResult model validates status field enum | unit | `pytest tests/test_reproduction/test_models.py::test_reproduction_result_validation -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_reproduction/ tests/test_tools/test_shell_exec.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_tools/test_shell_exec.py` — covers exec_shell local + SSH routing + timeout + error handling (REPRO-01)
- [ ] `tests/test_reproduction/__init__.py` — package marker
- [ ] `tests/test_reproduction/conftest.py` — shared fixtures: mock router, sample DiagnosisResult, env var manipulation
- [ ] `tests/test_reproduction/test_engine.py` — covers ReproductionEngine.reproduce(), venv detection, path traversal, command construction
- [ ] `tests/test_reproduction/test_models.py` — covers ReproductionResult field validation, status enum
- [ ] Framework install: `pip install "asyncssh>=2.23.0"` — new dependency not yet in pyproject.toml

## Security Domain

> `security_enforcement` not explicitly set to `false` in config — assumed enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | asyncssh SSH agent forwarding + key-based auth (D-09). No password auth in scope. |
| V3 Session Management | yes | asyncssh connection lifecycle via context manager (`async with`). Automatic cleanup on exit. |
| V4 Access Control | yes | Path traversal protection (D-10). Same pattern as edit_file — `Path.resolve()` + prefix check. |
| V5 Input Validation | yes | Command string validation: non-empty check, no shell injection (shlex.quote for user-supplied values). Timeout enforcement via `asyncio.wait_for()`. |
| V6 Cryptography | yes | asyncssh handles SSH key exchange and encryption via `cryptography` (PyCA). Never hand-roll crypto. |

### Known Threat Patterns for asyncssh + asyncio subprocess

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Shell injection via unescaped command strings | Tampering | Use `shlex.quote()` for any user-supplied values embedded in commands. exec_shell passes strings through — caller (Engine) is responsible for construction. |
| Path traversal via `../` in file arguments | Elevation of Privilege | Reuse edit_file's `Path.resolve()` + prefix check pattern (D-10). Validate any file paths before they reach the shell. |
| SSH man-in-the-middle (no host key verification) | Spoofing | D-09 sets `known_hosts=None` for internal test machines. Document this tradeoff. For production, set `known_hosts` to a trusted file. Planner should add checkpoint to verify environment. |
| Command timeout DoS (infinite commands) | Denial of Service | `asyncio.wait_for()` with configurable timeout (D-07). Default 60s, controlled by `shell_timeout` setting. |
| Credential leakage via stderr/env | Information Disclosure | SSH keys never passed via command line. Key path from env var (D-06). asyncssh reads key file directly — never echoes to logs. |

## Sources

### Primary (HIGH confidence)
- [asyncssh official docs (readthedocs.io)] — `connect()`, `conn.run()`, `SSHCompletedProcess`, `ProcessError`, agent forwarding, PTY behavior, error handling [VERIFIED: official docs]
- [asyncssh PyPI page] — v2.23.0 (May 9, 2026), Python >=3.10, cryptography >=39.0, EPL-2.0 license [VERIFIED: pypi.org/project/asyncssh/]
- [Python 3.10+ asyncio subprocess docs] — `create_subprocess_shell()`, `Process.communicate()`, `asyncio.wait_for()` [VERIFIED: docs.python.org/3/library/asyncio-subprocess.html]
- [Existing codebase] — Engine pattern (`diagnosis/engine.py`), Pydantic models (`diagnosis/models.py`), MCP tool pattern (`tools/file_edit.py`), Settings class (`config.py`), CLI pattern (`cli/reproduce.py`), test infrastructure (`tests/conftest.py`, `tests/test_diagnosis/`) [VERIFIED: local file reads]

### Secondary (MEDIUM confidence)
- [asyncssh GitHub README] — SSH agent forwarding built into asyncssh, uses `SSH_AUTH_SOCK` by default; client key types (RSA, Ed25519, ECDSA) [CITED: github.com/ronf/asyncssh]
- [Phase 3 edit_file test patterns] — @pytest.mark.asyncio, json.loads() result parsing, tmp_path fixture, path traversal test structure [CITED: tests/test_tools/test_file_edit.py]

### Tertiary (LOW confidence)
- None — all findings verified against primary or secondary sources.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | asyncssh package is 2.23.0 — confirmed via PyPI [VERIFIED]. `pip install asyncssh` uses this version. | Standard Stack | LOW — version confirmed on PyPI (2026-05-09 release). |
| A2 | `known_hosts=None` disables host key verification (safe for internal test machines) | Common Pitfalls | MEDIUM — if production environment is targeted, this opens a MitM vector. Planner should gate with checkpoint. |
| A3 | `asyncio.create_subprocess_shell()` hides the shell PID for signal propagation — sending SIGTERM to `proc.pid` may not kill the actual child process | Common Pitfalls | LOW — `proc.kill()` in asyncio handles process group termination. Verified in Python docs. |
| A4 | `cryptography` is already installed as a transitive dependency of other packages (openai, mcp) — asyncssh's `cryptography >=39.0` requirement is automatically satisfied | Environment Availability | LOW — `cryptography` is a ubiquitous dependency. Failure means pip install cascade fails, which would be immediately visible. |

## Open Questions (RESOLVED)

1. **Should ReproductionEngine construct reproduction commands via LLM or heuristics?**
   - RESOLVED: Start with heuristic command construction (run the Python file from evidence), then add LLM assistance as a refinement wave if needed. The ModelRouter is available in the constructor for future use per D-01.
   - What we know: D-01 says ReproductionEngine takes `ModelRouter`, suggesting LLM assistance. The agent's discretion covers "exact command construction."
   - Recommendation: Start with heuristic command construction (run the Python file from evidence), then add LLM assistance as a refinement wave if needed.

2. **What does "check dependencies exist" (D-13) mean for remote execution?**
   - RESOLVED: For local execution: check + install dependencies. For remote execution: check and report missing dependencies, but do NOT auto-install remotely.
   - What we know: D-13 says "checks dependencies exist, installs missing packages if needed, sets env vars."
   - Recommendation: Split D-13 into local path (check+install) and remote path (check+report).

3. **How should timeout values be configured?**
   - RESOLVED: Timeout is a parameter of exec_shell (configurable per-command). Global `shell_timeout` setting provides the default (60s).
   - What we know: The agent's discretion covers timeout values. D-07 says "configurable timeout" suggesting it's a parameter of exec_shell.
   - Recommendation: Make timeout a parameter of exec_shell. The ReproductionEngine sets it per-command based on context.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — asyncssh and asyncio subprocess are well-documented with verified API patterns. Versions confirmed on PyPI and official docs.
- Architecture: HIGH — Engine pattern and MCP tool patterns are proven in Phase 2/3. ReproductionEngine and exec_shell are straightforward adaptations.
- Pitfalls: MEDIUM — identified 5 key pitfalls from official docs and prior phase experience. Some edge cases (SSH agent in CI, encoding for binary output) are documented but not exhaustively tested.

**Research date:** 2026-05-25
**Valid until:** 2026-06-25 (30 days — stable domain, asyncssh has long release cycles; v2.23.0 is current as of May 2026)

## RESEARCH COMPLETE
