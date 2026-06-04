"""Minimal Claude-inspired tool permission policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str = ""
    requires_confirmation: bool = False


@dataclass
class PermissionPolicy:
    """Allow/ask/deny policy over tool names.

    The first matching deny wins, then ask, then allow. This is intentionally
    small; CLI/TUI layers can turn `requires_confirmation` into a prompt.
    """

    allow: list[str] = field(default_factory=lambda: ["code_search", "diagnose_trace", "generate_fixes"])
    ask: list[str] = field(default_factory=lambda: ["reproduce_issue", "verify_fix", "exec_shell", "run_test"])
    deny: list[str] = field(default_factory=list)

    def check(self, tool_name: str) -> PermissionDecision:
        if self._matches(tool_name, self.deny):
            return PermissionDecision(False, f"Tool denied by policy: {tool_name}")
        if self._matches(tool_name, self.ask):
            return PermissionDecision(True, f"Tool requires confirmation: {tool_name}", True)
        if self._matches(tool_name, self.allow):
            return PermissionDecision(True)
        return PermissionDecision(False, f"Tool not allowed by policy: {tool_name}")

    @staticmethod
    def _matches(tool_name: str, patterns: list[str]) -> bool:
        return any(fnmatch(tool_name, pattern) for pattern in patterns)
