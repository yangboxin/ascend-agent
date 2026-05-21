"""Tests for the FixEngine class and fix generation models."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from ascend_agent.diagnosis.fix_engine import FixEngine, _build_fix_user_prompt
from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    FixGenerationResult,
    FixResponse,
    FixSuggestion,
    Hypothesis,
    PartialFailure,
    Replacement,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fix_response(replacements=None) -> FixResponse:
    """Create a default FixResponse for test mocks."""
    if replacements is None:
        replacements = [
            Replacement(
                file_path="test.py",
                old_text="x = 1\n",
                new_text="x = 2\n",
            )
        ]
    return FixResponse(
        explanation="Mock fix: increment value",
        replacements=replacements,
    )


def _make_hypothesis(
    root_cause: str = "test root cause",
    file_path: str = "test.py",
    line_number: int = 1,
    code_snippet: str = "x = 1\n",
) -> Hypothesis:
    """Create a Hypothesis with a single evidence item for testing."""
    from ascend_agent.diagnosis.models import Evidence

    return Hypothesis(
        root_cause=root_cause,
        evidence=[
            Evidence(
                file_path=file_path,
                line_number=line_number,
                code_snippet=code_snippet,
                relevance="Test evidence",
            )
        ],
        confidence=0.8,
    )


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------


class TestFixEngineModels:
    """Tests for the fix generation Pydantic models."""

    def test_replacement_valid(self):
        """Replacement stores file_path, old_text, new_text."""
        r = Replacement(
            file_path="src/main.py",
            old_text="    return x + 1\n",
            new_text="    return x + 2\n",
        )
        assert r.file_path == "src/main.py"
        assert r.old_text == "    return x + 1\n"
        assert r.new_text == "    return x + 2\n"

    def test_replacement_forbids_extra(self):
        """Replacement raises ValidationError for extra fields."""
        with pytest.raises(ValidationError):
            Replacement(
                file_path="test.py",
                old_text="foo",
                new_text="bar",
                extra_field="x",
            )

    def test_fix_response_valid(self):
        """FixResponse stores explanation and list of replacements."""
        r = Replacement(file_path="x.py", old_text="a", new_text="b")
        fr = FixResponse(explanation="Fix test", replacements=[r])
        assert fr.explanation == "Fix test"
        assert len(fr.replacements) == 1
        assert fr.replacements[0].file_path == "x.py"

    def test_fix_suggestion_valid(self):
        """FixSuggestion stores all fields."""
        r = Replacement(file_path="x.py", old_text="a", new_text="b")
        fs = FixSuggestion(
            file_path="src/main.py",
            diff_patch="--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-foo\n+bar\n",
            explanation="Fix the issue",
            hypothesis_id=0,
            replacements=[r],
        )
        assert fs.file_path == "src/main.py"
        assert "--- a/src/main.py" in fs.diff_patch
        assert fs.hypothesis_id == 0
        assert len(fs.replacements) == 1

    def test_fix_suggestion_hypothesis_id_type(self):
        """hypothesis_id should accept int, reject str."""
        r = Replacement(file_path="x.py", old_text="a", new_text="b")
        # int works
        fs = FixSuggestion(
            file_path="test.py",
            diff_patch="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-foo\n+bar\n",
            explanation="test",
            hypothesis_id=0,
            replacements=[r],
        )
        assert fs.hypothesis_id == 0

        # str should raise
        with pytest.raises(ValidationError):
            FixSuggestion(
                file_path="test.py",
                diff_patch="diff",
                explanation="test",
                hypothesis_id="zero",
                replacements=[r],
            )

    def test_fix_generation_result_defaults(self):
        """FixGenerationResult has empty defaults."""
        fgr = FixGenerationResult()
        assert fgr.suggestions == []
        assert fgr.errors == []
        assert fgr.total_hypotheses == 0

    def test_diagnosis_output_valid(self):
        """DiagnosisOutput accepts context_doc and diagnosis_result."""
        from ascend_agent.diagnosis.models import DiagnosisOutput

        # Use model_construct to bypass forward-reference validation
        # since ContextDocument is in a different module
        dr = DiagnosisResult(hypotheses=[], errors=[], iterations_used=1)
        mock_doc = Mock()

        output = DiagnosisOutput.model_construct(
            context_doc=mock_doc,
            diagnosis_result=dr,
        )
        assert output.context_doc is mock_doc
        assert output.diagnosis_result.iterations_used == 1


# ---------------------------------------------------------------------------
# FixEngine class tests
# ---------------------------------------------------------------------------


class TestFixEngine:
    """Tests for the FixEngine class."""

    def test_constructor_stores_dependencies(
        self, mock_router, tmp_path: Path
    ):
        """FixEngine.__init__ stores router and resolved repo_path."""
        engine = FixEngine(router=mock_router, repo_path=str(tmp_path))
        assert engine._router is mock_router
        assert engine._repo_path_resolved == tmp_path.resolve()

    def test_generate_fixes_iterates_hypotheses(
        self, mock_router, tmp_path: Path
    ):
        """generate_fixes iterates all hypotheses and returns results."""
        # Create a real file the fix engine can read
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        # Mock LLM to return a successful FixResponse
        mock_router.completion.return_value = _make_fix_response()

        # Create a DiagnosisResult with 2 hypotheses
        hyp1 = _make_hypothesis(
            file_path="test.py", line_number=1, code_snippet="x = 1\n"
        )
        hyp2 = _make_hypothesis(
            root_cause="second issue",
            file_path="test.py",
            line_number=1,
            code_snippet="x = 1\n",
        )
        diagnosis = DiagnosisResult(hypotheses=[hyp1, hyp2])

        with patch(
            "ascend_agent.diagnosis.engine._read_function_body",
            return_value="1:x = 1\n",
        ):
            engine = FixEngine(router=mock_router, repo_path=str(tmp_path))
            result = engine.generate_fixes(diagnosis)

        assert isinstance(result, FixGenerationResult)
        # Both hypotheses should produce suggestions
        assert len(result.suggestions) == 2
        assert result.total_hypotheses == 2

    def test_generate_fixes_handles_llm_failure(
        self, mock_router, tmp_path: Path
    ):
        """generate_fixes catches LLM exceptions and records PartialFailure."""
        # Mock LLM to raise an exception
        mock_router.completion.side_effect = ValueError("LLM unavailable")

        hyp = _make_hypothesis()
        diagnosis = DiagnosisResult(hypotheses=[hyp])

        with patch(
            "ascend_agent.diagnosis.engine._read_function_body",
            return_value="1:x = 1\n",
        ):
            engine = FixEngine(router=mock_router, repo_path=str(tmp_path))
            result = engine.generate_fixes(diagnosis)

        assert len(result.suggestions) == 0
        assert len(result.errors) == 1
        assert result.errors[0].stage == "fix_generation"
        assert "LLM unavailable" in str(result.errors[0].reason)
        assert result.total_hypotheses == 1

    def test_generate_fixes_skips_malformed_output(
        self, mock_router, tmp_path: Path
    ):
        """generate_fixes skips hypothesis when old_text not found in file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("y = 999\n")

        # Mock LLM returns FixResponse with old_text not in file
        bad_replacement = Replacement(
            file_path="test.py",
            old_text="x = 1\n",  # not in the file (file has "y = 999")
            new_text="x = 2\n",
        )
        mock_router.completion.return_value = _make_fix_response(
            replacements=[bad_replacement]
        )

        hyp = _make_hypothesis(
            file_path="test.py", line_number=1, code_snippet="y = 999\n"
        )
        diagnosis = DiagnosisResult(hypotheses=[hyp])

        with patch(
            "ascend_agent.diagnosis.engine._read_function_body",
            return_value="1:y = 999\n",
        ):
            engine = FixEngine(router=mock_router, repo_path=str(tmp_path))
            result = engine.generate_fixes(diagnosis)

        # Should have 0 suggestions since old_text not found
        assert len(result.suggestions) == 0
        # Should have 0 errors since validation failure is not an exception
        assert len(result.errors) == 0

    def test_generate_fixes_computes_diff(self, mock_router, tmp_path: Path):
        """generate_fixes computes a valid unified diff patch."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        replacement = Replacement(
            file_path="test.py",
            old_text="x = 1\n",
            new_text="x = 2\n",
        )
        mock_router.completion.return_value = _make_fix_response(
            replacements=[replacement]
        )

        hyp = _make_hypothesis(
            file_path="test.py", line_number=1, code_snippet="x = 1\n"
        )
        diagnosis = DiagnosisResult(hypotheses=[hyp])

        with patch(
            "ascend_agent.diagnosis.engine._read_function_body",
            return_value="1:x = 1\n",
        ):
            engine = FixEngine(router=mock_router, repo_path=str(tmp_path))
            result = engine.generate_fixes(diagnosis)

        assert len(result.suggestions) == 1
        diff_patch = result.suggestions[0].diff_patch
        # Unified diff format checks
        assert "---" in diff_patch
        assert "+++" in diff_patch
        assert "-x = 1" in diff_patch
        assert "+x = 2" in diff_patch

    def test_read_code_context_returns_code(
        self, mock_router, tmp_path: Path
    ):
        """_read_code_context returns code for valid evidence."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo():\n    return 42\n")

        hyp = _make_hypothesis(
            file_path="test.py", line_number=1, code_snippet="def foo():"
        )
        engine = FixEngine(router=mock_router, repo_path=str(tmp_path))
        context = engine._read_code_context(hyp)

        # Should contain function code (read via _read_function_body)
        assert len(context) > 0
        assert "test.py:" in context

    def test_read_code_context_empty_on_missing_file(
        self, mock_router, tmp_path: Path
    ):
        """_read_code_context returns empty string for missing file."""
        hyp = _make_hypothesis(
            file_path="nonexistent.py",
            line_number=1,
            code_snippet="missing code",
        )
        engine = FixEngine(router=mock_router, repo_path=str(tmp_path))
        context = engine._read_code_context(hyp)

        assert context == ""

    def test_path_traversal_blocked(self, mock_router, tmp_path: Path):
        """Replacements with paths outside repo are skipped."""
        test_file = tmp_path / "test.py"
        test_file.write_text("safe content\n")

        # Try to access a file outside the repo
        traversal_replacement = Replacement(
            file_path="../../etc/passwd",
            old_text="root:",
            new_text="hacked:",
        )
        mock_router.completion.return_value = _make_fix_response(
            replacements=[traversal_replacement]
        )

        hyp = _make_hypothesis(
            file_path="test.py", line_number=1, code_snippet="safe content"
        )
        diagnosis = DiagnosisResult(hypotheses=[hyp])

        with patch(
            "ascend_agent.diagnosis.engine._read_function_body",
            return_value="1:safe content\n",
        ):
            engine = FixEngine(router=mock_router, repo_path=str(tmp_path))
            result = engine.generate_fixes(diagnosis)

        # The traversal replacement should be silently skipped
        assert len(result.suggestions) == 0
