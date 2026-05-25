import os

import pytest
from unittest.mock import Mock

from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    Evidence,
    Hypothesis,
)


@pytest.fixture
def mock_router():
    mock = Mock()
    mock.completion = Mock()
    return mock


@pytest.fixture
def sample_diagnosis():
    return DiagnosisResult(
        hypotheses=[
            Hypothesis(
                root_cause="Config mismatch in dimension parsing",
                evidence=[
                    Evidence(
                        file_path="tests/test_dim.py",
                        line_number=42,
                        code_snippet="def test_dimensions():\n    assert dim == 4096",
                        relevance="This test reproduces the dimension mismatch error",
                    )
                ],
                confidence=0.85,
            )
        ],
        errors=[],
        iterations_used=2,
    )


@pytest.fixture
def sample_repo_dir(tmp_path):
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    test_file = test_dir / "test_dim.py"
    test_file.write_text(
        "import os\n\n"
        "def test_dimensions():\n"
        "    dim = int(os.environ.get('DIM', '4096'))\n"
        "    assert dim == 4096, f'Expected 4096, got {dim}'\n"
    )
    return tmp_path


@pytest.fixture
def mock_settings():
    mock = Mock()
    mock.shell_timeout = 10
    mock.ssh_host = ""
    mock.ssh_user = ""
    mock.ssh_key_path = ""
    return mock
