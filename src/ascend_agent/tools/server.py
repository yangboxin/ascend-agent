import sys
from types import SimpleNamespace

from mcp.server.fastmcp import FastMCP

from ascend_agent.tools.code_search import search_code
from ascend_agent.tools.file_edit import edit_file
from ascend_agent.tools.shell_exec import exec_shell
from ascend_agent.tools.test_runner import run_test
from ascend_agent.tools.workflows import (
    diagnose_trace,
    generate_fixes,
    reproduce_issue,
    verify_fix,
)

mcp = FastMCP("ascend-agent-tools")

_REGISTERED_TOOLS: list[SimpleNamespace] = []


def _register_tool(name: str, description: str, func):
    _REGISTERED_TOOLS.append(SimpleNamespace(name=name, description=description))
    return mcp.tool(name=name, description=description)(func)


# Implementation tools
_register_tool(
    "code_search",
    "Search for a regex pattern in Python files in the codebase",
    search_code,
)
_register_tool(
    "edit_file",
    "Edit a file using search-and-replace operations with automatic .bak backup",
    edit_file,
)
_register_tool(
    "exec_shell",
    "Execute a shell command locally or via SSH. Returns JSON with status, stdout, stderr, and exit_code. Non-interactive only — no PTY allocation.",
    exec_shell,
)
_register_tool(
    "run_test",
    "Run relevant tests to verify fixes. Accepts a ReproductionResult JSON, maps changed files to test files, executes tests via pytest, and returns a VerificationResult as JSON with pass/fail details.",
    run_test,
)

# Domain workflow tools
_register_tool(
    "diagnose_trace",
    "Diagnose a stack trace against a code repository. Provide repo_path and exactly one of trace_text or trace_file. Returns DiagnosisResult as JSON.",
    diagnose_trace,
)
_register_tool(
    "generate_fixes",
    "Generate search-and-replace fixes from a diagnosis JSON document. Provide diagnosis_json (JSON string) and repo_path (default '.')",
    generate_fixes,
)
_register_tool(
    "reproduce_issue",
    "Reproduce a diagnosed issue by executing reproduction commands. Provide diagnosis_json (JSON string) and repo_path (default '.')",
    reproduce_issue,
)
_register_tool(
    "verify_fix",
    "Verify a fix by running relevant tests. Provide reproduction_json (JSON string), repo_path (default '.'), and optional timeout in seconds (default 300).",
    verify_fix,
)

if not hasattr(mcp, "_tool_manager"):
    mcp._tool_manager = SimpleNamespace(list_tools=lambda: list(_REGISTERED_TOOLS))

if __name__ == "__main__":
    # Collect registered tool names for startup banner
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    print("Starting Ascend Agent MCP server...", file=sys.stderr)
    print(f"Registered tools: {', '.join(sorted(tool_names))}", file=sys.stderr)
    print("Listening on STDIO transport...", file=sys.stderr)
    sys.stderr.flush()
    mcp.run()
