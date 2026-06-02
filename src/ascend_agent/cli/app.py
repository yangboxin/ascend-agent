import sys
import typer
from rich.console import Console
from typing import Optional

console = Console()
app = typer.Typer(rich_markup_mode="rich", help="Ascend Diagnostic Agent — diagnose, reproduce, and fix Ascend NPU issues")


def _resolve_provider(provider: str | None) -> str:
    """Resolve the active provider: explicit flag > config file > default."""
    if provider:
        return provider
    try:
        from ascend_agent.cli.config_manager import ConfigManager
        return ConfigManager().get_active()
    except Exception:
        return "openai"


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="LLM provider to use (e.g., openai, deepseek). Overrides per-engine model env vars.",
    ),
    repl: bool = typer.Option(
        False,
        "--repl",
        help="Enter interactive REPL mode with slash commands.",
    ),
    tui: bool = typer.Option(
        False,
        "--tui",
        help="Launch the immersive full-screen TUI (alternate screen buffer).",
    ),
):
    """Ascend Diagnostic Agent — diagnose, reproduce, and fix Ascend NPU issues.

    By default (no flags), launches the immersive full-screen TUI if stdout
    is a terminal. Use --repl for the simple REPL or --no-tui to force
    non-interactive mode.
    """
    resolved = _resolve_provider(provider)

    if ctx.invoked_subcommand is None:
        if tui:
            # Explicit --tui flag
            from ascend_agent.cli.tui_integration import run_tui_with_llm
            run_tui_with_llm(provider=resolved)
            raise typer.Exit()
        elif repl:
            # Explicit --repl flag
            from ascend_agent.cli.repl import run_repl
            run_repl(provider=resolved)
            raise typer.Exit()
        elif sys.stdin.isatty():
            # Default: launch TUI if interactive terminal
            from ascend_agent.cli.tui_integration import run_tui_with_llm
            run_tui_with_llm(provider=resolved)
            raise typer.Exit()
        else:
            console.print(ctx.get_help())
            raise typer.Exit()
    ctx.obj = {"provider": resolved}


@app.command()
def repl(
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="LLM provider to use in the REPL session.",
    ),
):
    """Enter interactive REPL mode with slash commands (/help, /models, etc.)."""
    from ascend_agent.cli.repl import run_repl
    run_repl(provider=_resolve_provider(provider))


@app.command()
def interactive(
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="LLM provider for the session.",
    ),
):
    """Launch the immersive full-screen TUI (alternate screen buffer).

    Features:
    - Fixed bottom input area
    - Scrollable conversation history
    - Streaming AI responses with typewriter effect
    - Command history (Up/Down arrows)
    - Ctrl+C interrupts current operation
    - Ctrl+D or /quit to exit
    """
    from ascend_agent.cli.tui_integration import run_tui_with_llm
    run_tui_with_llm(provider=_resolve_provider(provider))


from ascend_agent.cli.diagnose import diagnose_app
from ascend_agent.cli.reproduce import reproduce_app
from ascend_agent.cli.fix import fix_app
from ascend_agent.cli.verify import verify_app
from ascend_agent.cli.models import models_app

app.add_typer(diagnose_app)
app.add_typer(reproduce_app)
app.add_typer(fix_app)
app.add_typer(verify_app)
app.add_typer(models_app)
