"""Runtime tool registry wrapping the existing tool catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ascend_agent.runtime.permissions import PermissionPolicy
from ascend_agent.tools.catalog import ToolSpec, list_tools


@dataclass
class ToolRegistry:
    tools: dict[str, ToolSpec]
    permissions: PermissionPolicy

    @classmethod
    def from_patterns(
        cls,
        patterns: list[str] | None = None,
        permissions: PermissionPolicy | None = None,
    ) -> "ToolRegistry":
        return cls(
            tools={tool.name: tool for tool in list_tools(patterns)},
            permissions=permissions or PermissionPolicy(),
        )

    def describe(self) -> str:
        lines = []
        for tool in self.tools.values():
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)

    async def run(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")
        decision = self.permissions.check(name)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        if decision.requires_confirmation:
            raise PermissionError(decision.reason)
        tool = self.tools[name]
        result = tool.func(**(arguments or {}))
        if hasattr(result, "__await__"):
            result = await result
        return str(result)
