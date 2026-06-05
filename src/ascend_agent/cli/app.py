import sys
import typer
from rich.console import Console
from typing import Optional

from ascend_agent.providers.service import resolve_provider

console = Console()
app = typer.Typer(rich_markup_mode="rich", help="Ascend Diagnostic Agent — diagnose, reproduce, and fix Ascend NPU issues")


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
):
    if ctx.invoked_subcommand is None:
        if repl or sys.stdin.isatty():
            from ascend_agent.cli.repl import run_repl
            run_repl(provider=resolve_provider(provider))
            raise typer.Exit()
        else:
            console.print(ctx.get_help())
            raise typer.Exit()
    ctx.obj = {"provider": resolve_provider(provider)}


@app.command()
def repl(
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="LLM provider to use in the REPL session.",
    ),
    resume: Optional[str] = typer.Option(
        None,
        "--resume",
        help="Thread ID of a previous session to resume.",
    ),
):
    """Enter interactive REPL mode with slash commands (/help, /models, etc.)."""
    from ascend_agent.cli.repl import run_repl
    run_repl(provider=resolve_provider(provider), resume=resume)


@app.command()
def chat(
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="LLM provider to use in the chat session.",
    ),
    resume: Optional[str] = typer.Option(
        None,
        "--resume",
        help="Thread ID of a previous session to resume.",
    ),
):
    """Enter runtime-backed chat mode with slash commands."""
    from ascend_agent.cli.repl import run_repl
    run_repl(provider=resolve_provider(provider), resume=resume)


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
