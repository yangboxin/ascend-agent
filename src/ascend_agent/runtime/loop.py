"""Multi-turn agent loop with native tool calling and async streaming.

The agent loop runs as an async generator, yielding typed events so that
consumers (REPL, headless mode) can render streaming tokens, tool calls,
and final responses in real time.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Literal, Union

from ascend_agent.providers.router import ChatResponse
from ascend_agent.runtime.query_engine import QueryEngine
from ascend_agent.runtime.session import Session

# Event types yielded by the async generator
LoopEvent = tuple[str, Any]
"""A single agent-loop event: (event_type, payload).

Event types:
  user_message  — str: the user's input
  assistant_delta — str: a streaming token from the LLM
  assistant_message — str: a complete (non-streamed) assistant response
  tool_call – dict: a tool call being executed {"name": ..., "arguments": ...}
  tool_result – dict: tool execution result {"tool": ..., "result": ...}
  final – str: the final response text after all tool calls complete
  error – str: an error message
  max_turns – str: loop exceeded max_turns (auto-recovery not attempted)
"""


@dataclass
class AgentLoop:
    query_engine: QueryEngine
    max_turns: int = 8

    async def run_turn(
        self, session: Session, user_input: str
    ) -> AsyncGenerator[LoopEvent, None]:
        """Run a multi-turn agent loop, yielding events as they occur.

        Args:
            session: The conversation session.
            user_input: The user's latest message.

        Yields:
            LoopEvent tuples for streaming/display consumers.
        """
        session.add_user_message(user_input)
        yield ("user_message", user_input)

        for turn in range(1, self.max_turns + 1):
            response: ChatResponse = self.query_engine.call_model(session)

            # Prefer native tool_calls, fall back to JSON text parsing
            tool_calls = _native_tool_calls(response) or _extract_json_tool_calls(
                response.content
            )

            if not tool_calls:
                if response.content:
                    session.add_assistant_message(response.content)
                yield ("final", response.content)
                return

            if response.content:
                session.add_assistant_message(
                    response.content, tool_calls=response.tool_calls
                )
                yield ("assistant_message", response.content)

            for tool_call in tool_calls:
                tool_name = str(tool_call.get("name", ""))
                tool_call_id = str(tool_call.get("id", ""))
                arguments = tool_call.get("arguments") or {}
                yield ("tool_call", {"name": tool_name, "arguments": arguments})

                try:
                    result = await self.query_engine.tools.run(tool_name, arguments)
                except Exception as exc:
                    result = json.dumps(
                        {
                            "status": "error",
                            "tool": tool_name or "unknown",
                            "error": str(exc),
                        }
                    )
                    session.add_tool_message(
                        tool_name or "unknown", result, tool_call_id=tool_call_id
                    )
                    yield ("tool_result", {"tool": tool_name, "result": result, "error": str(exc)})
                    yield ("error", f"Tool '{tool_name}' failed: {exc}")
                    # Continue to next tool call — the LLM will see this error
                    # result on the next turn and can try a different approach.
                    continue

                session.add_tool_message(tool_name, result, tool_call_id=tool_call_id)
                yield ("tool_result", {"tool": tool_name, "result": result})

        # Max turns exhausted
        msg = f"Agent loop stopped after {self.max_turns} turns."
        session.add_assistant_message(msg)
        yield ("max_turns", msg)


async def run_turn_sync(session: Session, user_input: str, loop: AgentLoop) -> str:
    """Convenience: run loop to completion and return the final text.

    This is the synchronous-compatible wrapper for callers that don't
    care about streaming events (e.g., tests, headless mode).
    """
    final = ""
    async for event_type, payload in loop.run_turn(session, user_input):
        if event_type in ("final", "error", "max_turns"):
            final = str(payload)
    return final


# ---------------------------------------------------------------------------
# Tool-call extraction helpers
# ---------------------------------------------------------------------------


def _native_tool_calls(response: ChatResponse) -> list[dict[str, Any]] | None:
    """Extract tool calls from the native ChatResponse format."""
    if not response.tool_calls:
        return None
    result: list[dict[str, Any]] = []
    for tc in response.tool_calls:
        func = tc.get("function", {})
        arguments = func.get("arguments", "{}")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        result.append({
            "name": func.get("name", ""),
            "arguments": arguments,
            "id": tc.get("id", ""),
        })
    return result


def _extract_json_tool_calls(content: str) -> list[dict[str, Any]] | None:
    """Extract tool calls from JSON-in-text response (fallback)."""
    try:
        data = json.loads(content.strip())
    except (json.JSONDecodeError, AttributeError):
        return None

    if isinstance(data, dict) and isinstance(data.get("tool_call"), dict):
        return [_normalize_tool_call(data["tool_call"])]
    if isinstance(data, dict) and isinstance(data.get("tool_calls"), list):
        return [
            _normalize_tool_call(item)
            for item in data["tool_calls"]
            if isinstance(item, dict)
        ]
    return None


def _normalize_tool_call(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": data.get("name") or data.get("tool") or "",
        "arguments": data.get("arguments") or data.get("input") or {},
    }
