from pathlib import Path

import pytest
from unittest.mock import Mock


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
def mock_openai_response():
    """Returns a Mock that mimics OpenAI's parsed response.

    Use the side_effect pattern to set expectations:
        mock = mock_openai_response()
        mock.side_effect = lambda response_model: Mock(parsed=response_model(...))
    """

    def _make_mock(response_model=None):
        mock_completion = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        if response_model is not None:
            mock_message.parsed = response_model()
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        return mock_completion

    mock_client = Mock()
    mock_client.chat.completions.parse.side_effect = _make_mock
    return mock_client
