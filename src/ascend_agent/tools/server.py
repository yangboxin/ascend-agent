import sys

from mcp.server.fastmcp import FastMCP

from ascend_agent.tools.code_search import search_code
from ascend_agent.tools.file_edit import edit_file
from ascend_agent.tools.shell_exec import exec_shell
from ascend_agent.tools.test_runner import run_test

mcp = FastMCP("ascend-agent-tools")

mcp.tool(name="code_search", description="Search for a regex pattern in Python files in the codebase")(search_code)
mcp.tool(name="edit_file", description="Edit a file using search-and-replace operations with automatic .bak backup")(edit_file)
mcp.tool(name="exec_shell", description="Execute a shell command locally or via SSH. Returns JSON with status, stdout, stderr, and exit_code. Non-interactive only — no PTY allocation.")(exec_shell)
mcp.tool(name="run_test", description="Run relevant tests to verify fixes. Accepts a ReproductionResult JSON, maps changed files to test files, executes tests via pytest, and returns a VerificationResult as JSON with pass/fail details.")(run_test)

if __name__ == "__main__":
    # Collect registered tool names for startup banner
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    print("Starting Ascend Agent MCP server...", file=sys.stderr)
    print(f"Registered tools: {', '.join(sorted(tool_names))}", file=sys.stderr)
    print("Listening on STDIO transport...", file=sys.stderr)
    sys.stderr.flush()
    mcp.run()
