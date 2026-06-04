"""Runtime tool catalog for platform agents."""

from __future__ import annotations

import inspect
import os
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Awaitable, Callable

from ascend_agent.tools.code_search import search_code
from ascend_agent.tools.file_edit import edit_file
from ascend_agent.tools.shell_exec import exec_shell
from ascend_agent.tools.test_runner import run_test
from ascend_agent.tools.workflows import diagnose_trace, generate_fixes, reproduce_issue, verify_fix

ToolCallable = Callable[..., Awaitable[str] | str]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    category: str
    module: str
    func: ToolCallable


BUILTIN_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="code_search",
        description="Search source and config files using ripgrep-compatible regex.",
        category="impl",
        module="ascend",
        func=search_code,
    ),
    ToolSpec(
        name="edit_file",
        description="Apply atomic search-and-replace file edits with backup creation.",
        category="impl",
        module="ascend",
        func=edit_file,
    ),
    ToolSpec(
        name="exec_shell",
        description="Run a non-interactive shell command locally or via configured SSH.",
        category="impl",
        module="ascend",
        func=exec_shell,
    ),
    ToolSpec(
        name="run_test",
        description="Run relevant tests for a reproduction result and return verification JSON.",
        category="impl",
        module="ascend",
        func=run_test,
    ),
    ToolSpec(
        name="diagnose_trace",
        description="Run the diagnosis workflow on a repo and trace, returning DiagnosisResult JSON.",
        category="workflow",
        module="ascend",
        func=diagnose_trace,
    ),
    ToolSpec(
        name="generate_fixes",
        description="Generate search-and-replace fix suggestions from diagnosis JSON.",
        category="workflow",
        module="ascend",
        func=generate_fixes,
    ),
    ToolSpec(
        name="reproduce_issue",
        description="Reproduce a diagnosed issue using existing evidence and generated bad-case tests.",
        category="workflow",
        module="ascend",
        func=reproduce_issue,
    ),
    ToolSpec(
        name="verify_fix",
        description="Verify a reproduction result with focused tests, returning VerificationResult JSON.",
        category="workflow",
        module="ascend",
        func=verify_fix,
    ),
)

_PATH_ARGUMENTS = {
    "code_search": ("path",),
    "edit_file": ("file_path",),
}

_WORKING_DIR_ARGUMENTS = {
    "edit_file": {"repo_path": "repo"},
    "exec_shell": {"cwd": "root"},
    "diagnose_trace": {"working_dir": "root"},
    "generate_fixes": {"working_dir": "root"},
    "reproduce_issue": {"working_dir": "root"},
    "verify_fix": {"working_dir": "root"},
}


def list_tools(patterns: list[str] | None = None) -> list[ToolSpec]:
    return [tool for tool in BUILTIN_TOOLS if _matches_patterns(tool, patterns)]


async def fetch_tools() -> list[dict[str, str]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "category": tool.category,
            "module": tool.module,
        }
        for tool in BUILTIN_TOOLS
    ]


async def get_tool(name: str) -> dict[str, str] | None:
    for tool in BUILTIN_TOOLS:
        if tool.name == name:
            return {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "module": tool.module,
            }
    return None


async def run_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
    for tool in BUILTIN_TOOLS:
        if tool.name != name:
            continue
        result = tool.func(**(arguments or {}))
        if inspect.isawaitable(result):
            return await result
        return str(result)
    raise ValueError(f"Unknown tool: {name}")


def to_langchain_tools(tools: list[ToolSpec]) -> list[Any]:
    return to_langchain_tools_for_workdir(tools, None)


def to_langchain_tools_for_workdir(tools: list[ToolSpec], working_dir: Path | None) -> list[Any]:
    try:
        from langchain_core.tools import StructuredTool
    except Exception:
        return tools

    converted = []
    for tool in tools:
        func = _bind_to_workdir(tool, working_dir)
        converted.append(
            StructuredTool.from_function(
                coroutine=func if inspect.iscoroutinefunction(func) else None,
                func=None if inspect.iscoroutinefunction(func) else func,
                name=tool.name,
                description=tool.description,
            )
        )
    return converted


def _bind_to_workdir(tool: ToolSpec, working_dir: Path | None) -> ToolCallable:
    if working_dir is None:
        return tool.func
    root = working_dir.resolve()

    async def bound_tool(**kwargs: Any) -> str:
        for argument in _PATH_ARGUMENTS.get(tool.name, ()):
            if argument in kwargs:
                kwargs[argument] = str(_resolve_inside_root(root, kwargs[argument]))
        for argument, source in _WORKING_DIR_ARGUMENTS.get(tool.name, {}).items():
            kwargs.setdefault(argument, str(root) if source == "root" else ".")
        result = tool.func(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return str(result)

    bound_tool.__name__ = f"{tool.name}_bound"
    bound_tool.__doc__ = f"{tool.description} Scoped to the agent working directory."
    return bound_tool


def _resolve_inside_root(root: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        os.path.commonpath([str(root), str(resolved)])
    except ValueError as exc:
        raise ValueError(f"Path {value!r} is outside working directory {root}") from exc
    if os.path.commonpath([str(root), str(resolved)]) != str(root):
        raise ValueError(f"Path {value!r} is outside working directory {root}")
    return resolved


def _matches_patterns(tool: ToolSpec, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    positives = [p for p in patterns if p and not p.startswith("!")]
    negatives = [p[1:] for p in patterns if p.startswith("!")]
    identity = f"{tool.category}:{tool.module}:{tool.name}"
    positive_match = not positives or any(fnmatch(identity, pattern) for pattern in positives)
    negative_match = any(fnmatch(identity, pattern) for pattern in negatives)
    return positive_match and not negative_match
