def test_router_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from ascend_agent.diagnosis.router import ModelRouter

    try:
        ModelRouter()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "OPENAI_API_KEY" in str(e)


def test_router_uses_default_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    assert router._model == "gpt-4o"


def test_router_uses_env_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ASCEND_DIAGNOSIS_MODEL", "gpt-4o-mini")
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    assert router._model == "gpt-4o-mini"


def test_router_uses_explicit_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter(model="gpt-4o-2024-08-06")
    assert router._model == "gpt-4o-2024-08-06"
