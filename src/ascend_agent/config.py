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

    def model_post_init(self, __context):
        self.python_version = sys.version
        self.platform = sys.platform
        self.env_vars = dict(os.environ)


settings = Settings()
