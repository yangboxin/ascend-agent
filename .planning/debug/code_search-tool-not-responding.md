---
status: investigating
trigger: "MCP server's code_search tool does not respond / does not return search results"
created: 2026-05-21T00:00:00Z
updated: 2026-05-21T00:00:00Z
---

## Current Focus

hypothesis: "Tool name mismatch — registered as 'search_code' but expected/document as 'code_search'"
test: "Verified via server tool listing: mcp._tool_manager.list_tools() shows name='search_code'"
expecting: "Tool name should be 'code_search' per all planning docs and UAT"
next_action: "Report root cause: rename 'search_code' to 'code_search' in server.py registration"

## Symptoms

expected: MCP server's code_search tool accepts `pattern` and `path` params, returns matching Python file lines with line numbers. Results include file paths and matched content.
actual: Code search tool does not respond / returns no results. User reported "no".
errors: N/A
reproduction: N/A (user confirmed it doesn't work)
started: Always broken — Phase 1 tool registration misnamed

## Eliminated

- hypothesis: "rg (ripgrep) not installed causes failure"
  evidence: Native Python fallback (_native_search) exists and tests pass without rg. Tests use tmp_path and work perfectly.
  timestamp: 2026-05-21T00:00:00Z

- hypothesis: "Import error or runtime failure in code_search.py"
  evidence: All 3 code_search tests pass (test_search_regex_pattern, test_search_no_matches, test_search_empty_dir).
  timestamp: 2026-05-21T00:00:00Z

- hypothesis: "Function signature issue — wrong parameter names"
  evidence: Function signature is `search_code(pattern: str, path: str = ".", ctx: Context | None = None)` which matches expected params. Tests call it successfully.
  timestamp: 2026-05-21T00:00:00Z

## Evidence

- timestamp: 2026-05-21T00:00:00Z
  checked: server.py tool registration
  found: Line 10 registers tool as `mcp.tool(name="search_code", ...)` — name is "search_code"
  implication: The tool is registered with a name that does not match the documented/expected name

- timestamp: 2026-05-21T00:00:00Z
  checked: All planning docs referencing tool name
  found: UAT (01-UAT.md:39-44), VERIFICATION (01-VERIFICATION.md:60), SUMMARY (01-04-SUMMARY.md:12), PLAN (01-04-PLAN.md:58) all refer to the tool as "code_search"
  implication: The project spec consistently expects the tool to be called "code_search"

- timestamp: 2026-05-21T00:00:00Z
  checked: MCP server tool listing at runtime
  found: `mcp._tool_manager.list_tools()` returns tool names: ["search_code", "edit_file", "exec_shell", "run_test"]
  implication: An MCP client calling `tools/call` with name "code_search" would receive a "tool not found" error

- timestamp: 2026-05-21T00:00:00Z
  checked: test_server.py assertion
  found: Line 7 asserts `"search_code" in names` — this test validates the wrong name
  implication: The test perpetuates the bug by checking against the incorrect implementation name

- timestamp: 2026-05-21T00:00:00Z
  checked: rg availability
  found: rg not installed; native fallback works (all 3 code_search tests pass)
  implication: No issue with rg — native fallback is functional

## Resolution

root_cause: "The MCP tool is registered with the wrong name. server.py line 10 uses `name='search_code'`, but the project spec (UAT, planning docs, and user expectation) all refer to the tool as `code_search`. When an MCP client calls `code_search`, the server does not recognize it because the tool is only registered as `search_code`."
fix: "Change the tool name from 'search_code' to 'code_search' in server.py, and update the test assertion in test_server.py accordingly."
verification: ""
files_changed:
  - src/ascend_agent/tools/server.py
  - tests/test_tools/test_server.py
