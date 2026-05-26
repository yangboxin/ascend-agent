from __future__ import annotations

import asyncio
import json
import sys

from typing import Optional

import typer
from rich.console import Console

from ascend_agent.config import settings
from ascend_agent.diagnosis.models import DiagnosisOutput, ReproductionResult
from ascend_agent.diagnosis.router import create_router
from ascend_agent.reproduction.engine import ReproductionEngine

console = Console()
reproduce_app = typer.Typer(name="reproduce", help="Reproduce an issue from a diagnosis")


@reproduce_app.command(name="run")
def reproduce_run(
    ctx: typer.Context,
    diagnosis: str = typer.Argument(..., help="Path to diagnosis JSON file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Path to write reproduction result as JSON"),
    provider: Optional[str] = typer.Option(None, "--provider", help="LLM provider (overrides root --provider)"),
):
    """Reproduce diagnosed issues by executing reproduction commands.

    Loads a diagnosis JSON file, runs the reproduction workflow on each
    hypothesis, and displays structured results. Use --output to save
    results as JSON for Phase 5 verification.
    """
    try:
        with open(diagnosis) as f:
            data = f.read()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[red]Error:[/red] Failed to read diagnosis JSON: {e}")
        raise typer.Exit(code=1)

    try:
        diagnosis_output = DiagnosisOutput.model_validate_json(data)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to parse diagnosis JSON: {e}")
        raise typer.Exit(code=1)

    repo_path = diagnosis_output.context_doc.repo.path
    resolved_provider = provider or (ctx.obj.get("provider", "openai") if ctx.obj else "openai")

    try:
        router = create_router(provider=resolved_provider)
        engine = ReproductionEngine(router=router, repo_path=repo_path, settings=settings)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print(f"[yellow]Hint: Set the appropriate API key environment variable for provider '{resolved_provider}'.[/yellow]")
        raise typer.Exit(code=1)

    console.print("\n[bold cyan]Running reproduction...[/bold cyan]")
    try:
        result = asyncio.run(engine.reproduce(diagnosis_output.diagnosis_result))
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
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
        with open(output, "w") as f:
            f.write(result.model_dump_json(indent=2))
        console.print(f"[green]Saved reproduction result to {output}[/green]")
