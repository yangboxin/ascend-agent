import os
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASCEND_")

    python_version: str = ""
    platform: str = ""
    env_vars: dict[str, str] = {}
    repo_path: str | None = None
    mcp_server_command: str = "python -m ascend_agent.tools.server"

    def model_post_init(self, __context):
        self.python_version = sys.version
        self.platform = sys.platform
        self.env_vars = dict(os.environ)


settings = Settings()
