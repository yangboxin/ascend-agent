"""Domain workflow tools exposed to platform agents."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from ascend_agent.config import Settings, settings
from ascend_agent.context.models import ConfigEnv, ContextDocument
from ascend_agent.context.repo import RepoScanner
from ascend_agent.context.trace import trace_from_file, trace_from_text
from ascend_agent.diagnosis.engine import Engine
from ascend_agent.diagnosis.fix_engine import FixEngine
from ascend_agent.diagnosis.models import (
    DiagnosisOutput,
    DiagnosisResult,
    FixGenerationResult,
    ReproductionResult,
    VerificationResult,
)
from ascend_agent.diagnosis.router import create_router
from ascend_agent.reproduction.engine import ReproductionEngine
from ascend_agent.verification.engine import VerificationEngine


async def diagnose_trace(
    repo_path: str = ".",
    trace_text: str | None = None,
    trace_file: str | None = None,
    provider: str = "openai",
    working_dir: str | None = None,
) -> str:
    """Diagnose a trace against a repository and return DiagnosisResult JSON."""
    root = _root(working_dir)
    repo = _resolve_inside_root(root, repo_path)
    if not repo.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {repo}")
    if bool(trace_text) == bool(trace_file):
        raise ValueError("Provide exactly one of trace_text or trace_file")

    trace = trace_from_text(trace_text or "")
    if trace_file:
        trace_path = _resolve_inside_root(root, trace_file)
        trace = trace_from_file(trace_path)

    doc = ContextDocument(
        repo=RepoScanner().scan(repo),
        trace=trace,
        config_env=ConfigEnv(
            python_version=settings.python_version,
            platform=settings.platform,
            env_vars=settings.env_vars,
        ),
    )
    router = create_router(provider=provider)
    result = Engine(router=router, repo_path=str(repo)).diagnose(doc)
    return result.model_dump_json()


async def generate_fixes(
    diagnosis_json: str,
    repo_path: str = ".",
    provider: str = "openai",
    working_dir: str | None = None,
) -> str:
    """Generate search-and-replace fixes for a diagnosis JSON document."""
    root = _root(working_dir)
    repo = _resolve_inside_root(root, repo_path)
    diagnosis = _diagnosis_from_json(diagnosis_json)
    _validate_diagnosis_paths(diagnosis, repo)

    router = create_router(provider=provider)
    result = FixEngine(router=router, repo_path=str(repo)).generate_fixes(diagnosis)
    _validate_fix_paths(result, repo)
    return result.model_dump_json()


async def reproduce_issue(
    diagnosis_json: str,
    repo_path: str = ".",
    trace_text: str | None = None,
    provider: str = "openai",
    working_dir: str | None = None,
) -> str:
    """Run the reproduction workflow for a diagnosis JSON document."""
    root = _root(working_dir)
    repo = _resolve_inside_root(root, repo_path)
    diagnosis = _diagnosis_from_json(diagnosis_json)
    _validate_diagnosis_paths(diagnosis, repo)
    trace = trace_from_text(trace_text) if trace_text else None

    router = create_router(provider=provider)
    result = await ReproductionEngine(router=router, repo_path=str(repo)).reproduce(
        diagnosis,
        trace=trace,
    )
    _validate_reproduction_paths(result, repo)
    return result.model_dump_json()


async def verify_fix(
    reproduction_json: str,
    repo_path: str = ".",
    provider: str = "openai",
    timeout: int = 300,
    working_dir: str | None = None,
) -> str:
    """Verify a reproduction result with focused tests."""
    root = _root(working_dir)
    repo = _resolve_inside_root(root, repo_path)
    reproduction = ReproductionResult.model_validate_json(reproduction_json)
    _validate_reproduction_paths(reproduction, repo)

    tool_settings = Settings()
    tool_settings.test_timeout = timeout
    router = create_router(provider=provider)
    result = await VerificationEngine(
        router=router,
        repo_path=str(repo),
        settings=tool_settings,
    ).verify(reproduction)
    return result.model_dump_json()


def run_async_tool(coro: Any) -> Any:
    """Run a coroutine from sync CLI code without leaking event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    if loop.is_running():
        raise RuntimeError("Cannot synchronously run workflow tool inside an active event loop")
    return loop.run_until_complete(coro)


def _root(working_dir: str | None) -> Path:
    return Path(working_dir or Path.cwd()).resolve()


def _resolve_inside_root(root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        common = os.path.commonpath([str(root), str(resolved)])
    except ValueError as exc:
        raise ValueError(f"Path {value!r} is outside working directory {root}") from exc
    if common != str(root):
        raise ValueError(f"Path {value!r} is outside working directory {root}")
    return resolved


def _diagnosis_from_json(data: str) -> DiagnosisResult:
    try:
        loaded = json.loads(data)
    except json.JSONDecodeError:
        return DiagnosisResult.model_validate_json(data)
    if isinstance(loaded, dict) and "diagnosis_result" in loaded:
        return DiagnosisOutput.model_validate(loaded).diagnosis_result
    return DiagnosisResult.model_validate(loaded)


def _validate_diagnosis_paths(diagnosis: DiagnosisResult, repo: Path) -> None:
    for hypothesis in diagnosis.hypotheses:
        for evidence in hypothesis.evidence:
            _resolve_inside_root(repo, evidence.file_path)


def _validate_fix_paths(result: FixGenerationResult, repo: Path) -> None:
    for suggestion in result.suggestions:
        _resolve_inside_root(repo, suggestion.file_path)
        for replacement in suggestion.replacements:
            _resolve_inside_root(repo, replacement.file_path)


def _validate_reproduction_paths(result: ReproductionResult, repo: Path) -> None:
    if result.repo_path:
        _resolve_inside_root(repo, result.repo_path)
    for path in [*result.files_changed, result.repro_file]:
        if path:
            _resolve_inside_root(repo, path)

