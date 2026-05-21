import json

import pytest


@pytest.mark.asyncio
async def test_single_replacement_applies_correctly(tmp_path):
    """Verify single replacement works and .bak backup is created."""
    from ascend_agent.tools.file_edit import edit_file

    f = tmp_path / "test.py"
    f.write_text("x = 1\n")

    result = json.loads(await edit_file(file_path=str(f), operations=[
        {"old_text": "x = 1\n", "new_text": "x = 2\n"},
    ]))

    assert result["status"] == "ok"
    assert "Applied 1 replacement" in result["message"]
    # File content updated
    assert f.read_text() == "x = 2\n"
    # Backup file exists with original content
    backup = tmp_path / "test.py.bak"
    assert backup.exists()
    assert backup.read_text() == "x = 1\n"


@pytest.mark.asyncio
async def test_old_text_not_found_returns_error(tmp_path):
    """Verify error when old_text is not present in the file."""
    from ascend_agent.tools.file_edit import edit_file

    f = tmp_path / "test.py"
    f.write_text("x = 1\n")

    result = json.loads(await edit_file(file_path=str(f), operations=[
        {"old_text": "y = 2\n", "new_text": "y = 3\n"},
    ]))

    assert result["status"] == "error"
    assert "not found" in result["error"]
    # File content unchanged
    assert f.read_text() == "x = 1\n"
    # No .bak file created
    assert not (tmp_path / "test.py.bak").exists()


@pytest.mark.asyncio
async def test_duplicate_old_text_rejected(tmp_path):
    """Verify error when old_text appears multiple times."""
    from ascend_agent.tools.file_edit import edit_file

    f = tmp_path / "test.py"
    f.write_text("x = 1\nx = 1\n")

    result = json.loads(await edit_file(file_path=str(f), operations=[
        {"old_text": "x = 1\n", "new_text": "x = 2\n"},
    ]))

    assert result["status"] == "error"
    assert "appears" in result["error"] or "times" in result["error"]
    # File unchanged
    assert f.read_text() == "x = 1\nx = 1\n"


@pytest.mark.asyncio
async def test_multiple_replacements_atomic(tmp_path):
    """Verify two operations applied successfully in one call."""
    from ascend_agent.tools.file_edit import edit_file

    f = tmp_path / "test.py"
    f.write_text("x = 1\ny = 2\n")

    result = json.loads(await edit_file(file_path=str(f), operations=[
        {"old_text": "x = 1\n", "new_text": "x = 10\n"},
        {"old_text": "y = 2\n", "new_text": "y = 20\n"},
    ]))

    assert result["status"] == "ok"
    assert "Applied 2 replacement" in result["message"]
    # Both replacements applied
    assert f.read_text() == "x = 10\ny = 20\n"
    # Backup exists
    assert (tmp_path / "test.py.bak").exists()


@pytest.mark.asyncio
async def test_multiple_replacements_failure_rollback(tmp_path):
    """Verify no partial apply when one operation fails validation."""
    from ascend_agent.tools.file_edit import edit_file

    f = tmp_path / "test.py"
    f.write_text("x = 1\ny = 2\n")

    # Second operation has invalid old_text
    result = json.loads(await edit_file(file_path=str(f), operations=[
        {"old_text": "x = 1\n", "new_text": "x = 10\n"},
        {"old_text": "zzz_not_found\n", "new_text": "wrong\n"},
    ]))

    assert result["status"] == "error"
    assert "not found" in result["error"]
    # No .bak file (validation fails before backup)
    assert not (tmp_path / "test.py.bak").exists()
    # File content unchanged
    assert f.read_text() == "x = 1\ny = 2\n"


@pytest.mark.asyncio
async def test_path_traversal_prevented(tmp_path):
    """Verify path traversal is blocked when repo_path is provided."""
    from ascend_agent.tools.file_edit import edit_file

    repo_path = str(tmp_path)
    # Attempt to edit a file outside the repo
    result = json.loads(await edit_file(
        file_path="/etc/passwd",
        operations=[{"old_text": "root", "new_text": "admin"}],
        repo_path=repo_path,
    ))

    assert result["status"] == "error"
    assert "outside repository root" in result["error"]


@pytest.mark.asyncio
async def test_nonexistent_file_returns_error(tmp_path):
    """Verify error when the target file does not exist."""
    from ascend_agent.tools.file_edit import edit_file

    nonexistent = tmp_path / "does_not_exist.py"
    result = json.loads(await edit_file(
        file_path=str(nonexistent),
        operations=[{"old_text": "x", "new_text": "y"}],
    ))

    assert result["status"] == "error"
    assert "File not found" in result["error"]


@pytest.mark.asyncio
async def test_empty_operations_returns_error(tmp_path):
    """Verify error when empty operations list is provided."""
    from ascend_agent.tools.file_edit import edit_file

    f = tmp_path / "test.py"
    f.write_text("x = 1\n")
    result = json.loads(await edit_file(
        file_path=str(f),
        operations=[],
    ))

    assert result["status"] == "error"
    assert "No operations" in result["error"]
