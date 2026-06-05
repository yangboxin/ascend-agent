from __future__ import annotations

from pathlib import Path

import pytest

from ascend_agent.providers.router import ChatResponse
import asyncio

from ascend_agent.runtime import (
    AgentLoop,
    PermissionContext,
    PermissionPolicy,
    QueryEngine,
    Runtime,
    Session,
    ToolRegistry,
    run_turn_sync,
)
from ascend_agent.skills.loader import Skill, load_skills, skill_prompt_injection
from ascend_agent.tools.catalog import list_tools, to_langchain_tools_for_workdir
from ascend_agent.tools.catalog import list_tools, to_langchain_tools_for_workdir


class FakeRouter:
    def __init__(self) -> None:
        self.messages = []

    def chat(self, messages, tools=None):
        self.messages = messages
        return ChatResponse(content="runtime response")


class SequencedRouter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.messages = []

    def chat(self, messages, tools=None):
        self.messages.append(messages)
        raw = self.responses.pop(0)
        # Support both str and ChatResponse in the sequence
        if isinstance(raw, ChatResponse):
            return raw
        return ChatResponse(content=raw)


def test_permission_policy_allow_ask_deny():
    policy = PermissionPolicy(allow=["safe_*"], ask=["maybe_*"], deny=["bad_*"])

    assert policy.check("safe_tool").allowed
    assert policy.check("maybe_tool").requires_confirmation
    assert not policy.check("bad_tool").allowed
    assert not policy.check("unknown").allowed


def test_permission_context_modes(tmp_path: Path):
    plan = PermissionContext(mode="plan", working_dir=tmp_path)
    accept_edits = PermissionContext(mode="accept_edits", working_dir=tmp_path)
    bypass = PermissionContext(mode="bypass", working_dir=tmp_path)
    tools = {tool.name: tool for tool in list_tools()}

    assert plan.check(tools["code_search"], {"path": "."}).allowed
    assert not plan.check(tools["edit_file"], {"file_path": "x.py"}).allowed
    assert accept_edits.check(tools["edit_file"], {"file_path": "x.py"}).allowed
    assert accept_edits.check(tools["exec_shell"], {"command": "pytest"}).requires_confirmation
    assert bypass.check(tools["exec_shell"], {"command": "rm -rf /"}).allowed
    assert not plan.check(tools["code_search"], {"path": "../outside"}).allowed


def test_tool_registry_describes_catalog_tools():
    registry = ToolRegistry.from_patterns(["workflow:ascend:diagnose_trace"])

    assert "diagnose_trace" in registry.tools
    assert "diagnose_trace" in registry.describe()


@pytest.mark.asyncio
async def test_tool_registry_truncates_results():
    async def noisy() -> str:
        return "x" * 20

    tool = list_tools(["workflow:ascend:diagnose_trace"])[0]
    limited = tool.__class__(
        name="limited",
        description="Return long text",
        category="impl",
        module="test",
        func=noisy,
        is_read_only=True,
        max_result_size_chars=5,
    )
    registry = ToolRegistry(
        tools={"limited": limited},
        permissions=PermissionContext(mode="default"),
    )

    result = await registry.run("limited")

    assert result.startswith("xxxxx")
    assert "truncated" in result


def test_langchain_tool_binding_scopes_workdir(tmp_path: Path):
    tools = to_langchain_tools_for_workdir(list_tools(["workflow:ascend:diagnose_trace"]), tmp_path)

    diagnose = tools[0]
    assert diagnose.name == "diagnose_trace"
    assert diagnose.description
    assert "kwargs" in diagnose.args


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

    response = asyncio.run(run_turn_sync(session, "diagnose this", AgentLoop(engine)))

    assert response == "runtime response"
    assert session.messages[-1] == {"role": "assistant", "content": "runtime response"}
    assert router.messages[0]["role"] == "system"
    assert "diagnose_trace" in router.messages[0]["content"]


def test_agent_loop_runs_json_tool_call_then_final(tmp_path: Path):
    router = SequencedRouter(
        [
            '{"tool_call": {"name": "code_search", "arguments": {"pattern": "needle"}}}',
            "final answer",
        ]
    )
    registry = ToolRegistry.from_patterns(
        ["impl:ascend:code_search"],
        permissions=PermissionContext(mode="default", working_dir=tmp_path),
        working_dir=tmp_path,
    )
    session = Session(working_dir=tmp_path)
    loop = AgentLoop(QueryEngine(router=router, tools=registry))
    response = asyncio.run(run_turn_sync(session, "find needle", loop))

    assert response == "final answer"
    assert any(message.get("role") == "tool" for message in session.messages)


def test_agent_loop_records_empty_native_tool_call_assistant(tmp_path: Path):
    tool_calls = [
        {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "code_search",
                "arguments": '{"pattern": "needle"}',
            },
        }
    ]
    router = SequencedRouter(
        [
            ChatResponse(content="", tool_calls=tool_calls, finish_reason="tool_calls"),
            "final answer",
        ]
    )
    registry = ToolRegistry.from_patterns(
        ["impl:ascend:code_search"],
        permissions=PermissionContext(mode="default", working_dir=tmp_path),
        working_dir=tmp_path,
    )
    session = Session(working_dir=tmp_path)
    loop = AgentLoop(QueryEngine(router=router, tools=registry))

    response = asyncio.run(run_turn_sync(session, "find needle", loop))

    assert response == "final answer"
    assistant = session.messages[1]
    tool = session.messages[2]
    assert assistant["role"] == "assistant"
    assert assistant["content"] == ""
    assert assistant["tool_calls"] == tool_calls
    assert tool["role"] == "tool"
    assert tool["tool_call_id"] == "call_123"

    next_request_messages = router.messages[1]
    assistant_request = next(
        message for message in next_request_messages if message.get("role") == "assistant"
    )
    tool_request = next(
        message for message in next_request_messages if message.get("role") == "tool"
    )
    assert assistant_request["tool_calls"][0]["id"] == tool_request["tool_call_id"]


def test_runtime_create_public_facade(tmp_path: Path, monkeypatch):
    router = FakeRouter()

    def fake_create(provider, tools):
        return QueryEngine(router=router, tools=tools)

    monkeypatch.setattr(QueryEngine, "create", staticmethod(fake_create))
    runtime = Runtime.create(provider="openai", working_dir=tmp_path, permission_mode="plan")
    session = runtime.create_session()

    assert session.working_dir == tmp_path.resolve()
    assert runtime.run_turn_sync(session, "hello") == "runtime response"
    assert session.metadata["permission_mode"] == "plan"


# -- skill loader tests -------------------------------------------------------


def test_load_skills_empty_directory(tmp_path):
    """Returns empty list when no skills directory exists."""
    skills = load_skills(config_dir=tmp_path)
    assert skills == []


def test_load_skills_parses_frontmatter(tmp_path):
    """Parses skill files with valid YAML frontmatter."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "greeting.md").write_text(
        "---\n"
        "name: greeting\n"
        "description: Respond to greetings\n"
        "when_to_use: When the user says hello\n"
        "---\n"
        "# Greeting Skill\n\n"
        "Always respond with a friendly tone.\n"
    )

    skills = load_skills(config_dir=tmp_path)
    assert len(skills) == 1
    assert skills[0].name == "greeting"
    assert skills[0].description == "Respond to greetings"
    assert skills[0].when_to_use == "When the user says hello"
    assert "friendly tone" in skills[0].content


def test_skill_prompt_injection_formats_correctly():
    """skill_prompt_injection formats skills for system prompt."""
    skills = [
        Skill(name="greeting", description="Respond to greetings", content="...", when_to_use="hello"),
        Skill(name="debug", description="Debug workflow", content="..."),
    ]
    result = skill_prompt_injection(skills)
    assert "## Available Skills" in result
    assert "greeting" in result
    assert "debug" in result
    assert "When to use: hello" in result


def test_skill_prompt_injection_empty():
    """skill_prompt_injection returns empty str for no skills."""
    assert skill_prompt_injection([]) == ""


def test_load_skills_skips_invalid_frontmatter(tmp_path):
    """Skill files with invalid YAML are skipped gracefully."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "bad.md").write_text("No frontmatter here.\nJust content.")

    skills = load_skills(config_dir=tmp_path)
    assert skills == []


# -- session persistence tests ------------------------------------------------


def test_session_save_and_load(tmp_path, monkeypatch):
    """Session can be saved to JSONL and loaded back."""
    from ascend_agent.runtime.session import _sessions_dir

    monkeypatch.setattr(
        "ascend_agent.runtime.session._sessions_dir", lambda: tmp_path / "sessions"
    )

    session = Session(working_dir=tmp_path, provider="openai")
    session.add_user_message("hello")
    tool_calls = [
        {
            "id": "call_abc",
            "type": "function",
            "function": {"name": "search", "arguments": "{}"},
        }
    ]
    session.add_assistant_message("hi there", tool_calls=tool_calls)
    session.add_tool_message("search", "found it", tool_call_id="call_abc")

    filepath = session.save()
    assert filepath.exists()

    loaded = Session.load(session.thread_id, working_dir=tmp_path)
    assert loaded.thread_id == session.thread_id
    assert len(loaded.messages) == 3
    assert loaded.messages[0]["role"] == "user"
    assert loaded.messages[0]["content"] == "hello"
    assert loaded.messages[1]["role"] == "assistant"
    assert loaded.messages[1]["tool_calls"] == tool_calls
    assert loaded.messages[2]["role"] == "tool"
    assert loaded.messages[2]["name"] == "search"
    assert loaded.messages[2]["tool_call_id"] == "call_abc"


def test_session_load_missing_raises():
    """Loading a nonexistent session raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        Session.load("nonexistent-thread-id")


def test_session_fork(tmp_path):
    """Fork creates a new session with copied messages and new thread_id."""
    session = Session(working_dir=tmp_path, provider="deepseek")
    session.add_user_message("original")
    session.add_assistant_message("response")

    child = session.fork()
    assert child.thread_id != session.thread_id
    assert child.provider == "deepseek"
    assert child.metadata.get("forked_from") == session.thread_id
    assert len(child.messages) == 2
    assert child.messages[0]["content"] == "original"

    empty = session.fork(preserve_messages=False)
    assert empty.messages == []


def test_session_auto_creates_dir(tmp_path, monkeypatch):
    """Session.save() creates the sessions directory if needed."""
    sessions_dir = tmp_path / "custom_sessions"
    monkeypatch.setattr(
        "ascend_agent.runtime.session._sessions_dir", lambda: sessions_dir
    )

    session = Session(working_dir=tmp_path)
    session.add_user_message("test")
    filepath = session.save()

    assert sessions_dir.is_dir()
    assert filepath.exists()


def test_list_sessions_function(tmp_path, monkeypatch):
    """list_sessions returns saved sessions sorted by mtime."""
    from ascend_agent.runtime.session import list_sessions as ls, _sessions_dir

    monkeypatch.setattr(
        "ascend_agent.runtime.session._sessions_dir", lambda: tmp_path / "sessions"
    )

    assert ls() == []

    session = Session(working_dir=tmp_path)
    session.add_user_message("hello world")
    session.save()

    result = ls()
    assert len(result) == 1
    assert result[0]["thread_id"] == session.thread_id
    assert result[0]["message_count"] == 1


# -- context compaction tests -------------------------------------------------


def test_compact_context_noop_when_under_limit():
    """Messages under the token limit are returned unchanged."""
    from ascend_agent.runtime.query_engine import _compact_context

    messages = [
        {"role": "user", "content": "short"},
        {"role": "assistant", "content": "reply"},
    ]
    result = _compact_context(messages, max_tokens=10000)
    assert result == messages


def test_compact_context_trims_old_tool_results():
    """Old tool results are trimmed when over the token limit."""
    from ascend_agent.runtime.query_engine import _compact_context

    messages = [
        {"role": "user", "content": "x" * 50},
        {"role": "assistant", "content": "y" * 50},
    ] + [
        {"role": "tool", "content": "z" * 500, "name": f"tool{i}"}
        for i in range(10)
    ]

    result = _compact_context(messages, max_tokens=50)

    assert any("trimmed" in m.get("content", "") for m in result[:6])
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "assistant"


def test_compact_context_preserves_recent():
    """The last 4 tool results are never trimmed."""
    from ascend_agent.runtime.query_engine import _compact_context

    messages = [{"role": "tool", "content": "x" * 500, "name": f"t{i}"} for i in range(6)]
    result = _compact_context(messages, max_tokens=10)

    for i in range(-4, 0):
        assert "trimmed" not in result[i]["content"]
