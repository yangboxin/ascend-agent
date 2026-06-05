from __future__ import annotations

import os
from dataclasses import dataclass

from ascend_agent.providers.catalog import PROVIDER_PRESETS, full_model_id, split_model_id
from ascend_agent.providers import config_manager
from ascend_agent.providers.config_manager import ConfigManager, ProviderRecord


def resolve_provider(explicit: str | None = None) -> str:
    """Resolve the active provider: explicit flag > config file > default.

    Args:
        explicit: Explicitly requested provider string, or None.

    Returns:
        The resolved provider name (e.g., "openai", "deepseek").
        Falls back to "openai" when no configuration is found.
    """
    if explicit:
        return explicit
    try:
        return ConfigManager().get_active()
    except Exception:
        return "openai"


@dataclass(frozen=True)
class ModelStatus:
    active_model: str
    provider: str
    configured: bool
    config_file: str
    env_names: tuple[str, ...]


def is_configured(provider: ProviderRecord) -> bool:
    if provider.api_key:
        return True
    env_name = f"ASCEND_{provider.name.upper()}_API_KEY"
    if os.environ.get(env_name):
        return True
    return provider.name == "openai" and bool(os.environ.get("OPENAI_API_KEY"))


def provider_label(provider: str) -> str:
    preset = PROVIDER_PRESETS.get(provider)
    return preset.name if preset else provider


def known_models(provider: str) -> list[str]:
    preset = PROVIDER_PRESETS.get(provider)
    return list(preset.models) if preset else []


def validate_model_id(cm: ConfigManager, model_id: str) -> tuple[str, str]:
    provider, model = split_model_id(model_id)
    record = cm.get_provider(provider)
    if record is None:
        raise ValueError(f"Unknown provider '{provider}'. Run /models list to see available providers.")

    known = known_models(provider)
    if known and model not in known:
        allowed = ", ".join(full_model_id(provider, item) for item in known)
        raise ValueError(f"Unknown model '{model}' for {provider}. Available: {allowed}")
    return provider, model


def use_model(cm: ConfigManager, model_id: str) -> str:
    provider, model = validate_model_id(cm, model_id)
    selected = full_model_id(provider, model)
    cm.set_model(selected)
    return selected


def add_provider(
    cm: ConfigManager,
    provider: str,
    *,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> ProviderRecord:
    preset = PROVIDER_PRESETS.get(provider)
    if preset is not None:
        base_url = base_url or preset.base_url
        model = model or preset.default_model
        validate_model_id(cm, full_model_id(provider, model))
    elif not base_url or not model:
        raise ValueError("Custom providers require both base_url and model.")

    record = ProviderRecord(
        name=provider,
        base_url=base_url,
        api_key=api_key,
        default_model=model,
    )
    cm.add_provider(record)
    return record


def get_model_status(cm: ConfigManager) -> ModelStatus:
    active = cm.get_active_model()
    provider_name, _ = split_model_id(active)
    provider = cm.get_provider(provider_name)
    env_names = (f"ASCEND_{provider_name.upper()}_API_KEY",)
    if provider_name == "openai":
        env_names = (*env_names, "OPENAI_API_KEY")
    return ModelStatus(
        active_model=active,
        provider=provider_name,
        configured=is_configured(provider) if provider else False,
        config_file=str(config_manager.CONFIG_FILE),
        env_names=env_names,
    )
