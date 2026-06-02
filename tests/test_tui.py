"""Tests for the TUI (Terminal User Interface) module.

Tests the core components, hooks, and utilities without
requiring an actual terminal (no rendering tests).
"""

from __future__ import annotations

import pytest

from ascend_agent.cli.tui.components.message_bubble import Message, format_message
from ascend_agent.cli.tui.components.code_block import CodeBlock, detect_language
from ascend_agent.cli.tui.hooks.use_command_history import CommandHistory
from ascend_agent.cli.tui.hooks.use_streaming import StreamBuffer, StreamState
from ascend_agent.cli.tui.hooks.use_terminal_size import TerminalSize, TerminalSizeWatcher
from ascend_agent.cli.tui.utils.ansi import strip_ansi, visible_width, sgr, reset
from ascend_agent.cli.tui.utils.markdown import render_markdown


# ====================================================================
# Message model tests
# ====================================================================

class TestMessage:
    def test_user_message(self):
        msg = Message(role="user", content="hello")
        assert msg.is_user
        assert not msg.is_assistant
        assert not msg.is_system
        assert msg.id

    def test_assistant_message(self):
        msg = Message(role="assistant", content="hi there")
        assert msg.is_assistant
        assert not msg.is_user

    def test_system_message(self):
        msg = Message(role="system", content="notice")
        assert msg.is_system
        assert not msg.is_user

    def test_format_user_message(self):
        msg = Message(role="user", content="test message")
        formatted = format_message(msg)
        assert formatted

    def test_format_assistant_message(self):
        msg = Message(role="assistant", content="**bold** text")
        formatted = format_message(msg)
        assert formatted

    def test_format_system_message(self):
        msg = Message(role="system", content="notice")
        formatted = format_message(msg)
        assert formatted

    def test_unique_ids(self):
        a = Message(role="user", content="a")
        b = Message(role="user", content="b")
        assert a.id != b.id


# ====================================================================
# CommandHistory tests
# ====================================================================

class TestCommandHistory:
    def test_add_and_navigate(self):
        h = CommandHistory()
        h.add("first command")
        h.add("second command")
        h.add("third command")

        assert len(h) == 3

        # Navigate up from current input
        result = h.navigate_up("current")
        assert result == "third command"

        result = h.navigate_up("")
        assert result == "second command"

        result = h.navigate_up("")
        assert result == "first command"

        # Already at oldest
        result = h.navigate_up("")
        assert result is None

    def test_navigate_down_restores_input(self):
        h = CommandHistory()
        h.add("old")
        h.add("new")

        # Start: index = -1
        r = h.navigate_up("my current input")
        assert r == "new"  # index = 1

        r = h.navigate_up("")
        assert r == "old"  # index = 0

        r = h.navigate_up("")
        assert r is None  # at beginning, can't go further

        r = h.navigate_down()
        assert r == "new"  # index = 1

        r = h.navigate_down()
        assert r == "my current input"  # back to present, restores saved input

    def test_duplicate_suppression(self):
        h = CommandHistory()
        h.add("cmd")
        h.add("cmd")
        h.add("cmd")
        assert len(h) == 1

        h.add("other")
        h.add("cmd")
        assert len(h) == 3  # cmd, other, cmd (not consecutive dupes)

    def test_empty(self):
        h = CommandHistory()
        assert not h
        assert len(h) == 0
        assert h.navigate_up("test") is None
        assert h.navigate_down() is None

    def test_clear(self):
        h = CommandHistory()
        h.add("cmd1")
        h.add("cmd2")
        h.clear()
        assert len(h) == 0

    def test_search(self):
        h = CommandHistory()
        h.add("python test.py")
        h.add("pip install")
        h.add("python -m pytest")
        results = h.search("python")
        assert len(results) == 2
        assert all("python" in r for r in results)

    def test_get_recent(self):
        h = CommandHistory()
        for i in range(20):
            h.add(f"cmd{i}")
        recent = h.get_recent(5)
        assert len(recent) == 5
        assert recent[-1] == "cmd19"


# ====================================================================
# StreamBuffer tests
# ====================================================================

class TestStreamBuffer:
    def test_append_and_drain(self):
        buf = StreamBuffer()
        buf.append("hello ")
        buf.append("world")
        assert buf.drain() == "hello world"
        assert buf.drain() == ""

    def test_complete_flag(self):
        buf = StreamBuffer()
        assert not buf.is_complete
        buf.is_complete = True
        assert buf.is_complete

    def test_reset(self):
        buf = StreamBuffer()
        buf.append("data")
        buf.is_complete = True
        buf.reset()
        assert not buf.is_complete
        assert buf.drain() == ""


# ====================================================================
# TerminalSize tests
# ====================================================================

class TestTerminalSize:
    def test_content_height(self):
        size = TerminalSize(columns=80, rows=24)
        assert size.content_height == 19  # 24 - 5
        assert size.input_height == 3

    def test_minimum_height(self):
        size = TerminalSize(columns=80, rows=3)
        assert size.content_height == 1  # clamped to min 1


# ====================================================================
# ANSI utilities tests
# ====================================================================

class TestANSI:
    def test_strip_ansi(self):
        text = "\x1b[1;31mRed\x1b[0m Normal"
        assert strip_ansi(text) == "Red Normal"

    def test_visible_width(self):
        text = "\x1b[1;31mRed\x1b[0m"
        assert visible_width(text) == 3

    def test_sgr_reset(self):
        assert reset() == "\x1b[0m"

    def test_sgr_codes(self):
        assert sgr(1) == "\x1b[1m"
        assert sgr(1, 31) == "\x1b[1;31m"
        assert sgr() == "\x1b[0m"


# ====================================================================
# Markdown rendering tests
# ====================================================================

class TestMarkdown:
    def test_plain_text(self):
        result = render_markdown("Hello world")
        assert result

    def test_bold(self):
        result = render_markdown("This is **bold** text")
        assert result

    def test_italic(self):
        result = render_markdown("This is *italic* text")
        assert result

    def test_code_block(self):
        result = render_markdown("```python\nprint('hello')\n```")
        assert result

    def test_heading(self):
        result = render_markdown("# Heading 1")
        assert result
        result = render_markdown("## Heading 2")
        assert result

    def test_list(self):
        result = render_markdown("- item 1\n- item 2")
        assert result

    def test_multiline(self):
        text = "Hello\n\nThis is a paragraph.\n\n```python\nx = 1\n```\n\nDone."
        result = render_markdown(text)
        assert result


# ====================================================================
# CodeBlock tests
# ====================================================================

class TestCodeBlock:
    def test_create_block(self):
        block = CodeBlock(code="print('hello')", language="python")
        assert block.language == "python"
        assert block.line_count == 1
        assert block.is_expanded

    def test_line_count(self):
        block = CodeBlock(code="line1\nline2\nline3")
        assert block.line_count == 3

    def test_collapsed_preview(self):
        block = CodeBlock(code="a\nb\nc\nd\ne\nf")
        assert block.collapsed_preview_lines == 4

    def test_detect_python(self):
        assert detect_language("def foo():") == "python"
        assert detect_language("import os") == "python"
        assert detect_language("class Foo:") == "python"

    def test_detect_javascript(self):
        assert detect_language("function foo() {") == "javascript"
        assert detect_language("const x = 1;") == "javascript"

    def test_detect_go(self):
        assert detect_language("func main() {") == "go"
        assert detect_language("package main") == "go"

    def test_detect_rust(self):
        assert detect_language("fn main() {") == "rust"
        assert detect_language("impl Foo {") == "rust"

    def test_detect_html(self):
        assert detect_language("<div>") == "html"

    def test_detect_unknown(self):
        assert detect_language("random text") == ""


# ====================================================================
# TUI Application construction tests
# ====================================================================

class TestTUIAppConstruction:
    def test_app_creation(self):
        from ascend_agent.cli.tui.app import AscendTUI, TUI_STYLE
        tui = AscendTUI(provider="test", model="test-model")
        assert tui._provider == "test"
        assert tui._model == "test-model"
        assert tui._messages == []

    def test_message_management(self):
        from ascend_agent.cli.tui.app import AscendTUI
        tui = AscendTUI(provider="test", model="test-model")

        tui.add_user_message("hello")
        assert len(tui.messages) == 1
        assert tui.messages[0].is_user

        tui.add_assistant_message("hi")
        assert len(tui.messages) == 2
        assert tui.messages[1].is_assistant

    def test_append_to_assistant(self):
        from ascend_agent.cli.tui.app import AscendTUI
        tui = AscendTUI(provider="test", model="test-model")

        # Append when no message exists — creates one
        tui.append_to_assistant("chunk1")
        assert len(tui.messages) == 1
        assert tui.messages[0].content == "chunk1"

        # Append to existing
        tui.append_to_assistant("chunk2")
        assert len(tui.messages) == 1
        assert tui.messages[0].content == "chunk1chunk2"

    def test_update_last_assistant(self):
        from ascend_agent.cli.tui.app import AscendTUI
        tui = AscendTUI(provider="test", model="test-model")

        tui.add_user_message("query")
        tui.update_last_assistant("final response")
        assert len(tui.messages) == 2
        assert tui.messages[1].content == "final response"

    def test_clear_messages(self):
        from ascend_agent.cli.tui.app import AscendTUI
        tui = AscendTUI(provider="test", model="test-model")
        tui.add_user_message("a")
        tui.add_assistant_message("b")
        tui.clear_messages()
        assert len(tui.messages) == 0

    def test_build_app_layout(self):
        from ascend_agent.cli.tui.app import AscendTUI
        tui = AscendTUI(provider="test", model="test-model")
        tui._build_app()

        assert tui._app is not None
        # 4 children: status, content, separator, input
        children = tui._app.layout.container.children
        assert len(children) == 4

    def test_stream_start(self):
        from ascend_agent.cli.tui.app import AscendTUI
        tui = AscendTUI(provider="test", model="test-model")
        manager, buf = tui.start_stream()
        assert manager is not None
        assert buf is not None
        assert manager.is_streaming is False  # Not started yet
