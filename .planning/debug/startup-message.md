---
status: resolved
trigger: "python -m ascend_agent.tools.server does not output a startup or tool registration message"
created: 2026-05-21T12:00:00Z
updated: 2026-05-21T12:01:00Z
---

## Current Focus

hypothesis: "FastMCP stdio transport prints nothing to stdout because stdout is reserved for MCP JSON-RPC protocol messages, and server.py doesn't output anything to stderr either"
test: "Verify by reading server.py (already read) and confirming there is no print/log to stderr before mcp.run()"
expecting: "Confirmed — no startup message in server.py at all"
next_action: "Document the root cause and recommended fix"

## Symptoms

expected: Server should output a startup message confirming it's running and which tools are registered.
actual: The bash window goes blank after `python -m ascend_agent.tools.server` and the user must Ctrl-C to exit.
errors: None (no error messages)
reproduction: Run `python -m ascend_agent.tools.server` from the project root.
started: Initial implementation (Phase 1 Architecture Foundation)

## Eliminated

- hypothesis: "The issue is a bug in FastMCP library"
  evidence: FastMCP's `run_stdio_async` intentionally does not print to stdout (it's reserved for protocol). This is by design.
  timestamp: 2026-05-21T12:00:00Z

## Evidence

- timestamp: 2026-05-21T12:00:00Z
  checked: src/ascend_agent/tools/server.py
  found: The file has 16 lines. It creates a FastMCP server, registers 4 tools via `mcp.tool()`, and calls `mcp.run()` in the `__main__` block. There are zero print/log statements anywhere.
  implication: The server produces no stdout or stderr output before or during startup. The only output would be MCP JSON-RPC protocol messages on stdout (which happen only when a client connects and sends requests).

- timestamp: 2026-05-21T12:00:00Z
  checked: FastMCP.run() -> run_stdio_async() -> stdio_server()
  found: `run_stdio_async()` (server.py line 753) enters `stdio_server()` context manager and then calls `self._mcp_server.run()`. The `stdio_server()` (stdio.py) only sets up stdin reader and stdout writer task groups. No startup message is printed anywhere in this chain.
  implication: The stdio transport provides zero user feedback by design — stdout is reserved for MCP JSON-RPC protocol messages.

- timestamp: 2026-05-21T12:00:00Z
  checked: FastMCP's `lifespan` parameter
  found: FastMCP accepts a `lifespan` async context manager that is executed when the server starts. This could be used to print startup messages to stderr, but server.py does not use it.
  implication: A `lifespan` hook is available but unused.

- timestamp: 2026-05-21T12:00:00Z
  checked: FastMCP logging utilities (fastmcp/utilities/logging.py)
  found: `configure_logging()` sets up logging (RichHandler to stderr if rich is available, or default StreamHandler). FastMCP init calls this, but nothing is logged at startup — only during request processing.
  implication: The logging infrastructure exists and writes to stderr, but no startup log message is emitted.

- timestamp: 2026-05-21T12:00:00Z
  checked: MCP protocol design (stdio.py)
  found: `stdio_server()` wraps `sys.stdout` and writes JSON-RPC messages to it. stdout is exclusively for protocol communication. stderr is available for diagnostics.
  implication: Any startup message MUST go to stderr, not stdout. Printing to stdout would corrupt the MCP protocol.

## Resolution

root_cause: "FastMCP's stdio transport reserves stdout for MCP JSON-RPC protocol messages and intentionally prints nothing to stdout. server.py has no stderr output before `mcp.run()`, so no startup message appears."
fix: "Print a startup message to stderr using `print(..., file=sys.stderr)` or `logging.info()` (which goes to stderr via the configured RichHandler). Best practice: add a lifespan handler that prints to stderr, or print directly to stderr before `mcp.run()`."
verification: "Run `python -m ascend_agent.tools.server 2>&1 | head -5` — should see startup message on stderr."
files_changed:
  - src/ascend_agent/tools/server.py
