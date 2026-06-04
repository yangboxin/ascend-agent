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

    if tool.name == "code_search":
        async def code_search_bound(pattern: str, path: str = ".") -> str:
            """Search files inside the agent working directory."""
            safe_path = _resolve_inside_root(root, path)
            return await search_code(pattern=pattern, path=str(safe_path))

        return code_search_bound

    if tool.name == "edit_file":
        async def edit_file_bound(file_path: str, operations: list[dict]) -> str:
            """Edit one file inside the agent working directory."""
            safe_path = _resolve_inside_root(root, file_path)
            return await edit_file(file_path=str(safe_path), operations=operations, repo_path=str(root))

        return edit_file_bound

    if tool.name == "exec_shell":
        async def exec_shell_bound(command: str, timeout: int = 60) -> str:
            """Execute a shell command from the agent working directory."""
            return await exec_shell(command=command, timeout=timeout, cwd=str(root))

        return exec_shell_bound

    if tool.name == "diagnose_trace":
        async def diagnose_trace_bound(
            repo_path: str = ".",
            trace_text: str | None = None,
            trace_file: str | None = None,
            provider: str = "openai",
        ) -> str:
            """Diagnose a trace inside the agent working directory."""
            return await diagnose_trace(
                repo_path=repo_path,
                trace_text=trace_text,
                trace_file=trace_file,
                provider=provider,
                working_dir=str(root),
            )

        return diagnose_trace_bound

    if tool.name == "generate_fixes":
        async def generate_fixes_bound(
            diagnosis_json: str,
            repo_path: str = ".",
            provider: str = "openai",
        ) -> str:
            """Generate fixes for diagnosis JSON inside the agent working directory."""
            return await generate_fixes(
                diagnosis_json=diagnosis_json,
                repo_path=repo_path,
                provider=provider,
                working_dir=str(root),
            )

        return generate_fixes_bound

    if tool.name == "reproduce_issue":
        async def reproduce_issue_bound(
            diagnosis_json: str,
            repo_path: str = ".",
            trace_text: str | None = None,
            provider: str = "openai",
        ) -> str:
            """Reproduce a diagnosis inside the agent working directory."""
            return await reproduce_issue(
                diagnosis_json=diagnosis_json,
                repo_path=repo_path,
                trace_text=trace_text,
                provider=provider,
                working_dir=str(root),
            )

        return reproduce_issue_bound

    if tool.name == "verify_fix":
        async def verify_fix_bound(
            reproduction_json: str,
            repo_path: str = ".",
            provider: str = "openai",
            timeout: int = 300,
        ) -> str:
            """Verify a fix inside the agent working directory."""
            return await verify_fix(
                reproduction_json=reproduction_json,
                repo_path=repo_path,
                provider=provider,
                timeout=timeout,
                working_dir=str(root),
            )

        return verify_fix_bound

    return tool.func


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
