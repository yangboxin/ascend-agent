from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from ascend_agent.diagnosis.models import FixSuggestion
from ascend_agent.tools.file_edit import edit_file

EditFunc = Callable[[str, list[dict], str | None], Awaitable[str]]


@dataclass(frozen=True)
class AppliedFixFile:
    file_path: str
    ok: bool
    error: str = ""


@dataclass(frozen=True)
class ApplyFixesResult:
    files: list[AppliedFixFile]

    @property
    def applied(self) -> int:
        return sum(1 for file in self.files if file.ok)

    @property
    def failed(self) -> int:
        return sum(1 for file in self.files if not file.ok)


def group_fix_operations(suggestions: list[FixSuggestion]) -> dict[str, list[dict]]:
    by_file: dict[str, list[dict]] = defaultdict(list)
    for suggestion in suggestions:
        for replacement in suggestion.replacements:
            by_file[suggestion.file_path].append(
                {"old_text": replacement.old_text, "new_text": replacement.new_text}
            )
    return dict(by_file)


async def apply_fix_suggestions(
    suggestions: list[FixSuggestion],
    repo_path: str,
    *,
    edit_func: EditFunc = edit_file,
) -> ApplyFixesResult:
    files: list[AppliedFixFile] = []

    for file_path, operations in group_fix_operations(suggestions).items():
        resolved_path = Path(repo_path) / file_path
        try:
            result_str = await edit_func(str(resolved_path), operations, repo_path)
            result = json.loads(result_str)
        except Exception as exc:
            files.append(AppliedFixFile(file_path=file_path, ok=False, error=str(exc)))
            continue

        if result.get("status") == "ok":
            files.append(AppliedFixFile(file_path=file_path, ok=True))
        else:
            files.append(
                AppliedFixFile(
                    file_path=file_path,
                    ok=False,
                    error=result.get("error", "unknown error"),
                )
            )

    return ApplyFixesResult(files=files)
