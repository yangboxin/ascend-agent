import sys

from mcp.server.fastmcp import FastMCP

from ascend_agent.tools.code_search import search_code
from ascend_agent.tools.file_edit import edit_file
from ascend_agent.tools.shell_exec import exec_shell
from ascend_agent.tools.test_runner import run_test

mcp = FastMCP("ascend-agent-tools")

mcp.tool(name="search_code", description="Search for a regex pattern in Python files in the codebase")(search_code)
mcp.tool(name="edit_file", description="[STUB] Edit a file in the codebase — implemented in Phase 3")(edit_file)
mcp.tool(name="exec_shell", description="[STUB] Execute a shell command — implemented in Phase 4")(exec_shell)
mcp.tool(name="run_test", description="[STUB] Run a test command — implemented in Phase 5")(run_test)

if __name__ == "__main__":
    # Collect registered tool names for startup banner
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    print("Starting Ascend Agent MCP server...", file=sys.stderr)
    print(f"Registered tools: {', '.join(sorted(tool_names))}", file=sys.stderr)
    print("Listening on STDIO transport...", file=sys.stderr)
    sys.stderr.flush()
    mcp.run()
