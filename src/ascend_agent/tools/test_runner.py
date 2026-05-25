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
        if repo_path is None:
            from ascend_agent.config import Settings

            settings = Settings()
            repo_path = settings.repo_path or str(Path.cwd())

        from ascend_agent.diagnosis.router import ModelRouter
        from ascend_agent.verification.engine import VerificationEngine

        router = ModelRouter()
        settings = __import__("ascend_agent.config", fromlist=["Settings"]).Settings()
        settings.test_timeout = timeout
        engine = VerificationEngine(router=router, repo_path=repo_path, settings=settings)
        result = await engine.verify(reproduction)

        if ctx is not None:
            ctx.info(
                f"run_test: status={result.status}, "
                f"{result.passed} passed, {result.failed} failed"
            )

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
