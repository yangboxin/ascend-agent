import typer
from rich.console import Console
from typing import Optional

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
):
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()
    ctx.obj = {"provider": provider or "openai"}


from ascend_agent.diagnosis.router import create_router
from ascend_agent.cli.diagnose import diagnose_app
from ascend_agent.cli.reproduce import reproduce_app
from ascend_agent.cli.fix import fix_app
from ascend_agent.cli.verify import verify_app

app.add_typer(diagnose_app)
app.add_typer(reproduce_app)
app.add_typer(fix_app)
app.add_typer(verify_app)
