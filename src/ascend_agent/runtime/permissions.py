"""Mode-aware runtime permission checks."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Literal

PermissionMode = Literal["default", "plan", "accept_edits", "bypass"]


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str = ""
    requires_confirmation: bool = False


@dataclass(frozen=True)
class PermissionRule:
    action: Literal["allow", "ask", "deny"]
    tool: str | None = None
    path: str | None = None
    command_pattern: str | None = None

    def matches(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        if self.tool is not None and not fnmatch(tool_name, self.tool):
            return False
        if self.path is not None:
            candidate = _argument_path(arguments)
            if candidate is None or not fnmatch(candidate, self.path):
                return False
        if self.command_pattern is not None:
            command = str(arguments.get("command", ""))
            if not re.search(self.command_pattern, command):
                return False
        return True


@dataclass
class PermissionContext:
    """Check tool requests using a Claude-inspired mode policy."""

    mode: PermissionMode = "default"
    working_dir: Path | None = None
    rules: list[PermissionRule] = field(default_factory=list)

    def check(self, tool: Any, arguments: dict[str, Any] | None = None) -> PermissionDecision:
        arguments = arguments or {}
        tool_name = tool if isinstance(tool, str) else tool.name

        rule_decision = self._check_rules(tool_name, arguments)
        if rule_decision is not None:
            return rule_decision

        if self.mode == "bypass":
            return PermissionDecision(True)

        read_only = _is_read_only(tool, tool_name)
        destructive = bool(getattr(tool, "is_destructive", False))
        path_decision = self._check_path(tool, arguments)
        if path_decision is not None:
            return path_decision

        if self.mode == "plan":
            if read_only:
                return PermissionDecision(True)
            return PermissionDecision(False, f"Tool denied in plan mode: {tool_name}")

        if self.mode == "accept_edits":
            if read_only:
                return PermissionDecision(True)
            if tool_name == "edit_file" and not destructive:
                return PermissionDecision(True)
            if tool_name == "edit_file":
                return PermissionDecision(True)
            if tool_name in {"exec_shell", "run_test", "reproduce_issue", "verify_fix"}:
                return PermissionDecision(
                    True,
                    f"Tool requires confirmation in accept_edits mode: {tool_name}",
                    True,
                )
            return PermissionDecision(False, f"Tool not allowed by policy: {tool_name}")

        if read_only:
            return PermissionDecision(True)
        if tool_name in {
            "edit_file",
            "exec_shell",
            "run_test",
            "reproduce_issue",
            "verify_fix",
        }:
            return PermissionDecision(
                True,
                f"Tool requires confirmation: {tool_name}",
                True,
            )
        return PermissionDecision(False, f"Tool not allowed by policy: {tool_name}")

    def _check_rules(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> PermissionDecision | None:
        for action in ("deny", "ask", "allow"):
            for rule in self.rules:
                if rule.action != action or not rule.matches(tool_name, arguments):
                    continue
                if action == "deny":
                    return PermissionDecision(False, f"Tool denied by rule: {tool_name}")
                if action == "ask":
                    return PermissionDecision(
                        True, f"Tool requires confirmation by rule: {tool_name}", True
                    )
                return PermissionDecision(True)
        return None

    def _check_path(self, tool: Any, arguments: dict[str, Any]) -> PermissionDecision | None:
        if self.working_dir is None:
            return None
        if isinstance(tool, str) or not hasattr(tool, "get_path"):
            candidate = _argument_path(arguments)
        else:
            candidate = tool.get_path(arguments)
        if candidate is None:
            return None

        root = self.working_dir.resolve()
        path = Path(candidate)
        if not path.is_absolute():
            path = root / path
        resolved = path.resolve()
        try:
            common = os.path.commonpath([str(root), str(resolved)])
        except ValueError:
            common = ""
        if common != str(root):
            return PermissionDecision(
                False,
                f"Path is outside working directory: {candidate}",
            )
        return None


@dataclass
class PermissionPolicy:
    """Compatibility facade over the mode-aware permission context.

    Existing code can keep passing allow/ask/deny glob lists over tool names.
    New runtime code should prefer `PermissionContext`.
    """

    allow: list[str] = field(default_factory=lambda: ["code_search", "diagnose_trace", "generate_fixes"])
    ask: list[str] = field(default_factory=lambda: ["reproduce_issue", "verify_fix", "exec_shell", "run_test"])
    deny: list[str] = field(default_factory=list)
    mode: PermissionMode | None = None
    working_dir: Path | None = None

    def check(
        self, tool: Any, arguments: dict[str, Any] | None = None
    ) -> PermissionDecision:
        tool_name = tool if isinstance(tool, str) else tool.name
        if self._matches(tool_name, self.deny):
            return PermissionDecision(False, f"Tool denied by policy: {tool_name}")
        if self._matches(tool_name, self.ask):
            return PermissionDecision(True, f"Tool requires confirmation: {tool_name}", True)
        if self._matches(tool_name, self.allow):
            return PermissionDecision(True)
        if self.mode is not None:
            return PermissionContext(
                mode=self.mode,
                working_dir=self.working_dir,
            ).check(tool, arguments)
        return PermissionDecision(False, f"Tool not allowed by policy: {tool_name}")

    @staticmethod
    def _matches(tool_name: str, patterns: list[str]) -> bool:
        return any(fnmatch(tool_name, pattern) for pattern in patterns)


def default_policy_for_mode(
    mode: PermissionMode = "default",
    working_dir: Path | None = None,
) -> PermissionContext:
    return PermissionContext(mode=mode, working_dir=working_dir)


def _is_read_only(tool: Any, tool_name: str) -> bool:
    if not isinstance(tool, str):
        return bool(getattr(tool, "is_read_only", False))
    return tool_name in {"code_search", "diagnose_trace", "generate_fixes"}


def _argument_path(arguments: dict[str, Any]) -> str | None:
    for key in ("file_path", "path", "repo_path", "working_dir", "cwd"):
        value = arguments.get(key)
        if value:
            return str(value)
    return None
