from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    name: str
    base_url: str
    default_model: str
    models: tuple[str, ...]
    api_key_env: str


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        default_model="gpt-5.5",
        models=("gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-4o"),
        api_key_env="ASCEND_OPENAI_API_KEY",
    ),
    "deepseek": ProviderPreset(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-v4-flash",
        models=("deepseek-v4-flash", "deepseek-v4-pro"),
        api_key_env="ASCEND_DEEPSEEK_API_KEY",
    ),
    "qwen": ProviderPreset(
        id="qwen",
        name="Qwen (DashScope)",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen3.6-plus",
        models=(
            "qwen3.7-max",
            "qwen3.6-plus",
            "qwen3.6-flash",
        ),
        api_key_env="ASCEND_QWEN_API_KEY",
    ),
    "ollama": ProviderPreset(
        id="ollama",
        name="Ollama (Local)",
        base_url="http://localhost:11434/v1",
        default_model="llama3.1",
        models=("llama3.1", "mistral", "codellama"),
        api_key_env="ASCEND_OLLAMA_API_KEY",
    ),
}


def default_model_id(provider: str) -> str:
    preset = PROVIDER_PRESETS.get(provider)
    if preset is None:
        return "gpt-5.5"
    return preset.default_model


def full_model_id(provider: str, model: str) -> str:
    if "/" in model:
        return model
    return f"{provider}/{model}"


def split_model_id(model_id: str) -> tuple[str, str]:
    if "/" not in model_id:
        return "openai", model_id
    provider, model = model_id.split("/", 1)
    return provider, model
