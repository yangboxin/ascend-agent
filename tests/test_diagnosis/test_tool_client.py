from __future__ import annotations

import io
import sys
import types
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


@pytest.mark.asyncio
async def test_fallback_tool_client_reports_primary_error_to_errlog():
    class BrokenClient:
        async def search_code(self, pattern: str, path: str) -> str:
            raise RuntimeError("mcp unavailable")

    class OkClient:
        async def search_code(self, pattern: str, path: str) -> str:
            return "fallback result"

    errlog = io.StringIO()
    client = FallbackToolClient(
        primary=BrokenClient(),
        fallback=OkClient(),
        errlog=errlog,
    )

    result = await client.search_code("foo", "/repo")

    assert result == "fallback result"
    assert "MCP search failed" in errlog.getvalue()
    assert "mcp unavailable" in errlog.getvalue()


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


def test_create_tool_client_rejects_unknown_backend():
    settings = Settings(
        diagnosis_tool_backend="unknown",
        mcp_server_command="python -m ascend_agent.tools.server",
    )

    with pytest.raises(ValueError, match="Diagnosis tool backend"):
        create_tool_client(settings=settings)


def test_mcp_tool_client_passes_errlog(monkeypatch):
    captured = {}
    errlog = io.StringIO()
    client = MCPToolClient(command="python", errlog=errlog)

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def initialize(self):
            return None

        async def call_tool(self, name, arguments):
            return SimpleNamespace(structuredContent={"result": "ok"}, content=[])

    class FakeStdio:
        async def __aenter__(self):
            return object(), object()

        async def __aexit__(self, *args):
            return None

    def fake_stdio_client(params, errlog=None):
        captured["errlog"] = errlog
        return FakeStdio()

    mcp_client = types.ModuleType("mcp.client")
    mcp_session = types.ModuleType("mcp.client.session")
    mcp_stdio = types.ModuleType("mcp.client.stdio")
    mcp_session.ClientSession = lambda read, write: FakeSession()
    mcp_stdio.StdioServerParameters = lambda **kwargs: SimpleNamespace(**kwargs)
    mcp_stdio.stdio_client = fake_stdio_client
    monkeypatch.setitem(sys.modules, "mcp.client", mcp_client)
    monkeypatch.setitem(sys.modules, "mcp.client.session", mcp_session)
    monkeypatch.setitem(sys.modules, "mcp.client.stdio", mcp_stdio)

    import asyncio
    asyncio.run(client.search_code("x", "."))

    assert captured["errlog"] is errlog


def test_create_tool_client_resolves_default_python_to_current_executable(monkeypatch):
    captured = {}

    class FakeMCPToolClient:
        def __init__(self, command, args=None, errlog=None):
            captured["command"] = command
            captured["args"] = args

        async def search_code(self, pattern: str, path: str) -> str:
            return "ok"

    monkeypatch.setattr("ascend_agent.diagnosis.tool_client.MCPToolClient", FakeMCPToolClient)
    settings = Settings(
        diagnosis_tool_backend="auto",
        mcp_server_command="python -m ascend_agent.tools.server",
    )

    client = create_tool_client(settings=settings)

    assert isinstance(client, FallbackToolClient)
    assert captured["command"] == sys.executable
    assert captured["args"] == ["-m", "ascend_agent.tools.server"]
