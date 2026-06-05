from ascend_agent.tools.server import mcp


def test_mcp_server_lists_tools():
    tools = mcp._tool_manager.list_tools()
    names = [t.name for t in tools]
    # Implementation tools
    assert "code_search" in names
    assert "edit_file" in names
    assert "exec_shell" in names
    assert "run_test" in names
    # Domain workflow tools
    assert "diagnose_trace" in names
    assert "generate_fixes" in names
    assert "reproduce_issue" in names
    assert "verify_fix" in names
    assert len(names) == 8


def test_tool_result_format(tmp_path):
    from ascend_agent.tools.code_search import search_code
    import inspect
    sig = inspect.signature(search_code)
    assert "pattern" in sig.parameters
    assert "path" in sig.parameters
