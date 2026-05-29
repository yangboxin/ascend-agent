from ascend_agent.context.models import ConfigEnv, ContextDocument, RepoInfo, TraceInfo
from ascend_agent.diagnosis.engine import Engine
from ascend_agent.diagnosis.models import DiagnosisResult, Evidence, Hypothesis, SearchDecision


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


def test_diagnosis_rejects_evidence_with_missing_snippet(mock_router, tmp_path):
    source = tmp_path / "engine.py"
    source.write_text(
        "def run():\n"
        "    return 4096\n",
        encoding="utf-8",
    )
    diagnosis = DiagnosisResult(
        hypotheses=[
            Hypothesis(
                root_cause="The model cited the wrong code.",
                evidence=[
                    Evidence(
                        file_path="engine.py",
                        line_number=2,
                        code_snippet="raise RuntimeError('not here')",
                        relevance="This snippet is not in the file.",
                    )
                ],
                confidence=0.8,
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
        repo=RepoInfo(path=str(tmp_path), language="python", file_count=1, structure=["engine.py"]),
        trace=TraceInfo(raw_text="RuntimeError: boom"),
        config_env=ConfigEnv(),
    )

    result = Engine(router=mock_router, repo_path=str(tmp_path)).diagnose(context)

    assert result.hypotheses == []
    assert result.errors[0].stage == "evidence_validation"
    assert "snippet" in result.errors[0].reason


def test_diagnosis_keeps_valid_evidence(mock_router, tmp_path):
    source = tmp_path / "engine.py"
    source.write_text(
        "def run():\n"
        "    hidden_size = 8192\n"
        "    raise ValueError('Invalid dimension')\n",
        encoding="utf-8",
    )
    diagnosis = DiagnosisResult(
        hypotheses=[
            Hypothesis(
                root_cause="The configured hidden size is invalid.",
                evidence=[
                    Evidence(
                        file_path="engine.py",
                        line_number=3,
                        code_snippet="3:    raise ValueError('Invalid dimension')",
                        relevance="This is the line that raises the error.",
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
        repo=RepoInfo(path=str(tmp_path), language="python", file_count=1, structure=["engine.py"]),
        trace=TraceInfo(raw_text="ValueError: Invalid dimension"),
        config_env=ConfigEnv(),
    )

    result = Engine(router=mock_router, repo_path=str(tmp_path)).diagnose(context)

    assert len(result.hypotheses) == 1
    assert result.hypotheses[0].evidence[0].file_path == "engine.py"
    assert result.errors == []
