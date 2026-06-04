from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ascend_agent.providers.catalog import PROVIDER_PRESETS, split_model_id

CONFIG_DIR = Path.home() / ".config" / "ascend-agent"
CONFIG_FILE = CONFIG_DIR / "providers.json"

BUILTIN_PROVIDERS: dict[str, dict[str, str]] = {
    preset.id: {"base_url": preset.base_url, "default_model": preset.default_model}
    for preset in PROVIDER_PRESETS.values()
}


@dataclass
class ProviderRecord:
    name: str
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    default_model: str = "gpt-4o"


class ConfigManager:
    """Manages opencode-style model configuration."""

    def __init__(self):
        self._config = self._load()

    def _load(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                return self._normalize(json.loads(CONFIG_FILE.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        return self._empty_config()

    def _empty_config(self) -> dict:
        return {"model": "openai/gpt-5.5", "provider": {}, "auth": {}}

    def _normalize(self, data: dict) -> dict:
        if "provider" in data:
            data.setdefault("model", "openai/gpt-5.5")
            data.setdefault("auth", {})
            return data

        config = self._empty_config()
        active_provider = data.get("active_provider") or ""
        for provider in data.get("providers", []):
            name = provider.get("name", "")
            if not name:
                continue
            model = provider.get("default_model") or BUILTIN_PROVIDERS.get(name, {}).get("default_model", "gpt-5.5")
            config["provider"][name] = {
                "options": {"baseURL": provider.get("base_url", "https://api.openai.com/v1")},
                "models": {model: {}},
            }
            if provider.get("api_key"):
                config["auth"][name] = {"api_key": provider["api_key"]}
        if active_provider:
            provider = config["provider"].get(active_provider, {})
            models = provider.get("models", {})
            model = next(
                iter(models),
                BUILTIN_PROVIDERS.get(active_provider, {}).get("default_model"),
            )
            if model:
                config["model"] = f"{active_provider}/{model}"
        return config

    def _save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(self._config, indent=2))

    def list_providers(self) -> list[ProviderRecord]:
        seen = set()
        result = []
        for name in self._config.get("provider", {}):
            seen.add(name)
            result.append(self._record_from_config(name))
        for name, defaults in BUILTIN_PROVIDERS.items():
            if name not in seen:
                result.append(ProviderRecord(
                    name=name,
                    base_url=defaults["base_url"],
                    default_model=defaults["default_model"],
                ))
        return result

    def get_provider(self, name: str) -> Optional[ProviderRecord]:
        if name in self._config.get("provider", {}):
            return self._record_from_config(name)
        if name in BUILTIN_PROVIDERS:
            d = BUILTIN_PROVIDERS[name]
            return ProviderRecord(name=name, base_url=d["base_url"], default_model=d["default_model"])
        return None

    def add_provider(self, record: ProviderRecord):
        provider = self._config.setdefault("provider", {})
        existing_models = provider.get(record.name, {}).get("models", {})
        existing_models.setdefault(record.default_model, {})
        provider[record.name] = {
            "options": {"baseURL": record.base_url},
            "models": existing_models,
        }
        if record.api_key:
            self._config.setdefault("auth", {}).setdefault(record.name, {})["api_key"] = record.api_key
        self._config["model"] = f"{record.name}/{record.default_model}"
        self._save()

    def remove_provider(self, name: str):
        if name in BUILTIN_PROVIDERS:
            return
        was_active = self.get_active() == name
        self._config.get("provider", {}).pop(name, None)
        self._config.get("auth", {}).pop(name, None)
        if was_active:
            first = self._get_first_available()
            self._config["model"] = f"{first}/{self.get_provider(first).default_model}"
        self._save()

    def get_active(self) -> str:
        active, _ = split_model_id(self._config.get("model", "openai/gpt-5.5"))
        if active and self.get_provider(active) is not None:
            return active
        first = self._get_first_available()
        return first

    def set_active(self, name: str):
        provider = self.get_provider(name)
        if provider is None:
            raise ValueError(f"Unknown provider: {name}")
        self._config["model"] = f"{name}/{provider.default_model}"
        self._save()

    def get_active_model(self) -> str:
        return self._config.get("model", "openai/gpt-5.5")

    def set_model(self, model_id: str):
        provider, model = split_model_id(model_id)
        record = self.get_provider(provider)
        if record is None:
            raise ValueError(f"Unknown provider: {provider}")
        record.default_model = model
        self.add_provider(record)
        self._config["model"] = f"{provider}/{model}"
        self._save()

    def _get_first_available(self) -> str:
        if self._config.get("provider"):
            return next(iter(self._config["provider"]))
        if BUILTIN_PROVIDERS:
            return next(iter(BUILTIN_PROVIDERS))
        return "openai"

    def _record_from_config(self, name: str) -> ProviderRecord:
        provider = self._config.get("provider", {}).get(name, {})
        options = provider.get("options", {})
        base_url = options.get("baseURL") or options.get("base_url")
        defaults = BUILTIN_PROVIDERS.get(name, {})
        active_provider, active_model = split_model_id(self._config.get("model", "openai/gpt-5.5"))
        models = provider.get("models", {})
        default_model = (
            active_model
            if active_provider == name
            else next(iter(models), defaults.get("default_model", "gpt-5.5"))
        )
        api_key = self._config.get("auth", {}).get(name, {}).get("api_key", "")
        return ProviderRecord(
            name=name,
            base_url=base_url or defaults.get("base_url", "https://api.openai.com/v1"),
            api_key=api_key,
            default_model=default_model,
        )
