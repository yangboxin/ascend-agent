import pytest


@pytest.mark.asyncio
async def test_search_regex_pattern(tmp_path):
    from ascend_agent.tools.code_search import search_code
    (tmp_path / "test.py").write_text("x = 42  # the answer\n")
    result = await search_code("42", str(tmp_path))
    assert "test.py" in result
    assert "42" in result


@pytest.mark.asyncio
async def test_search_no_matches(tmp_path):
    from ascend_agent.tools.code_search import search_code
    (tmp_path / "empty.py").write_text("y = 1\n")
    result = await search_code("ZZZZNOTFOUND", str(tmp_path))
    assert "No matches found" in result


@pytest.mark.asyncio
async def test_search_empty_dir(tmp_path):
    from ascend_agent.tools.code_search import search_code
    result = await search_code("anything", str(tmp_path))
    assert "No matches found" in result


@pytest.mark.asyncio
async def test_search_includes_config_files(tmp_path):
    from ascend_agent.tools.code_search import search_code

    (tmp_path / "config.yaml").write_text("hidden_size: 8192\n", encoding="utf-8")

    result = await search_code("hidden_size", str(tmp_path))

    assert "config.yaml" in result
    assert "hidden_size" in result
