"""run_test MCP tool — orchestrates VerificationEngine to run relevant tests.

Accepts a ReproductionResult JSON string, maps changed files to test files,
executes the relevant tests via pytest, and returns a VerificationResult JSON.
"""

import json
import logging
from pathlib import Path

from mcp.server.fastmcp import Context

logger = logging.getLogger(__name__)


async def run_test(
    reproduction_json: str,
    repo_path: str | None = None,
    timeout: int = 300,
    ctx: Context | None = None,
) -> str:
    """Run relevant tests to verify fixes.

    Accepts a ReproductionResult JSON, maps changed files to test files,
    executes tests via pytest, and returns a VerificationResult as JSON
    with pass/fail details.
    """
    try:
        from ascend_agent.diagnosis.models import ReproductionResult

        reproduction = ReproductionResult.model_validate_json(reproduction_json)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "summary": f"Failed to parse reproduction JSON: {e}",
            "tests_found": 0,
            "tests_run": 0,
            "passed": 0,
            "failed": 0,
            "errors": 1,
        })

    try:
        from ascend_agent.config import Settings
        from ascend_agent.diagnosis.router import create_router
        from ascend_agent.verification.engine import VerificationEngine

        settings = Settings()
        settings.test_timeout = timeout
        resolved_repo_path = repo_path or settings.repo_path or str(Path.cwd())
        router = create_router("openai")
        engine = VerificationEngine(router=router, repo_path=resolved_repo_path, settings=settings)
        result = await engine.verify(reproduction)

        if ctx is not None:
            msg = f"run_test: status={result.status}, {result.passed} passed, {result.failed} failed"
            if hasattr(ctx, "info") and not hasattr(ctx.info, "__await__"):
                ctx.info(msg)
            else:
                await ctx.info(msg)

        return result.model_dump_json()
    except Exception as e:
        logger.error("Test runner error: %s", e)
        return json.dumps({
            "status": "error",
            "summary": f"Test runner error: {e}",
            "tests_found": 0,
            "tests_run": 0,
            "passed": 0,
            "failed": 0,
            "errors": 1,
        })
