from __future__ import annotations

import shlex
from collections.abc import Sequence
from typing import Any, Protocol

from ascend_agent.config import Settings
from ascend_agent.tools.code_search import search_code


class DiagnosisToolClient(Protocol):
    async def search_code(self, pattern: str, path: str) -> str:
        """Search code and return text results."""


class LocalToolClient:
    """Default diagnosis tool client backed by in-process tool functions."""

    async def search_code(self, pattern: str, path: str) -> str:
        return await search_code(pattern, path)


class MCPToolClient:
    """Diagnosis tool client backed by an MCP stdio server."""

    def __init__(
        self,
        command: str,
        args: Sequence[str] | None = None,
        cwd: str | None = None,
    ):
        self._command = command
        self._args = list(args or [])
        self._cwd = cwd

    async def search_code(self, pattern: str, path: str) -> str:
        payload = await self._call_tool(
            "code_search", {"pattern": pattern, "path": path}
        )
        return self._extract_result_text(payload)

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        params = StdioServerParameters(
            command=self._command,
            args=self._args,
            cwd=self._cwd,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return result

    def _extract_result_text(self, result: Any) -> str:
        structured = getattr(result, "structuredContent", None)
        if isinstance(structured, dict):
            value = structured.get("result")
            if isinstance(value, str):
                return value

        content = getattr(result, "content", None)
        if isinstance(content, list):
            for item in content:
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    return text
        raise ValueError("MCP tool result did not include text content")


class FallbackToolClient:
    """Try primary tool client first, then fallback client on failure."""

    def __init__(self, primary: DiagnosisToolClient, fallback: DiagnosisToolClient):
        self._primary = primary
        self._fallback = fallback

    async def search_code(self, pattern: str, path: str) -> str:
        try:
            return await self._primary.search_code(pattern, path)
        except Exception:
            return await self._fallback.search_code(pattern, path)


def create_tool_client(settings: Settings | None = None) -> DiagnosisToolClient:
    """Create the tool client used by diagnosis workflows.

    Behavior is controlled by `ASCEND_DIAGNOSIS_TOOL_BACKEND`:
    - `local`: always use in-process local tools
    - `mcp`: use MCP client with automatic fallback to local on failure
    - `auto` (default): same as `mcp`
    """
    cfg = settings or Settings()
    backend = (cfg.diagnosis_tool_backend or "auto").strip().lower()
    local_client = LocalToolClient()
    if backend == "local":
        return local_client

    command_parts = shlex.split(cfg.mcp_server_command)
    if not command_parts:
        return local_client

    command = command_parts[0]
    args = command_parts[1:]
    mcp_client = MCPToolClient(command=command, args=args)
    return FallbackToolClient(primary=mcp_client, fallback=local_client)
