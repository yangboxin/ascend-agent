import json

import pytest

from ascend_agent.diagnosis.fix_apply import apply_fix_suggestions, group_fix_operations
from ascend_agent.diagnosis.models import FixSuggestion, Replacement


def _suggestion(file_path: str, old_text: str, new_text: str) -> FixSuggestion:
    return FixSuggestion(
        file_path=file_path,
        diff_patch="",
        explanation="test",
        hypothesis_id=0,
        replacements=[
            Replacement(file_path=file_path, old_text=old_text, new_text=new_text)
        ],
    )


def test_group_fix_operations_groups_replacements_by_file():
    grouped = group_fix_operations([
        _suggestion("a.py", "x", "y"),
        _suggestion("a.py", "m", "n"),
        _suggestion("b.py", "old", "new"),
    ])

    assert grouped == {
        "a.py": [
            {"old_text": "x", "new_text": "y"},
            {"old_text": "m", "new_text": "n"},
        ],
        "b.py": [{"old_text": "old", "new_text": "new"}],
    }


@pytest.mark.asyncio
async def test_apply_fix_suggestions_reports_success_and_failures(tmp_path):
    async def fake_edit(file_path, operations, repo_path):
        if file_path.endswith("bad.py"):
            return json.dumps({"status": "error", "error": "old_text not found"})
        return json.dumps({"status": "ok"})

    result = await apply_fix_suggestions(
        [
            _suggestion("good.py", "x", "y"),
            _suggestion("bad.py", "m", "n"),
        ],
        str(tmp_path),
        edit_func=fake_edit,
    )

    assert result.applied == 1
    assert result.failed == 1
    assert result.files[0].file_path == "good.py"
    assert result.files[0].ok is True
    assert result.files[1].file_path == "bad.py"
    assert result.files[1].ok is False
    assert result.files[1].error == "old_text not found"
