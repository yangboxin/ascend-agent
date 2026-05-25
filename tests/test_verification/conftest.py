import textwrap
from unittest.mock import Mock

import pytest

from ascend_agent.diagnosis.models import ReproductionResult


@pytest.fixture
def mock_router():
    mock = Mock()
    mock.completion = Mock()
    return mock


@pytest.fixture
def mock_settings():
    mock = Mock()
    mock.shell_timeout = 10
    mock.test_timeout = 30
    mock.ssh_host = ""
    mock.ssh_user = ""
    mock.ssh_key_path = ""
    return mock


@pytest.fixture
def sample_reproduction():
    return ReproductionResult(
        status="success",
        command="python -m pytest tests/test_shell_exec.py",
        stdout="1 passed",
        stderr="",
        exit_code=0,
        duration_seconds=1.5,
        hypothesis_id_tested=0,
        files_changed=["src/ascend_agent/tools/shell_exec.py"],
    )


@pytest.fixture
def sample_repo_dir(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(textwrap.dedent("""\
        [tool.pytest.ini_options]
        testpaths = ["tests"]
        asyncio_mode = "auto"
    """))
    src_pkg = tmp_path / "src" / "mypkg"
    src_pkg.mkdir(parents=True)
    core_py = src_pkg / "core.py"
    core_py.write_text("def add(a, b):\n    return a + b\n")
    test_dir = tmp_path / "tests"
    test_dir.mkdir(parents=True)
    test_core = test_dir / "test_core.py"
    test_core.write_text("from src.mypkg.core import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    return tmp_path
