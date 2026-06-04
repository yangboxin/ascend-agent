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
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    assert router._model == "gpt-5.5"


def test_router_uses_env_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ASCEND_DIAGNOSIS_MODEL", "gpt-4o-mini")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    assert router._model == "gpt-4o-mini"


def test_router_uses_explicit_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter(model="gpt-4o-2024-08-06")
    assert router._model == "gpt-4o-2024-08-06"


def test_provider_config_defaults():
    from ascend_agent.diagnosis.router import ProviderConfig

    config = ProviderConfig(base_url="https://test.com/v1", api_key="sk-test", default_model="gpt-4o")
    assert config.base_url == "https://test.com/v1"
    assert config.api_key == "sk-test"
    assert config.default_model == "gpt-4o"


def test_create_router_default_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.router import create_router

    router = create_router("openai")
    assert router is not None
    assert router._model == "gpt-5.5"


def test_create_router_with_base_url(monkeypatch):
    monkeypatch.setenv("ASCEND_OPENAI_API_KEY", "sk-custom")
    monkeypatch.setenv("ASCEND_OPENAI_BASE_URL", "https://custom.api.com/v1")
    from ascend_agent.diagnosis.router import create_router

    captured = {}
    def mock_openai_init(self, **kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openai.OpenAI.__init__", mock_openai_init)

    router = create_router("openai")
    assert captured.get("base_url") == "https://custom.api.com/v1"


def test_create_router_prefers_ascend_key(monkeypatch):
    monkeypatch.setenv("ASCEND_OPENAI_API_KEY", "sk-ascend-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-key")
    from ascend_agent.diagnosis.router import create_router

    captured = {}
    def mock_openai_init(self, **kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openai.OpenAI.__init__", mock_openai_init)

    router = create_router("openai")
    assert captured.get("api_key") == "sk-ascend-key"


def test_create_router_non_openai_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ASCEND_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(
        "ascend_agent.providers.config_manager.ConfigManager.get_provider",
        lambda self, name: None,
    )
    from ascend_agent.diagnosis.router import create_router

    try:
        create_router("deepseek")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "ASCEND_DEEPSEEK_API_KEY" in str(e)


def test_create_router_non_openai(monkeypatch):
    monkeypatch.setenv("ASCEND_DEEPSEEK_API_KEY", "sk-deepseek")
    from ascend_agent.diagnosis.router import create_router

    captured = {}
    def mock_openai_init(self, **kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openai.OpenAI.__init__", mock_openai_init)

    router = create_router("deepseek")
    assert captured.get("api_key") == "sk-deepseek"
    assert captured.get("base_url") == "https://api.deepseek.com/v1"


def test_model_router_backward_compat(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    assert router._model == "gpt-5.5"


def test_create_router_deepseek_defaults(monkeypatch):
    monkeypatch.setenv("ASCEND_DEEPSEEK_API_KEY", "sk-deepseek")
    captured = {}
    def mock_openai_init(self, **kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openai.OpenAI.__init__", mock_openai_init)
    from ascend_agent.diagnosis.router import create_router

    router = create_router("deepseek")
    assert captured.get("base_url") == "https://api.deepseek.com/v1"
    assert captured.get("api_key") == "sk-deepseek"
    assert router._model == "deepseek-v4-flash"


def test_create_router_deepseek_custom_base_url(monkeypatch):
    monkeypatch.setenv("ASCEND_DEEPSEEK_API_KEY", "sk-deepseek")
    monkeypatch.setenv("ASCEND_DEEPSEEK_BASE_URL", "https://custom.deepseek.com/v1")
    captured = {}
    def mock_openai_init(self, **kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openai.OpenAI.__init__", mock_openai_init)
    from ascend_agent.diagnosis.router import create_router

    router = create_router("deepseek")
    assert captured.get("base_url") == "https://custom.deepseek.com/v1"


def test_create_router_deepseek_custom_model(monkeypatch):
    monkeypatch.setenv("ASCEND_DEEPSEEK_API_KEY", "sk-deepseek")
    monkeypatch.setenv("ASCEND_DEEPSEEK_DEFAULT_MODEL", "deepseek-v4-pro")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.router import create_router

    router = create_router("deepseek")
    assert router._model == "deepseek-v4-pro"


def test_create_router_qwen_defaults(monkeypatch):
    monkeypatch.setenv("ASCEND_QWEN_API_KEY", "sk-qwen")
    captured = {}
    def mock_openai_init(self, **kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("openai.OpenAI.__init__", mock_openai_init)
    from ascend_agent.diagnosis.router import create_router

    router = create_router("qwen")
    assert captured.get("base_url") == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert router._model == "qwen3.6-plus"


def test_create_router_deepseek_missing_key(monkeypatch):
    monkeypatch.delenv("ASCEND_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "ascend_agent.providers.config_manager.ConfigManager.get_provider",
        lambda self, name: None,
    )
    from ascend_agent.diagnosis.router import create_router

    try:
        create_router("deepseek")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "ASCEND_DEEPSEEK_API_KEY" in str(e)


def test_create_router_qwen_missing_key(monkeypatch):
    monkeypatch.delenv("ASCEND_QWEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "ascend_agent.providers.config_manager.ConfigManager.get_provider",
        lambda self, name: None,
    )
    from ascend_agent.diagnosis.router import create_router

    try:
        create_router("qwen")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "ASCEND_QWEN_API_KEY" in str(e)


def test_completion_fallback_on_400(monkeypatch):
    from unittest.mock import Mock
    from openai import BadRequestError
    from pydantic import BaseModel

    class TestModel(BaseModel):
        result: str

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    mock_parse = Mock(side_effect=BadRequestError("Bad Request", response=Mock(status_code=400), body={}))
    router._client.chat.completions.parse = mock_parse

    mock_create_response = Mock()
    mock_create_response.choices = [Mock(message=Mock(content='{"result": "ok"}'))]
    router._client.chat.completions.create = Mock(return_value=mock_create_response)

    result = router.completion(
        messages=[{"role": "user", "content": "test"}],
        response_model=TestModel,
    )
    assert isinstance(result, TestModel)
    assert result.result == "ok"
    assert mock_parse.called
    assert router._client.chat.completions.create.called
    fallback_messages = router._client.chat.completions.create.call_args.kwargs["messages"]
    assert "Return only one valid JSON object" in fallback_messages[-1]["content"]


def test_completion_fallback_extracts_json_from_markdown(monkeypatch):
    from unittest.mock import Mock
    from openai import BadRequestError
    from pydantic import BaseModel

    class TestModel(BaseModel):
        result: str

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    router._client.chat.completions.parse = Mock(
        side_effect=BadRequestError(
            "Bad Request", response=Mock(status_code=400), body={}
        )
    )

    mock_create_response = Mock()
    mock_create_response.choices = [
        Mock(message=Mock(content='```json\n{"result": "ok"}\n```'))
    ]
    router._client.chat.completions.create = Mock(return_value=mock_create_response)

    result = router.completion(
        messages=[{"role": "user", "content": "test"}],
        response_model=TestModel,
    )

    assert result.result == "ok"


def test_completion_fallback_coerces_plain_search_decision(monkeypatch):
    from unittest.mock import Mock
    from openai import BadRequestError

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.models import SearchDecision
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    router._client.chat.completions.parse = Mock(
        side_effect=BadRequestError(
            "Bad Request", response=Mock(status_code=400), body={}
        )
    )

    mock_create_response = Mock()
    mock_create_response.choices = [
        Mock(message=Mock(content='search pattern: "unknown_symbol"'))
    ]
    router._client.chat.completions.create = Mock(return_value=mock_create_response)

    result = router.completion(
        messages=[{"role": "user", "content": "test"}],
        response_model=SearchDecision,
    )

    assert result.action == "search"
    assert result.searches[0].pattern == "unknown_symbol"


def test_completion_fallback_repairs_null_searches(monkeypatch):
    from unittest.mock import Mock
    from openai import BadRequestError

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.models import SearchDecision
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    router._client.chat.completions.parse = Mock(
        side_effect=BadRequestError(
            "Bad Request", response=Mock(status_code=400), body={}
        )
    )

    mock_create_response = Mock()
    mock_create_response.choices = [
        Mock(message=Mock(content='{"action": "search", "searches": null, "reasoning": "try"}'))
    ]
    router._client.chat.completions.create = Mock(return_value=mock_create_response)

    result = router.completion(
        messages=[{"role": "user", "content": "test"}],
        response_model=SearchDecision,
    )

    assert result.action == "search"
    assert result.searches == []


def test_completion_fallback_coerces_search_as_diagnosis_error(monkeypatch):
    from unittest.mock import Mock
    from openai import BadRequestError

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.models import DiagnosisResult
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    router._client.chat.completions.parse = Mock(
        side_effect=BadRequestError(
            "Bad Request", response=Mock(status_code=400), body={}
        )
    )

    mock_create_response = Mock()
    mock_create_response.choices = [
        Mock(message=Mock(content='search pattern: "unknown_symbol"'))
    ]
    router._client.chat.completions.create = Mock(return_value=mock_create_response)

    result = router.completion(
        messages=[{"role": "user", "content": "test"}],
        response_model=DiagnosisResult,
    )

    assert result.hypotheses == []
    assert result.errors[0].stage == "hypothesis_generation"
    assert "unknown_symbol" in result.errors[0].details


def test_completion_fallback_repairs_zero_evidence_line_numbers(monkeypatch):
    from unittest.mock import Mock
    from openai import BadRequestError

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.models import DiagnosisResult
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    router._client.chat.completions.parse = Mock(
        side_effect=BadRequestError(
            "Bad Request", response=Mock(status_code=400), body={}
        )
    )

    mock_create_response = Mock()
    mock_create_response.choices = [
        Mock(
            message=Mock(
                content=(
                    '{"hypotheses":[{"root_cause":"x","confidence":0.8,'
                    '"evidence":[{"file_path":"a.py","line_number":0,'
                    '"code_snippet":"x","relevance":"r"}]}],'
                    '"errors":[],"iterations_used":2}'
                )
            )
        )
    ]
    router._client.chat.completions.create = Mock(return_value=mock_create_response)

    result = router.completion(
        messages=[{"role": "user", "content": "test"}],
        response_model=DiagnosisResult,
    )

    assert result.hypotheses[0].evidence[0].line_number == 1
    assert result.errors[0].stage == "llm_output_repair"


def test_completion_no_fallback_non_400(monkeypatch):
    from unittest.mock import Mock
    from openai import APIStatusError

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.router import ModelRouter
    from pydantic import BaseModel

    class TestModel(BaseModel):
        result: str

    router = ModelRouter()
    mock_parse = Mock(side_effect=APIStatusError("Internal Error", response=Mock(status_code=500), body={}))
    router._client.chat.completions.parse = mock_parse

    try:
        router.completion(
            messages=[{"role": "user", "content": "test"}],
            response_model=TestModel,
        )
        assert False, "Should have raised APIStatusError"
    except APIStatusError:
        pass


def test_completion_fallback_empty_content(monkeypatch):
    from unittest.mock import Mock, call
    from openai import BadRequestError

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.router import ModelRouter
    from pydantic import BaseModel

    class TestModel(BaseModel):
        result: str

    router = ModelRouter()
    mock_parse = Mock(side_effect=BadRequestError("Bad Request", response=Mock(status_code=400), body={}))
    router._client.chat.completions.parse = mock_parse

    # Both the initial fallback and the retry return empty content
    mock_choice = Mock()
    mock_choice.message = Mock(content=None)
    mock_choice.finish_reason = "stop"
    mock_create_response = Mock()
    mock_create_response.choices = [mock_choice]
    router._client.chat.completions.create = Mock(return_value=mock_create_response)

    try:
        router.completion(
            messages=[{"role": "user", "content": "test"}],
            response_model=TestModel,
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Empty response" in str(e)
        assert "finish_reason=stop" in str(e)

    # Should have retried once after the first empty response
    assert router._client.chat.completions.create.call_count == 2
    # First call includes the JSON instruction, retry does not
    first_call_messages = router._client.chat.completions.create.call_args_list[0].kwargs["messages"]
    assert "Return only one valid JSON object" in first_call_messages[-1]["content"]
    retry_messages = router._client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert len(retry_messages) == 1  # only the original user message, no appended instruction


def test_chat_returns_raw_content(monkeypatch):
    from unittest.mock import Mock

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI.__init__", lambda self, **kwargs: None)
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    mock_create_response = Mock()
    mock_create_response.choices = [Mock(message=Mock(content="hello"))]
    router._client.chat.completions.create = Mock(return_value=mock_create_response)

    result = router.chat([{"role": "user", "content": "ping"}])

    assert result == "hello"
    assert router._client.chat.completions.create.called


def test_http_client_uses_ca_bundle(monkeypatch):
    monkeypatch.setenv("ASCEND_CA_BUNDLE", "/tmp/internal-ca.pem")
    monkeypatch.delenv("ASCEND_SSL_VERIFY", raising=False)
    monkeypatch.delenv("ASCEND_HTTPS_PROXY", raising=False)
    from ascend_agent.diagnosis import router as router_mod

    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(router_mod.httpx, "Client", fake_client)

    router_mod._build_http_client()

    assert captured["verify"] == "/tmp/internal-ca.pem"


def test_http_client_can_disable_ssl_verify(monkeypatch):
    monkeypatch.setenv("ASCEND_SSL_VERIFY", "false")
    monkeypatch.delenv("ASCEND_CA_BUNDLE", raising=False)
    monkeypatch.delenv("ASCEND_HTTPS_PROXY", raising=False)
    from ascend_agent.diagnosis import router as router_mod

    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(router_mod.httpx, "Client", fake_client)

    router_mod._build_http_client()

    assert captured["verify"] is False
