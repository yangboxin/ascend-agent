"""Prompt assembly and model invocation for the slim runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ascend_agent.diagnosis.router import ModelRouter, create_router
from ascend_agent.runtime.session import Session
from ascend_agent.runtime.tools import ToolRegistry


class ChatRouter(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> str:
        ...


@dataclass
class QueryEngine:
    """Build the Claude-inspired runtime prompt and call the model."""

    router: ChatRouter
    tools: ToolRegistry

    @classmethod
    def create(cls, provider: str, tools: ToolRegistry) -> "QueryEngine":
        return cls(router=create_router(provider), tools=tools)

    def invoke(self, session: Session, user_input: str) -> str:
        session.add_user_message(user_input)
        messages = [
            {
                "role": "system",
                "content": self._system_prompt(),
            },
            *self._conversation_messages(session),
        ]
        response = self.router.chat(messages)
        session.add_assistant_message(response)
        return response

    def _system_prompt(self) -> str:
        return (
            "You are Ascend Agent, a terminal-native assistant for Ascend NPU "
            "debugging. Use a concise, evidence-based style. When a task needs "
            "diagnosis, reproduction, fixing, or verification, refer to the "
            "available workflow tools and ask for missing inputs before acting.\n\n"
            "Available tools:\n"
            f"{self.tools.describe()}"
        )

    @staticmethod
    def _conversation_messages(session: Session) -> list[dict[str, str]]:
        return [
            {"role": message["role"], "content": message["content"]}
            for message in session.messages
            if message.get("role") in {"user", "assistant", "tool"}
        ]
