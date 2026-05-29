from __future__ import annotations

import os
import sys

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASCEND_")

    python_version: str = ""
    platform: str = ""
    env_vars: dict[str, str] = {}
    repo_path: str | None = None
    mcp_server_command: str = "python -m ascend_agent.tools.server"
    diagnosis_tool_backend: str = Field(
        default="auto",
        description="Diagnosis tool backend: auto|local|mcp (env: ASCEND_DIAGNOSIS_TOOL_BACKEND)",
    )
    ssh_host: str = Field(default="", description="SSH hostname for remote execution")
    ssh_user: str = Field(default="", description="SSH username for remote execution")
    ssh_key_path: str = Field(default="", description="Path to SSH private key file (fallback if agent unavailable)")
    shell_timeout: int = Field(default=60, ge=1, description="Default timeout in seconds for shell commands")
    test_timeout: int = Field(default=300, ge=1, description="Default timeout in seconds for test execution")

    # Phase 6: Provider config fields
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key (env: ASCEND_OPENAI_API_KEY, falls back to OPENAI_API_KEY)",
    )
    openai_base_url: str = Field(
        default="",
        description="OpenAI-compatible base URL override (env: ASCEND_OPENAI_BASE_URL)",
    )

    # Phase 7: Chinese provider config fields
    deepseek_api_key: str = Field(
        default="",
        description="DeepSeek API key (env: ASCEND_DEEPSEEK_API_KEY)",
    )
    deepseek_base_url: str = Field(
        default="",
        description="DeepSeek base URL override (env: ASCEND_DEEPSEEK_BASE_URL)",
    )
    deepseek_default_model: str = Field(
        default="",
        description="DeepSeek default model override (env: ASCEND_DEEPSEEK_DEFAULT_MODEL)",
    )
    qwen_api_key: str = Field(
        default="",
        description="Qwen DashScope API key (env: ASCEND_QWEN_API_KEY)",
    )
    qwen_base_url: str = Field(
        default="",
        description="Qwen DashScope base URL override (env: ASCEND_QWEN_BASE_URL)",
    )
    qwen_default_model: str = Field(
        default="",
        description="Qwen default model override (env: ASCEND_QWEN_DEFAULT_MODEL)",
    )

    def model_post_init(self, __context):
        self.python_version = sys.version
        self.platform = sys.platform
        # Store only non-sensitive env vars to avoid leaking API keys
        self.env_vars = {
            k: v for k, v in os.environ.items()
            if not any(sensitive in k.upper() for sensitive in ("KEY", "SECRET", "TOKEN", "PASSWORD", "AUTH"))
        }


settings = Settings()
