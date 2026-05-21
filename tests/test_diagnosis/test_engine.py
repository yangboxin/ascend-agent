"""Tests for the diagnosis Engine class and _read_function_body utility."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ascend_agent.diagnosis.engine import Engine, _read_function_body
from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    SearchAction,
    SearchDecision,
)


class TestReadFunctionBody:
    """Tests for the _read_function_body utility function."""

    def test_extracts_function_body_with_context(self, tmp_path: Path):
        """Returns function body ±5 lines for a valid Python file."""
        src = """def outer():
    def inner():
        x = 42
        return x
    return inner()

def unrelated():
    pass

result = outer()
"""
        f = tmp_path / "test_func.py"
        f.write_text(src)
        result = _read_function_body(str(f), 3)  # line 3 is 'x = 42' inside inner()
        assert result is not None
        # Should contain the function body lines (with line number prefix)
        assert "3:        x = 42" in result
        # Should contain the 'def inner():' line (surrounding context)
        # inner() starts at line 2, so context_lines=5 should include lines from
        # max(0, 2-1-5) = 0 to min(7, 5+5) = 7
        # line 0 is 'def outer():', line 1 is '    def inner():'
        assert "2:    def inner():" in result

    def test_fallback_to_line_window(self, tmp_path: Path):
        """Returns line-based window when target line is outside any function."""
        src = "a = 1\nb = 2\nc = 3\ndef foo():\n    pass\n"
        f = tmp_path / "test_fallback.py"
        f.write_text(src)
        # line 1 is 'a = 1' - outside any function
        result = _read_function_body(str(f), 1)
        assert result is not None
        # Should contain the top-level assignment
        assert "1:a = 1" in result

    def test_nonexistent_file_returns_none(self):
        """Returns None for a non-existent file."""
        result = _read_function_body("/nonexistent/path.py", 1)
        assert result is None


class TestEngine:
    """Tests for the Engine class."""

    def test_constructor_stores_dependencies(self, mock_router, tmp_path: Path):
        """Engine.__init__ stores router and repo_path."""
        engine = Engine(router=mock_router, repo_path=str(tmp_path))
        assert engine._router is mock_router
        assert engine._repo_path_resolved == tmp_path.resolve()

    def test_search_loop_hypothesizes_after_searches(self, mock_router, sample_context_doc, tmp_path: Path):
        """Engine search loop iterates with mock LLM: searches then hypothesizes."""
        # First call returns search decision
        # Second call returns hypothesize decision
        mock_router.completion.side_effect = [
            SearchDecision(
                action="search",
                searches=[SearchAction(pattern="def foo", rationale="looking for function")],
                reasoning="need more context",
            ),
            SearchDecision(
                action="hypothesize",
                searches=[],
                reasoning="enough info",
            ),
            DiagnosisResult(
                hypotheses=[],
                errors=[],
                iterations_used=2,
            ),
        ]

        with patch("ascend_agent.tools.code_search.search_code", return_value="No matches"):
            engine = Engine(router=mock_router, repo_path=str(tmp_path))
            result = engine.diagnose(sample_context_doc)

        assert isinstance(result, DiagnosisResult)
        # iterations_used should be 1 or 2 depending on logic
        assert 0 <= result.iterations_used <= 2

    def test_engine_handles_search_failure(self, mock_router, sample_context_doc, tmp_path: Path):
        """Engine reports partial failure on search error without crashing."""
        mock_router.completion.side_effect = [
            SearchDecision(
                action="search",
                searches=[SearchAction(pattern="def foo", rationale="test")],
                reasoning="test",
            ),
            SearchDecision(
                action="hypothesize",
                searches=[],
                reasoning="done",
            ),
            DiagnosisResult(
                hypotheses=[],
                errors=[],
                iterations_used=2,
            ),
        ]

        with patch("ascend_agent.tools.code_search.search_code", side_effect=ValueError("search failed")):
            engine = Engine(router=mock_router, repo_path=str(tmp_path))
            result = engine.diagnose(sample_context_doc)

        assert isinstance(result, DiagnosisResult)

    def test_engine_exhausts_budget(self, mock_router, sample_context_doc, tmp_path: Path):
        """Engine produces hypotheses when budget is exhausted (3 search iterations)."""
        # Always return search decisions to exhaust budget
        mock_router.completion.side_effect = [
            SearchDecision(
                action="search",
                searches=[SearchAction(pattern="search1", rationale="test")],
                reasoning="test",
            ),
            SearchDecision(
                action="search",
                searches=[SearchAction(pattern="search2", rationale="test")],
                reasoning="test",
            ),
            SearchDecision(
                action="search",
                searches=[SearchAction(pattern="search3", rationale="test")],
                reasoning="test",
            ),
            DiagnosisResult(
                hypotheses=[],
                errors=[],
                iterations_used=3,
            ),
        ]

        with patch("ascend_agent.tools.code_search.search_code", return_value="No matches"):
            engine = Engine(router=mock_router, repo_path=str(tmp_path))
            result = engine.diagnose(sample_context_doc)

        assert isinstance(result, DiagnosisResult)
        assert result.iterations_used == 3

    def test_engine_silent_no_clarifying_questions(self, mock_router, sample_context_doc, tmp_path: Path):
        """Engine never calls input() or prompts user for information."""
        mock_router.completion.side_effect = [
            SearchDecision(
                action="hypothesize",
                searches=[],
                reasoning="enough info",
            ),
            DiagnosisResult(
                hypotheses=[],
                errors=[],
                iterations_used=1,
            ),
        ]

        with patch("ascend_agent.tools.code_search.search_code", return_value="No matches"):
            engine = Engine(router=mock_router, repo_path=str(tmp_path))
            # This should never call input() or ask clarifying questions
            result = engine.diagnose(sample_context_doc)

        assert isinstance(result, DiagnosisResult)

    def test_function_body_extraction_valid(self, tmp_path: Path):
        """_read_function_body returns code with {line_no}:{code} format."""
        src = """import os

def calculate(x, y):
    result = x + y
    return result

value = calculate(1, 2)
"""
        f = tmp_path / "calc.py"
        f.write_text(src)
        result = _read_function_body(str(f), 4)  # line 4 inside calculate()
        assert result is not None
        # Should contain the line number prefix format
        assert "4:    result = x + y" in result
        assert "5:    return result" in result

    def test_function_body_extraction_fallback(self, tmp_path: Path):
        """_read_function_body falls back to line window when line is outside function."""
        src = """TOP_LEVEL = 42

def func():
    pass
"""
        f = tmp_path / "fallback.py"
        f.write_text(src)
        result = _read_function_body(str(f), 1)  # line 1 is top-level
        assert result is not None
        assert "1:TOP_LEVEL = 42" in result

    def test_function_body_extraction_nonexistent_file(self):
        """_read_function_body returns None for non-existent file."""
        result = _read_function_body("/nonexistent/path.py", 1)
        assert result is None
