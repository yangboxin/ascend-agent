import json

from mcp.server.fastmcp import Context


async def edit_file(path: str, content: str, ctx: Context | None = None) -> str:
    return json.dumps({
        "status": "stub",
        "message": "edit_file not implemented in Phase 1. Full implementation planned for Phase 3 (Fix Generation).",
    })
