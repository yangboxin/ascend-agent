import asyncio
import json
import logging
import os

from mcp.server.fastmcp import Context

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60


async def exec_shell(command: str, timeout: int = DEFAULT_TIMEOUT, ctx: Context | None = None) -> str:
    """Execute a shell command locally or via SSH. Returns JSON with status, stdout, stderr, exit_code.

    Routes to _exec_remote if ASCEND_SSH_HOST env var is set, otherwise _exec_local.
    """
    ssh_host = os.environ.get("ASCEND_SSH_HOST", "").strip()
    if ssh_host:
        logger.info("Routing command to remote SSH host: %s", ssh_host)
        return await _exec_remote(command, timeout, ctx)
    return await _exec_local(command, timeout, ctx)


async def _exec_local(command: str, timeout: int, ctx: Context | None = None) -> str:
    """Execute command via local subprocess (D-03, D-04)."""
    try:
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
                "stderr": f"timed out after {timeout}s",
                "exit_code": -1,
            })

        stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        exit_code = proc.returncode if proc.returncode is not None else -1

        status = "success" if exit_code == 0 else "fail"

        if ctx is not None:
            await ctx.info(f"Local exec: exit_code={exit_code}, status={status}")

        return json.dumps({
            "status": status,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
        })
    except Exception as e:
        logger.exception("Local command execution failed: %s", command)
        return json.dumps({
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
        })


async def _exec_remote(command: str, timeout: int, ctx: Context | None = None) -> str:
    """Execute command via SSH using asyncssh (D-05, D-06, D-07, D-08, D-09).

    asyncssh is imported inside the function body to avoid ImportError
    when only local execution is used and asyncssh is not installed.
    """
    import asyncssh

    ssh_host = os.environ.get("ASCEND_SSH_HOST", "").strip()
    ssh_user = os.environ.get("ASCEND_SSH_USER", "").strip()
    ssh_key_path = os.environ.get("ASCEND_SSH_KEY_PATH", "").strip()

    if not ssh_host:
        return json.dumps({
            "status": "error",
            "stdout": "",
            "stderr": "ASCEND_SSH_HOST is not set — remote execution requires a target host",
            "exit_code": -1,
        })

    ssh_auth_sock = os.environ.get("SSH_AUTH_SOCK")
    if not ssh_auth_sock and not ssh_key_path:
        return json.dumps({
            "status": "error",
            "stdout": "",
            "stderr": "No SSH authentication method available — set ASCEND_SSH_KEY_PATH or start ssh-agent",
            "exit_code": -1,
        })

    connect_kwargs = {"host": ssh_host, "known_hosts": None}
    if ssh_user:
        connect_kwargs["username"] = ssh_user
    if ssh_key_path:
        connect_kwargs["client_keys"] = [ssh_key_path]

    if ctx is not None:
        await ctx.info(f"Connecting to SSH host: {ssh_host}")

    try:
        async with asyncssh.connect(**connect_kwargs) as conn:
            result = await asyncio.wait_for(
                conn.run(command, check=False), timeout=timeout
            )
            exit_code = result.exit_status if result.exit_status is not None else 0
            status = "success" if exit_code == 0 else "fail"

            if ctx is not None:
                await ctx.info(f"Remote exec: exit_code={exit_code}, status={status}")

            return json.dumps({
                "status": status,
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
                "exit_code": exit_code,
            })
    except asyncssh.ProcessError as e:
        logger.warning("Remote command failed: %s", e)
        return json.dumps({
            "status": "fail",
            "stdout": "",
            "stderr": e.stderr or str(e),
            "exit_code": e.exit_status if e.exit_status is not None else -1,
        })
    except asyncssh.Error as e:
        logger.error("SSH connection error: %s", e)
        return json.dumps({
            "status": "error",
            "stdout": "",
            "stderr": f"SSH error: {e}",
            "exit_code": -1,
        })
    except asyncio.TimeoutError:
        return json.dumps({
            "status": "error",
            "stdout": "",
            "stderr": f"SSH command timed out after {timeout}s",
            "exit_code": -1,
        })
    except Exception as e:
        logger.exception("Remote command execution failed: %s", command)
        return json.dumps({
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
        })
