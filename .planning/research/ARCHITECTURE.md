# Architecture Research — v1.1 Multi-Provider & Multi-Repo

## Provider ModelRouter Refactor

Current state:
```
ModelRouter (OpenAI only)
  ├── __init__()  # reads OPENAI_API_KEY
  └── completion()  # calls openai.with_options().parse()
```

Target state:
```
ModelRouter (provider-agnostic)
  ├── __init__(provider: str)  # reads provider config
  ├── completion()  # dispatches to correct provider backend
  └── backends: dict[str, ProviderBackend]
       ├── OpenAIProvider  # existing logic, refactored
       ├── AnthropicProvider  # new
       ├── GoogleProvider  # new
       ├── OllamaProvider  # new
       ├── OpenAILikeProvider  # DeepSeek, Qwen, etc.
```

## Provider Backend Interface

```python
class ProviderBackend(Protocol):
    async def complete(
        self, messages: list[dict], response_model: type[BaseModel], **kwargs
    ) -> BaseModel: ...
```

Each backend implements:
- Authentication (API key / no auth for Ollama)
- Endpoint construction (base_url + path)
- Structured output parsing (native or regex fallback)
- Error handling (retry, timeout, provider-specific errors)

## Multi-Repo Integration

- Settings.repo_path → Settings.target_repos: list[str] | None
- CLI: `--repo` flag on diagnose/fix/reproduce/verify
- Engine constructors: `repo_path` stays str, but CLI resolves which repo

## Build Order

1. **Provider interface** — define ProviderBackend protocol, refactor existing OpenAI logic
2. **Provider implementations** — Anthropic, Google, Ollama, OpenAILike (DeepSeek/Qwen)
3. **Config system** — per-provider API keys, model mapping, task routing
4. **Multi-repo CLI** — --repo flag, target_repos in Settings
5. **Tests** — mock providers, integration tests for each backend
