"""Workflow runner — bridges legacy workflow commands with the runtime.

Provides a unified entry point for the four domain workflows (diagnose,
fix, reproduce, verify) so that every code path shares the same provider
resolution, permission model, and session infrastructure.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ascend_agent.config import Settings
from ascend_agent.context.models import ConfigEnv, ContextDocument
from ascend_agent.context.repo import RepoScanner
from ascend_agent.context.trace import trace_from_file, trace_from_text
from ascend_agent.diagnosis.engine import Engine
from ascend_agent.diagnosis.fix_engine import FixEngine
from ascend_agent.diagnosis.models import (
    DiagnosisResult,
    FixGenerationResult,
    ReproductionResult,
    VerificationResult,
)
from ascend_agent.providers.router import ModelRouter, create_router
from ascend_agent.reproduction.engine import ReproductionEngine
from ascend_agent.runtime.permissions import PermissionMode
from ascend_agent.verification.engine import VerificationEngine


def _run_async(coro: Any) -> Any:
    """Run a coroutine from sync code without leaking event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    if loop.is_running():
        raise RuntimeError(
            "Cannot run async engine from inside an active event loop"
        )
    return loop.run_until_complete(coro)


@dataclass
class WorkflowRunner:
    """Unified entry point for domain workflow operations.

    All four workflows share the same provider resolution and can
    optionally participate in the runtime permission model.
    """

    provider: str = "openai"
    permission_mode: PermissionMode = "default"
    _router: ModelRouter | None = field(default=None, repr=False)
    _settings: Settings | None = field(default=None, repr=False)

    @property
    def router(self) -> ModelRouter:
        """Lazily create the ModelRouter for the configured provider."""
        if self._router is None:
            self._router = create_router(provider=self.provider)
        return self._router

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            self._settings = Settings()
        return self._settings

    # -- diagnosis -------------------------------------------------------

    def run_diagnosis(
        self,
        repo_path: str,
        *,
        trace_text: str | None = None,
        trace_file: str | None = None,
        search_tool: Callable | None = None,
    ) -> tuple[DiagnosisResult, ContextDocument]:
        """Run the full diagnosis workflow.

        Returns (diagnosis_result, context_document) for display and
        optional JSON output.
        """
        repo = Path(repo_path).resolve()
        if not repo.is_dir():
            raise ValueError(f"Repository path does not exist: {repo}")
        if bool(trace_text) == bool(trace_file):
            raise ValueError("Provide exactly one of trace_text or trace_file")

        trace = trace_from_text(trace_text or "")
        if trace_file:
            trace = trace_from_file(Path(trace_file))

        doc = ContextDocument(
            repo=RepoScanner().scan(repo),
            trace=trace,
            config_env=ConfigEnv(
                python_version=self.settings.python_version,
                platform=self.settings.platform,
                env_vars=self.settings.env_vars,
            ),
        )
        result = Engine(
            router=self.router,
            repo_path=str(repo),
            search_tool=search_tool,
        ).diagnose(doc)
        return result, doc

    # -- fix -------------------------------------------------------------

    def run_fix(
        self,
        diagnosis: DiagnosisResult,
        repo_path: str,
    ) -> FixGenerationResult:
        """Generate search-and-replace fix suggestions for a diagnosis."""
        return FixEngine(
            router=self.router,
            repo_path=str(Path(repo_path).resolve()),
        ).generate_fixes(diagnosis)

    # -- reproduce -------------------------------------------------------

    def run_reproduce(
        self,
        diagnosis: DiagnosisResult,
        repo_path: str,
        *,
        trace_text: str | None = None,
    ) -> ReproductionResult:
        """Reproduce diagnosed issues by executing reproduction commands."""
        trace = trace_from_text(trace_text) if trace_text else None
        return _run_async(
            ReproductionEngine(
                router=self.router,
                repo_path=str(Path(repo_path).resolve()),
                settings=self.settings,
            ).reproduce(diagnosis, trace=trace)
        )

    # -- verify ----------------------------------------------------------

    def run_verify(
        self,
        reproduction: ReproductionResult,
        repo_path: str,
        *,
        timeout: int = 300,
    ) -> VerificationResult:
        """Verify fixes by running relevant tests."""
        tool_settings = Settings()
        tool_settings.test_timeout = timeout
        return _run_async(
            VerificationEngine(
                router=self.router,
                repo_path=str(Path(repo_path).resolve()),
                settings=tool_settings,
            ).verify(reproduction)
        )
