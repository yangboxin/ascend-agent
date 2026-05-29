from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _dummy_api_key(monkeypatch: pytest.MonkeyPatch):
    """Ensure dummy API keys are available for all tests.
    
    Tests that explicitly test "missing API key" behavior
    should call monkeypatch.delenv() themselves.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy-key")
    monkeypatch.setenv("ASCEND_DEEPSEEK_API_KEY", "sk-test-dummy-key")
    monkeypatch.setenv("ASCEND_QWEN_API_KEY", "sk-test-dummy-key")


@pytest.fixture(scope="session")
def sample_trace():
    return (
        'Traceback (most recent call last):\n'
        '  File "/home/user/vllm-ascend/vllm/entrypoints/openai/api_server.py", line 245, in create_chat_completion\n'
        "    result = await engine.generate(prompt, sampling_params)\n"
        '  File "/home/user/vllm-ascend/vllm/engine/async_llm_engine.py", line 89, in generate\n'
        "    output = await self._run_engine(model_input)\n"
        '  File "/home/user/vllm-ascend/vllm/engine/async_llm_engine.py", line 156, in _run_engine\n'
        '    raise ValueError("Invalid dimension: expected 4096, got 8192")\n'
        "ValueError: Invalid dimension: expected 4096, got 8192\n"
    )


@pytest.fixture(scope="function")
def sample_repo_dir(tmp_path: Path):
    (tmp_path / "main.py").write_text("def foo():\n    return 42\n")
    (tmp_path / "utils").mkdir()
    (tmp_path / "utils" / "__init__.py").write_text("")
    (tmp_path / "utils" / "helper.py").write_text("def helper():\n    return 'help'\n")
    (tmp_path / ".gitignore").write_text("*.log\n")
    (tmp_path / "ignored.log").write_text("should be ignored\n")
    return tmp_path


@pytest.fixture(scope="function")
def sample_repo_files(sample_repo_dir: Path):
    return [
        "main.py",
        "utils/__init__.py",
        "utils/helper.py",
        ".gitignore",
        "ignored.log",
    ]
