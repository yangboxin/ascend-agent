"""Prompt assembly and model invocation for the runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from ascend_agent.providers.router import ChatResponse, create_router
from ascend_agent.runtime.session import Session
from ascend_agent.runtime.tools import ToolRegistry
from ascend_agent.skills.loader import Skill, load_skills, skill_prompt_injection


class ChatRouter(Protocol):
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        ...


@dataclass
class QueryEngine:
    """Build the runtime prompt and call the model provider."""

    router: ChatRouter
    tools: ToolRegistry
    _skills: list[Skill] | None = None

    @classmethod
    def create(cls, provider: str, tools: ToolRegistry) -> "QueryEngine":
        return cls(router=create_router(provider), tools=tools)

    def invoke(self, session: Session, user_input: str) -> str:
        """Compatibility one-shot invocation used by older tests/callers."""
        session.add_user_message(user_input)
        response = self.call_model(session)
        session.add_assistant_message(response.content or "")
        return response.content or ""

    def call_model(self, session: Session) -> ChatResponse:
        messages = self.build_messages(session)
        return self.router.chat(messages, tools=self.tools.tool_schemas())

    def build_messages(self, session: Session) -> list[dict[str, Any]]:
        messages = self._conversation_messages(session)
        messages = _compact_context(messages, max_tokens=8000)
        return [
            {
                "role": "system",
                "content": self.system_prompt(session),
            },
            *messages,
        ]

    def system_prompt(self, session: Session) -> str:
        sections: list[str] = [
            self._identity_section(),
            self._runtime_section(session),
            self._tool_section(),
        ]
        skill_section = self._skill_section()
        if skill_section:
            sections.append(skill_section)
        sections.append(self._json_tool_protocol_section())
        return "\n\n".join(sections)

    def _identity_section(self) -> str:
        return (
            "You are Ascend Agent, a terminal-native assistant for Ascend NPU "
            "debugging. Use concise, evidence-based reasoning."
        )

    def _runtime_section(self, session: Session) -> str:
        return (
            "Runtime context:\n"
            f"- date: {date.today().isoformat()}\n"
            f"- thread_id: {session.thread_id}\n"
            f"- working_dir: {session.working_dir}\n"
            f"- provider: {session.provider}\n"
            f"- model: {session.model or 'unknown'}"
        )

    def _tool_section(self) -> str:
        return "Available tools:\n" + self.tools.describe()

    def _skill_section(self) -> str:
        """Load and format available user-defined skills for the prompt."""
        if self._skills is None:
            try:
                self._skills = load_skills()
            except Exception:
                self._skills = []
        return skill_prompt_injection(self._skills)

    def _json_tool_protocol_section(self) -> str:
        return (
            "Tool protocol:\n"
            "When a tool is needed and native tool calling is unavailable, return "
            'only JSON in the form {"tool_call": {"name": "<tool>", '
            '"arguments": {}}}. After tool results are provided, answer normally. '
            "Do not wrap this JSON in markdown."
        )

    @staticmethod
    def _conversation_messages(session: Session) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for message in session.messages:
            role = message.get("role")
            if role not in {"user", "assistant", "tool"}:
                continue
            item: dict[str, Any] = {"role": role, "content": message.get("content", "")}
            if role == "tool":
                if message.get("name"):
                    item["name"] = message["name"]
                if message.get("tool_call_id"):
                    item["tool_call_id"] = message["tool_call_id"]
            result.append(item)
        return result


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: characters / 4 (close enough for English)."""
    return len(text) // 4


def _compact_context(
    messages: list[dict[str, Any]], max_tokens: int = 8000
) -> list[dict[str, Any]]:
    """Trim old tool results when the estimated token count exceeds max_tokens.

    System message, user messages, and the most recent assistant message are
    always preserved.  Tool results are truncated (summarised) from oldest to
    newest until the total falls below ``max_tokens``.
    """
    estimated = sum(_estimate_tokens(m.get("content", "")) for m in messages)
    if estimated <= max_tokens:
        return messages

    # Find indices of trimmable tool messages
    tool_indices = [
        i for i, m in enumerate(messages) if m.get("role") == "tool"
    ]

    # Trim from oldest, keeping at least the last 4 tool messages
    keep_last = 4
    trim_count = max(0, len(tool_indices) - keep_last)
    for idx in tool_indices[:trim_count]:
        content = messages[idx].get("content", "")
        if len(content) > 200:
            messages[idx]["content"] = content[:200] + "\n... (trimmed)"

    return messages
