import json

from mcp.server.fastmcp import Context


async def exec_shell(command: str, ctx: Context | None = None) -> str:
    return json.dumps({
        "status": "stub",
        "message": "exec_shell not implemented in Phase 1. Full implementation planned for Phase 4 (Reproduction).",
    })
