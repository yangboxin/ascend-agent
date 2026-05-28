from pydantic import BaseModel, ConfigDict, Field


class ConfigEnv(BaseModel):
    model_config = ConfigDict(extra="forbid")

    python_version: str = Field(default="")
    platform: str = Field(default="")
    env_vars: dict[str, str] = Field(default_factory=dict)


class RepoInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    language: str = Field(default="python")
    file_count: int = Field(default=0)
    structure: list[str] = Field(default_factory=list)


class TraceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str | None = Field(default=None)
    line: int | None = Field(default=None, ge=1)
    function: str | None = Field(default=None)
    text: str


class TraceCause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_type: str | None = Field(default=None)
    error_message: str | None = Field(default=None)
    frames: list[TraceEntry] = Field(default_factory=list)


class TraceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_type: str | None = Field(default=None)
    error_message: str | None = Field(default=None)
    frames: list[TraceEntry] = Field(default_factory=list)
    causes: list[TraceCause] = Field(default_factory=list)
    runtime_signals: dict[str, str] = Field(default_factory=dict)
    parse_warnings: list[str] = Field(default_factory=list)
    raw_text: str


class ContextDocument(BaseModel):
    """Top-level schema contract consumed by Phase 2 (Diagnosis Engine)."""

    model_config = ConfigDict(extra="forbid")

    repo: RepoInfo | None = Field(default=None)
    trace: TraceInfo | None = Field(default=None)
    config_env: ConfigEnv = Field(default_factory=ConfigEnv)
