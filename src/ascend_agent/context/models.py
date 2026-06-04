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


class TraceSignalCandidate(BaseModel):
    """Low-confidence signal extracted from noisy text such as OCR output."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="Signal category, e.g. error_type, runtime_symbol, error_code")
    value: str = Field(description="Normalized candidate value")
    confidence: float = Field(ge=0.0, le=1.0)
    source_text: str = Field(description="Original text that produced the candidate")
    reason: str = Field(description="Why the candidate was extracted")


class TraceErrorEvent(BaseModel):
    """A candidate error event found in the trace text."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="Error category, e.g. python_exception, ascend_runtime")
    message: str = Field(description="Normalized event message")
    confidence: float = Field(ge=0.0, le=1.0)
    source_line: int = Field(ge=1, description="1-based line number in the raw trace")
    source_text: str = Field(description="Original line that produced the event")


class TraceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_type: str | None = Field(default=None)
    error_message: str | None = Field(default=None)
    frames: list[TraceEntry] = Field(default_factory=list)
    causes: list[TraceCause] = Field(default_factory=list)
    runtime_signals: dict[str, str] = Field(default_factory=dict)
    signal_candidates: list[TraceSignalCandidate] = Field(default_factory=list)
    error_events: list[TraceErrorEvent] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)
    raw_text: str


class TraceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    label: str = Field(default="")
    line_count: int = Field(default=0, ge=0)
    trace: TraceInfo


class TraceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[TraceSource] = Field(default_factory=list)
    error_type: str | None = Field(default=None)
    error_message: str | None = Field(default=None)
    frames: list[TraceEntry] = Field(default_factory=list)
    runtime_signals: dict[str, str] = Field(default_factory=dict)
    signal_candidates: list[TraceSignalCandidate] = Field(default_factory=list)
    error_events: list[TraceErrorEvent] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)
    raw_text: str = Field(default="")

    def to_trace_info(self) -> TraceInfo:
        return TraceInfo(
            error_type=self.error_type,
            error_message=self.error_message,
            frames=self.frames,
            runtime_signals=self.runtime_signals,
            signal_candidates=self.signal_candidates,
            error_events=self.error_events,
            parse_warnings=self.parse_warnings,
            raw_text=self.raw_text,
        )


class ContextDocument(BaseModel):
    """Top-level schema contract consumed by Phase 2 (Diagnosis Engine)."""

    model_config = ConfigDict(extra="forbid")

    repo: RepoInfo | None = Field(default=None)
    trace: TraceInfo | None = Field(default=None)
    trace_bundle: TraceBundle | None = Field(default=None)
    config_env: ConfigEnv = Field(default_factory=ConfigEnv)
