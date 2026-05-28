import pytest

from ascend_agent.context.models import ConfigEnv, ContextDocument, RepoInfo, TraceInfo
from ascend_agent.diagnosis.engine import Engine
from ascend_agent.diagnosis.models import DiagnosisResult, Evidence, Hypothesis, SearchDecision


@pytest.mark.xfail(
    reason="Phase 0 baseline: Diagnosis evidence is schema-validated but not checked against repository files.",
    strict=True,
)
def test_diagnosis_rejects_nonexistent_evidence_file(mock_router, tmp_path):
    diagnosis = DiagnosisResult(
        hypotheses=[
            Hypothesis(
                root_cause="The model invented evidence.",
                evidence=[
                    Evidence(
                        file_path="missing.py",
                        line_number=99,
                        code_snippet="raise RuntimeError('missing')",
                        relevance="This file does not exist.",
                    )
                ],
                confidence=0.9,
            )
        ],
        errors=[],
        iterations_used=1,
    )
    mock_router.completion.side_effect = [
        SearchDecision(action="hypothesize", reasoning="done"),
        diagnosis,
    ]
    context = ContextDocument(
        repo=RepoInfo(path=str(tmp_path), language="python", file_count=0, structure=[]),
        trace=TraceInfo(raw_text="RuntimeError: boom"),
        config_env=ConfigEnv(),
    )

    result = Engine(router=mock_router, repo_path=str(tmp_path)).diagnose(context)

    assert result.hypotheses == []
    assert result.errors
    assert result.errors[0].stage == "evidence_validation"
