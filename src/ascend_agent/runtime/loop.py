"""Minimal agent loop facade."""

from __future__ import annotations

from dataclasses import dataclass

from ascend_agent.runtime.query_engine import QueryEngine
from ascend_agent.runtime.session import Session


@dataclass
class AgentLoop:
    """One-turn loop today; grows into tool-call iteration later."""

    query_engine: QueryEngine

    def run_turn(self, session: Session, user_input: str) -> str:
        return self.query_engine.invoke(session, user_input)
