from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


CONFIG_DIR = Path.home() / ".config" / "ascend-agent"
CONFIG_FILE = CONFIG_DIR / "providers.json"

BUILTIN_PROVIDERS: dict[str, dict[str, str]] = {
    "openai": {"base_url": "https://api.openai.com/v1", "default_model": "gpt-4o"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "default_model": "deepseek-v4-flash"},
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-turbo",
    },
}


@dataclass
class ProviderRecord:
    name: str
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    default_model: str = "gpt-4o"


class ConfigManager:
    """Manages provider configurations persisted to ~/.config/ascend-agent/providers.json."""

    def __init__(self):
        self._config = self._load()

    def _load(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"active_provider": "", "providers": []}

    def _save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(self._config, indent=2))

    def list_providers(self) -> list[ProviderRecord]:
        seen = set()
        result = []
        for p in self._config["providers"]:
            seen.add(p["name"])
            result.append(ProviderRecord(**p))
        for name, defaults in BUILTIN_PROVIDERS.items():
            if name not in seen:
                result.append(ProviderRecord(
                    name=name,
                    base_url=defaults["base_url"],
                    default_model=defaults["default_model"],
                ))
        return result

    def get_provider(self, name: str) -> Optional[ProviderRecord]:
        for p in self._config["providers"]:
            if p["name"] == name:
                return ProviderRecord(**p)
        if name in BUILTIN_PROVIDERS:
            d = BUILTIN_PROVIDERS[name]
            return ProviderRecord(name=name, base_url=d["base_url"], default_model=d["default_model"])
        return None

    def add_provider(self, record: ProviderRecord):
        providers = self._config["providers"]
        for i, p in enumerate(providers):
            if p["name"] == record.name:
                providers[i] = asdict(record)
                self._save()
                return
        providers.append(asdict(record))
        self._save()

    def remove_provider(self, name: str):
        if name in BUILTIN_PROVIDERS:
            return
        self._config["providers"] = [p for p in self._config["providers"] if p["name"] != name]
        if self._config.get("active_provider") == name:
            self._config["active_provider"] = self._get_first_available()
        self._save()

    def get_active(self) -> str:
        active = self._config.get("active_provider", "")
        if active and self.get_provider(active) is not None:
            return active
        first = self._get_first_available()
        return first

    def set_active(self, name: str):
        if self.get_provider(name) is None:
            raise ValueError(f"Unknown provider: {name}")
        self._config["active_provider"] = name
        self._save()

    def _get_first_available(self) -> str:
        if self._config["providers"]:
            return self._config["providers"][0]["name"]
        if BUILTIN_PROVIDERS:
            return next(iter(BUILTIN_PROVIDERS))
        return "openai"
