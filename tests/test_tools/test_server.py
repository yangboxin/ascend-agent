from ascend_agent.tools.server import mcp


def test_mcp_server_lists_tools():
    tools = mcp._tool_manager.list_tools()
    names = [t.name for t in tools]
    assert "code_search" in names
    assert "edit_file" in names
    assert "exec_shell" in names
    assert "run_test" in names
    assert len(names) == 4


def test_tool_result_format(tmp_path):
    from ascend_agent.tools.code_search import search_code
    import inspect
    sig = inspect.signature(search_code)
    assert "pattern" in sig.parameters
    assert "path" in sig.parameters
