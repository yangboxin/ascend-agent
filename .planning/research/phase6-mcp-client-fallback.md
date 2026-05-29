# Phase 6 MCP Client Fallback

Date: 2026-05-29

## Scope

Phase 6 upgrades diagnosis tool wiring from a local-only seam to a real MCP
client path with automatic local fallback.

## Implemented

- Added real `MCPToolClient` based on MCP SDK:
  - `mcp.client.stdio.StdioServerParameters`
  - `mcp.client.stdio.stdio_client`
  - `mcp.client.session.ClientSession`
  - `call_tool("code_search", ...)`
- Added `FallbackToolClient`:
  - tries MCP first,
  - falls back to local tool client on any MCP failure.
- Added backend selection in `create_tool_client()`:
  - `ASCEND_DIAGNOSIS_TOOL_BACKEND=local|mcp|auto`
  - `auto` and `mcp` use MCP+fallback,
  - `local` uses in-process tools only.
- Added config field:
  - `diagnosis_tool_backend` in `Settings`.

## Verification

Target tests:

```text
python -m pytest tests/test_diagnosis/test_tool_client.py \
  tests/test_cli.py tests/test_diagnosis/test_engine.py \
  tests/test_diagnosis/test_evidence_validation_baseline.py -q

34 passed
```

Phase 0-6 target suite:

```text
python -m pytest tests/test_context.py tests/test_context_trace_regressions.py \
  tests/test_diagnosis/test_engine.py \
  tests/test_diagnosis/test_evidence_validation_baseline.py \
  tests/test_diagnosis/test_tool_client.py \
  tests/test_diagnosis/test_router.py tests/test_tools/test_code_search.py \
  tests/test_cli.py -q

69 passed
```
