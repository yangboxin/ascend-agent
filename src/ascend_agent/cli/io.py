"""Small CLI I/O helpers shared by command adapters."""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Any


def read_text_input(path: str | None, *, stdin_required: bool = False) -> str:
    if path is not None:
        return Path(path).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    if stdin_required:
        raise ValueError("Provide a file path or pipe JSON via stdin.")
    return ""


def load_model_json(model: type[Any], path: str | None, *, label: str) -> Any:
    try:
        data = read_text_input(path, stdin_required=True)
    except OSError as exc:
        raise ValueError(f"Failed to read {label} JSON: {exc}") from exc
    try:
        return model.model_validate_json(data)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Failed to parse {label} JSON: {exc}") from exc


def write_model_json(model: Any, path: str) -> None:
    Path(path).write_text(model.model_dump_json(indent=2), encoding="utf-8")


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value
