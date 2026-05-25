import json
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_exec_local_returns_json():
    from ascend_agent.tools.shell_exec import exec_shell

    result = json.loads(await exec_shell(command="echo hello", timeout=10))
    assert "status" in result
    assert "stdout" in result
    assert "stderr" in result
    assert "exit_code" in result
    assert result["status"] in ("success", "fail", "error")


@pytest.mark.asyncio
async def test_exec_local_success():
    from ascend_agent.tools.shell_exec import exec_shell

    result = json.loads(await exec_shell(command="echo hello", timeout=10))
    assert result["status"] == "success"
    assert "hello" in result["stdout"]
    assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_exec_local_failure():
    from ascend_agent.tools.shell_exec import exec_shell

    result = json.loads(await exec_shell(command="exit 1", timeout=10))
    assert result["status"] == "fail"
    assert result["exit_code"] == 1


@pytest.mark.asyncio
async def test_exec_local_timeout():
    from ascend_agent.tools.shell_exec import exec_shell

    result = json.loads(await exec_shell(command="sleep 30", timeout=1))
    assert result["status"] == "error"
    assert "timed out" in result["stderr"].lower()
    assert result["exit_code"] == -1


@pytest.mark.asyncio
async def test_exec_ssh_routing(monkeypatch):
    from ascend_agent.tools.shell_exec import exec_shell

    monkeypatch.setenv("ASCEND_SSH_HOST", "testhost.example.com")
    monkeypatch.setenv("ASCEND_SSH_USER", "testuser")

    with patch(
        "ascend_agent.tools.shell_exec._exec_remote", new_callable=AsyncMock
    ) as mock_remote:
        mock_remote.return_value = json.dumps({
            "status": "success",
            "stdout": "remote ok",
            "stderr": "",
            "exit_code": 0,
        })
        result = json.loads(await exec_shell(command="echo test", timeout=10))
        mock_remote.assert_called_once()
        assert result["status"] == "success"
        assert result["stdout"] == "remote ok"


@pytest.mark.asyncio
async def test_exec_invalid_command():
    from ascend_agent.tools.shell_exec import exec_shell

    result = json.loads(
        await exec_shell(command="nonexistent_command_xyz", timeout=10)
    )
    assert result["status"] == "error"
