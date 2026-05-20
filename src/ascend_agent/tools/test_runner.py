import json

from mcp.server.fastmcp import Context


async def run_test(command: str, path: str | None = None, ctx: Context | None = None) -> str:
    return json.dumps({
        "status": "stub",
        "message": "run_test not implemented in Phase 1. Full implementation planned for Phase 5 (Verification).",
    })
