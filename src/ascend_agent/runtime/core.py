"""Public runtime facade."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, AsyncGenerator

from ascend_agent.runtime.loop import AgentLoop, LoopEvent, run_turn_sync
from ascend_agent.runtime.permissions import PermissionMode, default_policy_for_mode
from ascend_agent.runtime.query_engine import QueryEngine
from ascend_agent.runtime.session import Session
from ascend_agent.runtime.tools import ToolRegistry


@dataclass
class Runtime:
    provider: str
    working_dir: Path
    permission_mode: PermissionMode = "default"
    model: str | None = None
    tools: ToolRegistry | None = None
    loop: AgentLoop | None = None

    @classmethod
    def create(
        cls,
        provider: str = "openai",
        working_dir: str | Path = ".",
        permission_mode: PermissionMode = "default",
        model: str | None = None,
    ) -> "Runtime":
        root = Path(working_dir).resolve()
        permissions = default_policy_for_mode(permission_mode, root)
        tools = ToolRegistry.from_patterns(
            ["impl:ascend:*", "workflow:ascend:*"],
            permissions=permissions,
            working_dir=root,
        )
        engine = QueryEngine.create(provider, tools)
        loop = AgentLoop(engine)
        return cls(
            provider=provider,
            working_dir=root,
            permission_mode=permission_mode,
            model=model,
            tools=tools,
            loop=loop,
        )

    def create_session(self) -> Session:
        return Session(
            working_dir=self.working_dir,
            provider=self.provider,
            model=self.model,
            metadata={"permission_mode": self.permission_mode},
        )

    async def run_turn(
        self, session: Session, user_input: str
    ) -> AsyncGenerator[LoopEvent, None]:
        """Run a turn of the agent loop, yielding streaming events."""
        if self.loop is None:
            raise RuntimeError("Runtime loop is not initialized")
        async for event in self.loop.run_turn(session, user_input):
            yield event

    def run_turn_sync(self, session: Session, user_input: str) -> str:
        """Convenience: run a turn synchronously, returning the final text."""
        if self.loop is None:
            raise RuntimeError("Runtime loop is not initialized")
        return asyncio.run(run_turn_sync(session, user_input, self.loop))

    def set_permission_mode(self, mode: PermissionMode) -> None:
        self.permission_mode = mode
        if self.tools is not None:
            self.tools.permissions = default_policy_for_mode(mode, self.working_dir)

    def set_confirmation_handler(
        self, handler: Callable[[str, dict[str, Any]], bool] | None
    ) -> None:
        """Register a handler that prompts the user before running sensitive tools."""
        if self.tools is not None:
            self.tools.set_confirmation_handler(handler)
