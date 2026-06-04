import pytest


def test_repo_scanner_discovers_files(sample_repo_dir):
    from ascend_agent.context.repo import RepoScanner
    result = RepoScanner().scan(sample_repo_dir)
    assert result.file_count == 3
    assert "main.py" in result.structure
    assert "utils/__init__.py" in result.structure
    assert "utils/helper.py" in result.structure


def test_repo_scanner_respects_gitignore(sample_repo_dir):
    from ascend_agent.context.repo import RepoScanner
    result = RepoScanner().scan(sample_repo_dir)
    assert not any(f.endswith(".log") for f in result.structure)
    assert "ignored.log" not in result.structure


def test_repo_info_schema(sample_repo_dir):
    from ascend_agent.context.repo import RepoScanner
    from ascend_agent.context.models import RepoInfo
    result = RepoScanner().scan(sample_repo_dir)
    assert isinstance(result, RepoInfo)
    assert result.path == str(sample_repo_dir.resolve())
    assert result.language == "python"


def test_repo_scanner_rejects_missing_path(tmp_path):
    from ascend_agent.context.repo import RepoScanner

    with pytest.raises(OSError, match="Repository path does not exist"):
        RepoScanner().scan(tmp_path / "missing")


def test_trace_parse_error_type(sample_trace):
    from ascend_agent.context.trace import parse_stack_trace
    result = parse_stack_trace(sample_trace)
    assert result.error_type == "ValueError"
    assert "Invalid dimension" in result.error_message


def test_trace_parse_frames(sample_trace):
    from ascend_agent.context.trace import parse_stack_trace
    result = parse_stack_trace(sample_trace)
    assert len(result.frames) == 3
    assert "api_server.py" in result.frames[0].file
    assert result.frames[0].line == 245
    assert result.frames[2].function == "_run_engine"


def test_trace_from_stdin(sample_trace, monkeypatch):
    from ascend_agent.context.trace import trace_from_stdin
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(sample_trace))
    result = trace_from_stdin()
    assert result.error_type == "ValueError"
    assert len(result.frames) == 3


def test_trace_text_arg(sample_trace):
    from ascend_agent.context.trace import trace_from_text
    result = trace_from_text(sample_trace)
    assert result.error_type == "ValueError"
    assert len(result.frames) == 3


def test_trace_bundle_from_files_preserves_sources(tmp_path):
    from ascend_agent.context.trace import trace_bundle_from_files

    first = tmp_path / "early.log"
    second = tmp_path / "late.log"
    first.write_text("INFO boot\n")
    second.write_text("RuntimeError: later failure\n")

    bundle = trace_bundle_from_files([first, second])

    assert len(bundle.sources) == 2
    assert bundle.sources[0].path == str(first.resolve())
    assert bundle.error_type == "RuntimeError"
    assert "Trace source" in bundle.raw_text


def test_trace_bundle_from_dir_reads_sorted_files(tmp_path):
    from ascend_agent.context.trace import trace_bundle_from_dir

    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "b.log").write_text("ValueError: b\n")
    (logs / "a.log").write_text("RuntimeError: a\n")

    bundle = trace_bundle_from_dir(logs)

    assert [source.label for source in bundle.sources] == ["a.log", "b.log"]
    assert len(bundle.error_events) == 2
