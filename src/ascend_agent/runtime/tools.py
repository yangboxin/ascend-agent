"""Runtime tool registry wrapping the existing tool catalog."""

from __future__ import annotations

import inspect
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ascend_agent.runtime.permissions import PermissionContext, PermissionPolicy
from ascend_agent.tools.catalog import ToolSpec, list_tools

_PATH_ARGUMENTS = {
    "code_search": ("path",),
    "edit_file": ("file_path",),
}

_WORKING_DIR_ARGUMENTS = {
    "edit_file": {"repo_path": "root"},
    "exec_shell": {"cwd": "root"},
    "diagnose_trace": {"working_dir": "root"},
    "generate_fixes": {"working_dir": "root"},
    "reproduce_issue": {"working_dir": "root"},
    "verify_fix": {"working_dir": "root"},
}


@dataclass
class ToolRegistry:
    tools: dict[str, ToolSpec]
    permissions: PermissionContext | PermissionPolicy
    working_dir: Path | None = None

    @classmethod
    def from_patterns(
        cls,
        patterns: list[str] | None = None,
        permissions: PermissionContext | PermissionPolicy | None = None,
        working_dir: Path | None = None,
    ) -> "ToolRegistry":
        return cls(
            tools={tool.name: tool for tool in list_tools(patterns)},
            permissions=permissions or PermissionPolicy(),
            working_dir=working_dir,
        )

    def list(self) -> list[ToolSpec]:
        return list(self.tools.values())

    def get(self, name: str) -> ToolSpec:
        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")
        return self.tools[name]

    def describe(self) -> str:
        lines = []
        for tool in self.tools.values():
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)

    def tool_schemas(self) -> list[dict[str, Any]]:
        """Return tool definitions in OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema or {"type": "object", "properties": {}},
                },
            }
            for tool in self.tools.values()
        ]

    async def run(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        arguments = dict(arguments or {})
        tool = self.get(name)
        decision = self.permissions.check(tool, arguments)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        if decision.requires_confirmation:
            raise PermissionError(decision.reason)

        func = self._bound_func(tool)
        result = func(**arguments)
        if inspect.isawaitable(result):
            result = await result
        return tool.format_result(str(result))

    def _bound_func(self, tool: ToolSpec):
        if self.working_dir is None:
            return tool.func
        root = self.working_dir.resolve()

        async def bound_tool(**kwargs: Any) -> str:
            for argument in _PATH_ARGUMENTS.get(tool.name, ()):
                if argument in kwargs:
                    kwargs[argument] = str(_resolve_inside_root(root, kwargs[argument]))
            for argument, source in _WORKING_DIR_ARGUMENTS.get(tool.name, {}).items():
                kwargs.setdefault(argument, str(root) if source == "root" else ".")
            result = tool.func(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            return str(result)

        return bound_tool


def _resolve_inside_root(root: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        common = os.path.commonpath([str(root), str(resolved)])
    except ValueError as exc:
        raise ValueError(f"Path {value!r} is outside working directory {root}") from exc
    if common != str(root):
        raise ValueError(f"Path {value!r} is outside working directory {root}")
    return resolved
