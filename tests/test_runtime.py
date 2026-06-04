from __future__ import annotations

from pathlib import Path

import pytest

from ascend_agent.runtime import AgentLoop, PermissionPolicy, QueryEngine, Session, ToolRegistry


class FakeRouter:
    def __init__(self) -> None:
        self.messages = []

    def chat(self, messages):
        self.messages = messages
        return "runtime response"


def test_permission_policy_allow_ask_deny():
    policy = PermissionPolicy(allow=["safe_*"], ask=["maybe_*"], deny=["bad_*"])

    assert policy.check("safe_tool").allowed
    assert policy.check("maybe_tool").requires_confirmation
    assert not policy.check("bad_tool").allowed
    assert not policy.check("unknown").allowed


def test_tool_registry_describes_catalog_tools():
    registry = ToolRegistry.from_patterns(["workflow:ascend:diagnose_trace"])

    assert "diagnose_trace" in registry.tools
    assert "diagnose_trace" in registry.describe()


@pytest.mark.asyncio
async def test_tool_registry_blocks_confirmation_tools():
    registry = ToolRegistry.from_patterns(["workflow:ascend:verify_fix"])

    with pytest.raises(PermissionError, match="requires confirmation"):
        await registry.run("verify_fix", {"reproduction_json": "{}"})


def test_agent_loop_records_session_messages(tmp_path: Path):
    registry = ToolRegistry.from_patterns(["workflow:ascend:diagnose_trace"])
    router = FakeRouter()
    engine = QueryEngine(router=router, tools=registry)
    session = Session(working_dir=tmp_path)

    response = AgentLoop(engine).run_turn(session, "diagnose this")

    assert response == "runtime response"
    assert session.messages[-1] == {"role": "assistant", "content": "runtime response"}
    assert router.messages[0]["role"] == "system"
    assert "diagnose_trace" in router.messages[0]["content"]
