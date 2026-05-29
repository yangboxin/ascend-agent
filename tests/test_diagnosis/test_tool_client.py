from __future__ import annotations

from types import SimpleNamespace

import pytest

from ascend_agent.config import Settings
from ascend_agent.diagnosis.tool_client import (
    FallbackToolClient,
    LocalToolClient,
    MCPToolClient,
    create_tool_client,
)


@pytest.mark.asyncio
async def test_mcp_tool_client_prefers_structured_result(monkeypatch):
    client = MCPToolClient(command="python", args=["-m", "ascend_agent.tools.server"])

    async def fake_call_tool(name, arguments):
        assert name == "code_search"
        assert arguments["pattern"] == "foo"
        return SimpleNamespace(
            structuredContent={"result": "src/main.py:1:def foo(): pass"},
            content=[],
        )

    monkeypatch.setattr(client, "_call_tool", fake_call_tool)

    result = await client.search_code("foo", "src")

    assert "main.py" in result


@pytest.mark.asyncio
async def test_fallback_tool_client_uses_fallback_on_primary_error():
    class BrokenClient:
        async def search_code(self, pattern: str, path: str) -> str:
            raise RuntimeError("mcp unavailable")

    class OkClient:
        async def search_code(self, pattern: str, path: str) -> str:
            return f"fallback:{pattern}:{path}"

    client = FallbackToolClient(primary=BrokenClient(), fallback=OkClient())

    result = await client.search_code("foo", "/repo")

    assert result == "fallback:foo:/repo"


def test_create_tool_client_local_backend():
    settings = Settings(
        diagnosis_tool_backend="local",
        mcp_server_command="python -m ascend_agent.tools.server",
    )

    client = create_tool_client(settings=settings)

    assert isinstance(client, LocalToolClient)


def test_create_tool_client_auto_backend_wraps_mcp():
    settings = Settings(
        diagnosis_tool_backend="auto",
        mcp_server_command="python -m ascend_agent.tools.server",
    )

    client = create_tool_client(settings=settings)

    assert isinstance(client, FallbackToolClient)
