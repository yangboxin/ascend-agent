# Phase 6: Provider Routing Foundation — Pattern Map

**Mapped:** 2026-05-26
**Files analyzed:** 10 (7 modified, 3 new test files)
**Analogs found:** 8 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/ascend_agent/diagnosis/router.py` | service+model | config resolution | `src/ascend_agent/diagnosis/models.py` (model) + `router.py` itself (factory) | exact |
| `src/ascend_agent/config.py` | config | env-var resolution | `src/ascend_agent/config.py` (self) | self-exact |
| `src/ascend_agent/cli/app.py` | route | CLI parsing | `src/ascend_agent/cli/app.py` (self) | self-exact |
| `src/ascend_agent/cli/diagnose.py` | CLI command | request-response | `src/ascend_agent/cli/diagnose.py` (self line 76) | self-exact |
| `src/ascend_agent/cli/fix.py` | CLI command | request-response | `src/ascend_agent/cli/fix.py` (self line 53) | self-exact |
| `src/ascend_agent/cli/reproduce.py` | CLI command | request-response | `src/ascend_agent/cli/diagnose.py` line 76 | role-match |
| `src/ascend_agent/cli/verify.py` | CLI command | request-response | `src/ascend_agent/cli/diagnose.py` line 76 | role-match |
| `tests/test_diagnosis/test_router.py` | test | unit test | `tests/test_diagnosis/test_router.py` (self) | self-exact |
| `tests/test_diagnosis/conftest.py` | test | fixture | `tests/test_diagnosis/conftest.py` (self) | self-exact |
| `tests/test_cli.py` | test | integration test | `tests/test_cli.py` (self lines 21-35) | self-exact |

**Engine files (NO CHANGES NEEDED):** `diagnosis/engine.py`, `diagnosis/fix_engine.py`, `reproduction/engine.py`, `verification/engine.py` — all 4 accept `router: ModelRouter` in constructor. `create_router()` returns `ModelRouter`, so no structural changes needed.

---

## Pattern Assignments

### `src/ascend_agent/diagnosis/router.py` — ProviderConfig model + create_router factory

**Role:** model + factory function  
**Data flow:** config resolution (env var → Pydantic model → OpenAI client)  
**Changes:** Add `ProviderConfig` Pydantic model, add `create_router()` factory, modify `ModelRouter.__init__` to accept `ProviderConfig` internally while preserving backward-compatible kwargs.

#### Analog A: Pydantic model pattern from `src/ascend_agent/diagnosis/models.py` (lines 1-4, 6-15)

The `ProviderConfig` should follow the exact same Pydantic v2 pattern as all existing models:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider (OpenAI-compatible API)."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(description="Base URL for the OpenAI-compatible API endpoint")
    api_key: str = Field(description="API key for this provider")
    default_model: str = Field(description="Default model name for this provider")
```

**Pattern invariants to copy:**
- `from __future__ import annotations` (line 1)
- `model_config = ConfigDict(extra="forbid")` — used across all 5 phases in every model
- `Field(description=...)` — every field has a description

#### Analog B: Env var resolution pattern from `src/ascend_agent/diagnosis/router.py` (lines 19-29)

The `create_router()` factory should follow the same env var resolution pattern as the existing `ModelRouter.__init__`:

```python
def create_router(provider: str = "openai") -> ModelRouter:
    """Create a configured ModelRouter for the given provider.

    Resolves provider-specific env vars (ASCEND_{PROVIDER}_API_KEY,
    ASCEND_{PROVIDER}_BASE_URL) and constructs a ProviderConfig.

    Default provider "openai" falls back to OPENAI_API_KEY for
    backward compatibility (PROV-04).

    Args:
        provider: Provider name, e.g. "openai" or "deepseek".

    Returns:
        A configured ModelRouter instance.

    Raises:
        ValueError: If required API key is missing.
    """
    prefix = f"ASCEND_{provider.upper()}"
    api_key = os.environ.get(f"{prefix}_API_KEY")
    base_url = os.environ.get(f"{prefix}_BASE_URL")

    if provider == "openai":
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "ASCEND_OPENAI_API_KEY or OPENAI_API_KEY is required. "
                "Set one of these environment variables."
            )
    else:
        if not api_key:
            raise ValueError(
                f"{prefix}_API_KEY is required for provider '{provider}'. "
                f"Set the {prefix}_API_KEY environment variable."
            )

    config = ProviderConfig(
        base_url=base_url or "https://api.openai.com/v1",
        api_key=api_key,
        default_model=os.environ.get(f"{prefix}_DEFAULT_MODEL", "gpt-4o"),
    )
    return ModelRouter(config=config)
```

**Pattern invariants to copy:**
- ValueError with actionable message (line 22-25 of existing router.py)
- `os.environ.get()` for env var resolution with fallback
- Provider-specific prefix: `ASCEND_{PROVIDER}_API_KEY`, `ASCEND_{PROVIDER}_BASE_URL`

#### Analog C: ModelRouter backward-compatible constructor from `src/ascend_agent/diagnosis/router.py` (lines 19-29)

The `ModelRouter.__init__` should accept both old kwargs and new `ProviderConfig`:

```python
class ModelRouter:
    """Thin wrapper around the LLM client for diagnosis calls."""

    _DEFAULT_MODEL = "gpt-4o"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        config: ProviderConfig | None = None,
    ):
        if config is not None:
            # New code path: use ProviderConfig
            self._client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
            )
            self._model = config.default_model
        else:
            # Backward-compatible code path (deprecated)
            api_key = api_key or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required for diagnosis. "
                    "Set the OPENAI_API_KEY environment variable."
                )
            self._client = OpenAI(api_key=api_key)
            self._model = model or os.environ.get(
                "ASCEND_DIAGNOSIS_MODEL", self._DEFAULT_MODEL
            )
        logger.info("ModelRouter initialized (model: %s)", self._model)
```

**Key insight:** The `base_url` parameter of `OpenAI()` is the critical addition. Currently `OpenAI(api_key=api_key)` — the new code path must pass `base_url=config.base_url`.

---

### `src/ascend_agent/config.py` — Add provider fields to Settings

**Role:** config  
**Data flow:** env-var resolution via pydantic-settings  
**Changes:** Add `openai_api_key`, `openai_base_url` fields following existing `ASCEND_` env prefix convention.

#### Analog: Existing `Settings` class from `src/ascend_agent/config.py` (lines 8-25)

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASCEND_")

    # ... existing fields ...

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
```

**Pattern invariants to copy:**
- `SettingsConfigDict(env_prefix="ASCEND_")` — all fields auto-prefixed with `ASCEND_`
- Field names map to env vars as: `openai_api_key` → `ASCEND_OPENAI_API_KEY`
- `Field(default=..., description=...)` — all config fields use this pattern
- Existing fields: `ssh_host`, `ssh_user`, `ssh_key_path`, `shell_timeout`, `test_timeout` (lines 16-20)

---

### `src/ascend_agent/cli/app.py` — Add root `--provider` flag

**Role:** route (CLI entry point)  
**Data flow:** CLI parsing → subcommand dispatch  
**Changes:** Add `--provider` option to `@app.callback()` (D-03), pass through to subcommands via context.

#### Analog: Existing `app.py` from `src/ascend_agent/cli/app.py` (lines 1-23)

```python
import typer
from rich.console import Console
from typing import Optional

from ascend_agent.diagnosis.router import create_router

console = Console()
app = typer.Typer(
    rich_markup_mode="rich",
    help="Ascend Diagnostic Agent — diagnose, reproduce, and fix Ascend NPU issues",
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="LLM provider to use (e.g., openai, deepseek). Overrides per-engine model env vars.",
    ),
):
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()
    # Store provider in context for subcommands to consume
    ctx.obj = {"provider": provider or "openai"}


from ascend_agent.cli.diagnose import diagnose_app
from ascend_agent.cli.reproduce import reproduce_app
from ascend_agent.cli.fix import fix_app
from ascend_agent.cli.verify import verify_app

app.add_typer(diagnose_app)
app.add_typer(reproduce_app)
app.add_typer(fix_app)
app.add_typer(verify_app)
```

**Pattern invariants to copy:**
- `@app.callback(invoke_without_command=True)` — root-level flags, already established in line 8
- `ctx.obj = ...` — pass shared state to subcommands via Typer context
- `typer.Option(None, "--provider", help=...)` — optional string, defaults resolved at call time
- `Optional[str]` type hint for optional CLI options

---

### `src/ascend_agent/cli/diagnose.py` — Replace `ModelRouter()` with `create_router()`

**Role:** CLI command  
**Data flow:** CLI → engine wiring  
**Changes:** Line 76 `ModelRouter()` → `create_router(provider=...)`, pass `ctx` for provider flag.

#### Analog: Existing pattern at `src/ascend_agent/cli/diagnose.py` lines 74-83

Current code (line 76):
```python
router = ModelRouter()
engine = Engine(router=router, repo_path=repo)
```

New code should use `create_router()` and read provider from context:
```python
# Read provider from root callback (or allow per-command override)
provider = ctx.obj.get("provider", "openai") if ctx.obj else "openai"
router = create_router(provider=provider)
engine = Engine(router=router, repo_path=repo)
```

The function signature needs `ctx: typer.Context` added:
```python
def diagnose_run(
    ctx: typer.Context,
    repo: str = typer.Argument(..., help="Path to local repository"),
    ...
```

**Pattern invariants to copy:**
- try/except around router + engine construction (lines 75-83) — catches `ValueError` for missing API key
- `console.print(f"[red]Error:[/red] {e}")` — Rich error display
- `raise typer.Exit(code=1)` — exit with error code
- Per-command `--provider` override: `provider: Optional[str] = typer.Option(None, "--provider", help=...)` that falls back to `ctx.obj.get("provider", "openai")`

---

### `src/ascend_agent/cli/fix.py` — Replace `ModelRouter(model=...)` with `create_router()`

**Role:** CLI command  
**Data flow:** CLI → engine wiring  
**Changes:** Line 53 `ModelRouter(model=...)` → `create_router(provider=...)`

#### Analog: Existing pattern at `src/ascend_agent/cli/fix.py` lines 51-60

Current code (line 53):
```python
router = ModelRouter(model=os.environ.get("ASCEND_FIX_MODEL", "gpt-4o"))
engine = FixEngine(router=router, repo_path=repo_path)
```

New code:
```python
provider = ctx.obj.get("provider", "openai") if ctx.obj else "openai"
router = create_router(provider=provider)
engine = FixEngine(router=router, repo_path=repo_path)
```

**Pattern invariants to copy:**
- Same try/except structure as diagnose.py (lines 55-60)
- `console.print("[yellow]Hint: Set the OPENAI_API_KEY..." )` — Rich hint display
- Per-command `--provider` flag pattern (same as diagnose.py)

---

### `src/ascend_agent/cli/reproduce.py` — Replace `ModelRouter()` with `create_router()`

**Role:** CLI command  
**Data flow:** CLI → engine wiring  
**Changes:** Line 44 `ModelRouter()` → `create_router(provider=...)`

#### Analog: `src/ascend_agent/cli/diagnose.py` lines 74-83

Current code (line 44):
```python
router = ModelRouter()
engine = ReproductionEngine(router=router, repo_path=repo_path, settings=settings)
```

New code:
```python
provider = ctx.obj.get("provider", "openai") if ctx.obj else "openai"
router = create_router(provider=provider)
engine = ReproductionEngine(router=router, repo_path=repo_path, settings=settings)
```

---

### `src/ascend_agent/cli/verify.py` — Replace `ModelRouter()` with `create_router()`

**Role:** CLI command  
**Data flow:** CLI → engine wiring  
**Changes:** Line 46 `ModelRouter()` → `create_router(provider=...)`

#### Analog: `src/ascend_agent/cli/diagnose.py` lines 74-83

Current code (line 46):
```python
router = ModelRouter()
engine = VerificationEngine(router=router, repo_path=repo_path, settings=settings)
```

New code:
```python
provider = ctx.obj.get("provider", "openai") if ctx.obj else "openai"
router = create_router(provider=provider)
engine = VerificationEngine(router=router, repo_path=repo_path, settings=settings)
```

---

### Tests — `tests/test_diagnosis/test_router.py` (modify + expand)

**Role:** test  
**Data flow:** unit test  
**Changes:** Add tests for `create_router()` and `ProviderConfig`.

#### Analog A: Existing test pattern from `tests/test_diagnosis/test_router.py` (lines 1-34)

```python
def test_router_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from ascend_agent.diagnosis.router import ModelRouter

    try:
        ModelRouter()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "OPENAI_API_KEY" in str(e)


def test_router_uses_default_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from ascend_agent.diagnosis.router import ModelRouter

    router = ModelRouter()
    assert router._model == "gpt-4o"
```

**Pattern invariants to copy:**
- Inline imports (`from ascend_agent.diagnosis.router import ModelRouter`) — avoids side effects at module level
- `monkeypatch.setenv()` / `monkeypatch.delenv()` for env var control
- ValueError assertion via try/except with `assert "KEY" in str(e)`
- No fixture dependencies — self-contained tests

#### Analog B: Pattern for testing `create_router()` with `monkeypatch`

```python
def test_create_router_default_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from ascend_agent.diagnosis.router import create_router

    router = create_router("openai")
    assert router is not None
    assert router._model == "gpt-4o"


def test_create_router_with_base_url(monkeypatch):
    monkeypatch.setenv("ASCEND_OPENAI_API_KEY", "sk-custom")
    monkeypatch.setenv("ASCEND_OPENAI_BASE_URL", "https://custom.api.com/v1")
    from ascend_agent.diagnosis.router import create_router

    router = create_router("openai")
    assert router._client.base_url == "https://custom.api.com/v1"
```

#### Analog C: CLI integration tests from `tests/test_cli.py` (lines 21-35)

```python
def test_cli_diagnose_run_basic(tmp_path, monkeypatch):
    from unittest.mock import Mock

    (tmp_path / "test.py").write_text("x = 1\n")
    mock_engine = Mock()
    mock_engine.diagnose.return_value = Mock(hypotheses=[], errors=[], iterations_used=0)
    import ascend_agent.cli.diagnose as diag_mod
    monkeypatch.setattr(diag_mod, "Engine", lambda router, repo_path: mock_engine)
    monkeypatch.setattr("ascend_agent.diagnosis.router.ModelRouter.__init__", lambda self: None)

    result = runner.invoke(app, [
        "diagnose", "run", str(tmp_path),
        "--trace-text", "ValueError: test",
    ])
    assert result.exit_code == 0
```

**Pattern invariants to copy:**
- `monkeypatch.setattr("ascend_agent.diagnosis.router.ModelRouter.__init__", lambda self: None)` — mock ModelRouter constructor (or `create_router`)
- `runner.invoke(app, [...])` — `CliRunner` from `typer.testing`
- Mock engines via `Mock()` with `.return_value` set

For `--provider` flag tests:
```python
def test_cli_with_provider_flag(tmp_path, monkeypatch):
    """--provider flag is consumed and passed to create_router."""
    from unittest.mock import Mock
    from ascend_agent.cli.app import app
    from typer.testing import CliRunner

    runner = CliRunner()
    (tmp_path / "test.py").write_text("x = 1\n")

    mock_engine = Mock()
    mock_engine.diagnose.return_value = Mock(hypotheses=[], errors=[], iterations_used=0)
    import ascend_agent.cli.diagnose as diag_mod
    monkeypatch.setattr(diag_mod, "Engine", lambda router, repo_path: mock_engine)
    monkeypatch.setattr("ascend_agent.diagnosis.router.create_router", lambda provider: Mock())

    result = runner.invoke(app, [
        "--provider", "deepseek",
        "diagnose", "run", str(tmp_path),
        "--trace-text", "ValueError: test",
    ])
    assert result.exit_code == 0
```

---

## Shared Patterns

### Authentication (API Key Resolution)

**Source:** `src/ascend_agent/diagnosis/router.py` lines 19-29 (existing) + new `create_router()` factory  
**Apply to:** All 4 CLI files (diagnose.py, fix.py, reproduce.py, verify.py)

The env var resolution pattern is:
1. `ASCEND_{PROVIDER}_API_KEY` checked first
2. For `"openai"` fallback to `OPENAI_API_KEY` (PROV-04)
3. For other providers, raise `ValueError` if key is missing
4. `ASCEND_{PROVIDER}_BASE_URL` for base URL override (PROV-01)

```python
# Pattern from existing router.py lines 19-25
api_key = api_key or os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError(
        "OPENAI_API_KEY is required for diagnosis. "
        "Set the OPENAI_API_KEY environment variable."
    )
```

### Error Handling

**Source:** All 4 CLI files (diagnose.py lines 80-83, fix.py lines 55-60, reproduce.py lines 46-49, verify.py lines 48-51)  
**Apply to:** All CLI files — ValueError from `create_router()` / `ModelRouter()` caught and displayed

```python
# Pattern from diagnose.py lines 75-83
try:
    router = create_router(provider=provider)
    engine = Engine(router=router, repo_path=repo)
    result = engine.diagnose(doc)
except ValueError as e:
    console.print(f"[red]Error:[/red] {e}")
    console.print("[yellow]Hint: Set the OPENAI_API_KEY environment variable...[/yellow]")
    raise typer.Exit(code=1)
```

### Pydantic Model Conventions

**Source:** `src/ascend_agent/diagnosis/models.py` (lines 1-9 across all models)  
**Apply to:** New `ProviderConfig` model

```python
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field

class SomeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_name: str = Field(description="...")
```

### Typer CLI Wiring Pattern

**Source:** `src/ascend_agent/cli/app.py` (all lines) + `src/ascend_agent/cli/diagnose.py` (lines 1-19)  
**Apply to:** All CLI files

```python
# Root app (app.py) — callback with shared state
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, provider: Optional[str] = typer.Option(...)):
    ctx.obj = {"provider": provider or "openai"}

# Subcommand (diagnose.py) — access context
@diagnose_app.command(name="run")
def diagnose_run(ctx: typer.Context, ...):
    provider = ctx.obj.get("provider", "openai") if ctx.obj else "openai"
```

---

## Files with No Analog Needed

| File | Role | Reason |
|------|------|--------|
| `src/ascend_agent/diagnosis/engine.py` | engine | No changes needed — already accepts `router: ModelRouter` |
| `src/ascend_agent/diagnosis/fix_engine.py` | engine | No changes needed — already accepts `router: ModelRouter` |
| `src/ascend_agent/reproduction/engine.py` | engine | No changes needed — already accepts `router: ModelRouter` |
| `src/ascend_agent/verification/engine.py` | engine | No changes needed — already accepts `router: ModelRouter` |

---

## Metadata

**Analog search scope:** `src/ascend_agent/` (all Python files), `tests/` (all test files), `.planning/` (project docs)
**Files scanned:** 25+ source and test files
**Pattern extraction date:** 2026-05-26
