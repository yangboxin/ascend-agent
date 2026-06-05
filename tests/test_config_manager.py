import json


def test_config_manager_writes_opencode_style_config(tmp_path, monkeypatch):
    import ascend_agent.providers.config_manager as config_mod

    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "providers.json")

    cm = config_mod.ConfigManager()
    cm.add_provider(
        config_mod.ProviderRecord(
            name="deepseek",
            base_url="https://api.deepseek.com/v1",
            api_key="sk-test",
            default_model="deepseek-v4-pro",
        )
    )

    data = json.loads((tmp_path / "providers.json").read_text())
    assert data["model"] == "deepseek/deepseek-v4-pro"
    assert data["provider"]["deepseek"]["options"]["baseURL"] == "https://api.deepseek.com/v1"
    assert data["provider"]["deepseek"]["models"] == {"deepseek-v4-pro": {}}
    assert data["auth"]["deepseek"]["api_key"] == "sk-test"
    assert cm.get_active() == "deepseek"
    assert cm.get_provider("deepseek").default_model == "deepseek-v4-pro"


def test_config_manager_reads_legacy_provider_config(tmp_path, monkeypatch):
    import ascend_agent.providers.config_manager as config_mod

    config_file = tmp_path / "providers.json"
    config_file.write_text(
        json.dumps(
            {
                "active_provider": "qwen",
                "providers": [
                    {
                        "name": "qwen",
                        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                        "api_key": "sk-qwen",
                        "default_model": "qwen-plus",
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_file)

    cm = config_mod.ConfigManager()

    assert cm.get_active_model() == "qwen/qwen-plus"
    provider = cm.get_provider("qwen")
    assert provider.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert provider.api_key == "sk-qwen"
    assert provider.default_model == "qwen-plus"
