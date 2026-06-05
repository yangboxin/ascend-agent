"""Conversation session state for the slim runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _sessions_dir() -> Path:
    return Path.home() / ".config" / "ascend-agent" / "sessions"


def list_sessions() -> list[dict[str, Any]]:
    """List saved sessions, newest first."""
    target = _sessions_dir()
    if not target.is_dir():
        return []
    result: list[dict[str, Any]] = []
    for filepath in sorted(target.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(filepath) as f:
                first = json.loads(f.readline())
            result.append({
                "thread_id": filepath.stem,
                "last_updated": datetime.fromtimestamp(filepath.stat().st_mtime, tz=timezone.utc).isoformat(),
                "first_message": first.get("content", "")[:100],
                "message_count": sum(1 for _ in open(filepath)),
            })
        except Exception:
            continue
    return result


@dataclass
class Session:
    """A lightweight runtime session independent of any CLI/TUI."""

    working_dir: Path
    provider: str = "openai"
    model: str | None = None
    thread_id: str = field(default_factory=lambda: uuid4().hex)
    messages: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    transcript: list[dict[str, Any]] = field(default_factory=list)

    # -- message helpers --------------------------------------------------

    def add_user_message(self, content: str) -> None:
        self._append({"role": "user", "content": content})

    def add_assistant_message(
        self, content: str, tool_calls: list[dict[str, Any]] | None = None
    ) -> None:
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self._append(msg)

    def add_tool_message(
        self, name: str, content: str, tool_call_id: str = ""
    ) -> None:
        msg: dict[str, Any] = {"role": "tool", "content": content, "name": name}
        if tool_call_id:
            msg["tool_call_id"] = tool_call_id
        self._append(msg)

    def _append(self, message: dict[str, Any]) -> None:
        self.messages.append(message)
        self.transcript.append(
            {
                **message,
                "thread_id": self.thread_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    # -- persistence ------------------------------------------------------

    def save(self) -> Path:
        """Persist the transcript as JSONL and return the file path."""
        target = _sessions_dir()
        target.mkdir(parents=True, exist_ok=True)
        filepath = target / f"{self.thread_id}.jsonl"
        with open(filepath, "w") as f:
            for entry in self.transcript:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return filepath

    def fork(self, preserve_messages: bool = True) -> "Session":
        """Create a new session forked from this one.

        Args:
            preserve_messages: If True, copy previous messages into the
                new session for context continuity.
        """
        child = Session(
            working_dir=self.working_dir,
            provider=self.provider,
            model=self.model,
            thread_id=uuid4().hex,
            artifacts=dict(self.artifacts),
            metadata={**self.metadata, "forked_from": self.thread_id},
        )
        if preserve_messages:
            child.messages = list(self.messages)
            child.transcript = list(self.transcript)
        return child

    @classmethod
    def load(cls, thread_id: str, working_dir: str | Path | None = None) -> "Session":
        """Reconstitute a session from its JSONL transcript file.

        Args:
            thread_id: The session's thread ID (filename without .jsonl).
            working_dir: Override working_dir (defaults to cwd).

        Returns:
            A Session with messages and transcript replayed.

        Raises:
            FileNotFoundError: If no transcript exists for this thread_id.
        """
        filepath = _sessions_dir() / f"{thread_id}.jsonl"
        if not filepath.exists():
            raise FileNotFoundError(f"No saved session for thread_id {thread_id}")

        wd = Path(working_dir) if working_dir else Path.cwd()
        session = cls(working_dir=wd, thread_id=thread_id)
        with open(filepath) as f:
            for line in f:
                entry = json.loads(line.strip())
                session.transcript.append(entry)
                role = entry.get("role")
                if role in ("user", "assistant", "tool"):
                    msg: dict[str, Any] = {"role": role, "content": entry.get("content", "")}
                    if role == "assistant" and entry.get("tool_calls"):
                        msg["tool_calls"] = entry["tool_calls"]
                    if role == "tool" and entry.get("name"):
                        msg["name"] = entry["name"]
                    if role == "tool" and entry.get("tool_call_id"):
                        msg["tool_call_id"] = entry["tool_call_id"]
                    session.messages.append(msg)
        return session
