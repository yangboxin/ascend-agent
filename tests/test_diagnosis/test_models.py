import pytest
from pydantic import ValidationError


def test_evidence_valid():
    from ascend_agent.diagnosis.models import Evidence

    ev = Evidence(
        file_path="/repo/main.py",
        line_number=42,
        code_snippet="def foo():\n    return 1",
        relevance="Matches error location",
    )
    assert ev.file_path == "/repo/main.py"
    assert ev.line_number == 42
    assert ev.code_snippet == "def foo():\n    return 1"
    assert ev.relevance == "Matches error location"


def test_evidence_forbids_extra():
    from ascend_agent.diagnosis.models import Evidence

    with pytest.raises(ValidationError):
        Evidence(
            file_path="/repo/main.py",
            line_number=42,
            code_snippet="def foo():\n    return 1",
            relevance="Matches error location",
            extra_field="x",
        )


def test_hypothesis_confidence_range():
    from ascend_agent.diagnosis.models import Hypothesis, Evidence

    valid_evidence = [
        Evidence(
            file_path="/repo/main.py",
            line_number=42,
            code_snippet="def foo():\n    return 1",
            relevance="Test",
        )
    ]

    # Below range
    with pytest.raises(ValidationError):
        Hypothesis(root_cause="test", evidence=valid_evidence, confidence=-0.1)

    # Above range
    with pytest.raises(ValidationError):
        Hypothesis(root_cause="test", evidence=valid_evidence, confidence=1.1)

    # At lower bound
    h = Hypothesis(root_cause="test", evidence=valid_evidence, confidence=0.0)
    assert h.confidence == 0.0

    # Mid range
    h = Hypothesis(root_cause="test", evidence=valid_evidence, confidence=0.5)
    assert h.confidence == 0.5

    # At upper bound
    h = Hypothesis(root_cause="test", evidence=valid_evidence, confidence=1.0)
    assert h.confidence == 1.0


def test_diagnosis_result_defaults():
    from ascend_agent.diagnosis.models import DiagnosisResult

    dr = DiagnosisResult()
    assert dr.hypotheses == []
    assert dr.errors == []
    assert dr.iterations_used == 0


def test_search_decision_invalid_action():
    from ascend_agent.diagnosis.models import SearchDecision

    # Invalid action
    with pytest.raises(ValidationError):
        SearchDecision(action="invalid", reasoning="x")

    # Valid: search
    sd = SearchDecision(action="search", reasoning="Need to find function definition")
    assert sd.action == "search"

    # Valid: hypothesize
    sd = SearchDecision(action="hypothesize", reasoning="Sufficient information")
    assert sd.action == "hypothesize"


def test_partial_failure_optional_details():
    from ascend_agent.diagnosis.models import PartialFailure

    # Without details
    pf = PartialFailure(stage="search", reason="timeout")
    assert pf.details is None

    # With details
    pf = PartialFailure(stage="search", reason="timeout", details="30s timeout")
    assert pf.details == "30s timeout"
