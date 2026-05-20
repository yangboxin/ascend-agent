import typer
from rich.console import Console

console = Console()
app = typer.Typer(rich_markup_mode="rich", help="Ascend Diagnostic Agent — diagnose, reproduce, and fix Ascend NPU issues")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        console.print("[bold]Ascend Diagnostic Agent[/bold]")
        console.print("Use [cyan]--help[/cyan] for available commands.")
        raise typer.Exit()


from ascend_agent.cli.diagnose import diagnose_app
from ascend_agent.cli.reproduce import reproduce_app
from ascend_agent.cli.fix import fix_app

app.add_typer(diagnose_app)
app.add_typer(reproduce_app)
app.add_typer(fix_app)
