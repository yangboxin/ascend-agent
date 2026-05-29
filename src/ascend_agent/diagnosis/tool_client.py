from __future__ import annotations

from typing import Protocol

from ascend_agent.tools.code_search import search_code


class DiagnosisToolClient(Protocol):
    async def search_code(self, pattern: str, path: str) -> str:
        """Search code and return text results."""


class LocalToolClient:
    """Default diagnosis tool client backed by in-process tool functions."""

    async def search_code(self, pattern: str, path: str) -> str:
        return await search_code(pattern, path)


def create_tool_client() -> DiagnosisToolClient:
    """Create the tool client used by diagnosis workflows.

    Phase 4/5 wiring keeps local behavior while providing a seam for a future
    MCP-backed client.
    """
    return LocalToolClient()
