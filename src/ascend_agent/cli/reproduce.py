from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from ascend_agent.diagnosis.models import DiagnosisOutput, ReproductionResult
from ascend_agent.providers.service import resolve_provider
from ascend_agent.cli.io import load_model_json, write_model_json
from ascend_agent.runtime.permissions import PermissionMode
from ascend_agent.runtime.workflow_runner import WorkflowRunner

console = Console()
reproduce_app = typer.Typer(name="reproduce", help="Reproduce an issue from a diagnosis")


@reproduce_app.command(name="run")
def reproduce_run(
    ctx: typer.Context,
    diagnosis: str = typer.Argument(..., help="Path to diagnosis JSON file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Path to write reproduction result as JSON"),
    provider: Optional[str] = typer.Option(None, "--provider", help="LLM provider (overrides root --provider)"),
    permission_mode: PermissionMode = typer.Option("default", "--permission-mode", help="Permission mode: default, plan, accept_edits, bypass"),
):
    """Reproduce diagnosed issues by executing reproduction commands.

    Loads a diagnosis JSON file, runs the reproduction workflow on each
    hypothesis, and displays structured results. Use --output to save
    results as JSON for Phase 5 verification.
    """
    try:
        diagnosis_output = load_model_json(DiagnosisOutput, diagnosis, label="diagnosis")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    repo_path = diagnosis_output.context_doc.repo.path
    resolved_provider = resolve_provider(provider or (ctx.obj.get("provider") if ctx.obj else None))

    console.print("\n[bold cyan]Running reproduction...[/bold cyan]")
    try:
        runner = WorkflowRunner(provider=resolved_provider, permission_mode=permission_mode)
        result = runner.run_reproduce(
            diagnosis=diagnosis_output.diagnosis_result,
            repo_path=repo_path,
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print(f"[yellow]Hint: Set the appropriate API key environment variable for provider '{resolved_provider}'.[/yellow]")
        raise typer.Exit(code=1)

    # Set repo_path on result so downstream consumers (e.g., verify) know which repo was used
    result.repo_path = repo_path
    status_color = "green" if result.status == "success" else "red"
    console.print(f"\n[bold]Reproduction Result[/bold]")
    console.print(f"Status: [{status_color}]{result.status}[/{status_color}]")
    console.print(f"Command: [cyan]{result.command}[/cyan]")
    console.print(f"Exit code: {result.exit_code}")
    console.print(f"Duration: {result.duration_seconds:.2f}s")
    console.print(f"Hypothesis tested: {result.hypothesis_id_tested}")
    if result.stdout:
        console.print(f"\n[bold]stdout:[/bold]\n{result.stdout}")
    if result.stderr:
        console.print(f"\n[bold red]stderr:[/bold red]\n{result.stderr}")

    if output is not None:
        write_model_json(result, output)
        console.print(f"[green]Saved reproduction result to {output}[/green]")
