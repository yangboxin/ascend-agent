"""Conversation session state for the slim runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class Session:
    """A lightweight runtime session independent of any CLI/TUI."""

    working_dir: Path
    provider: str = "openai"
    model: str | None = None
    thread_id: str = field(default_factory=lambda: uuid4().hex)
    messages: list[dict[str, str]] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_message(self, name: str, content: str) -> None:
        self.messages.append({"role": "tool", "content": content, "name": name})
