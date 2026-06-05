"""verify CLI — run test verification on reproduction results."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ascend_agent.config import settings
from ascend_agent.diagnosis.models import ReproductionResult
from ascend_agent.providers.service import resolve_provider
from ascend_agent.cli.io import load_model_json, write_model_json
from ascend_agent.runtime.permissions import PermissionMode
from ascend_agent.runtime.workflow_runner import WorkflowRunner

console = Console()
verify_app = typer.Typer(name="verify", help="Verify fixes by running relevant tests")


@verify_app.callback()
def verify_root():
    """Verify fixes by running relevant tests."""


@verify_app.command(name="run")
def verify_run(
    ctx: typer.Context,
    reproduction: str = typer.Argument(..., help="Path to reproduction result JSON"),
    output: str | None = typer.Option(None, "--output", "-o", help="Path to write verification result as JSON"),
    provider: Optional[str] = typer.Option(None, "--provider", help="LLM provider (overrides root --provider)"),
    permission_mode: PermissionMode = typer.Option("default", "--permission-mode", help="Permission mode: default, plan, accept_edits, bypass"),
):
    """Verify fixes by running tests against the changed files.

    Loads a reproduction JSON, auto-detects the test framework, maps changed
    files to test files, runs the relevant tests, and displays pass/fail results.
    """
    try:
        reproduction_result = load_model_json(ReproductionResult, reproduction, label="reproduction")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    repo_path = reproduction_result.repo_path or settings.repo_path or "."
    resolved_provider = resolve_provider(provider or (ctx.obj.get("provider") if ctx.obj else None))

    console.print("\n[bold cyan]Running verification...[/bold cyan]")
    try:
        runner = WorkflowRunner(provider=resolved_provider, permission_mode=permission_mode)
        result = runner.run_verify(
            reproduction=reproduction_result,
            repo_path=repo_path,
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print(f"[yellow]Hint: Set the appropriate API key environment variable for provider '{resolved_provider}'.[/yellow]")
        raise typer.Exit(code=1)

    status_color = "green" if result.status == "pass" else ("yellow" if result.status == "no_tests" else "red")
    console.print(f"\n[bold]Verification Result[/bold]")
    console.print(f"Status: [{status_color}]{result.status}[/{status_color}]")
    console.print(f"Framework: [cyan]{result.framework or 'none detected'}[/cyan]")
    console.print(f"Command: [dim]{result.command}[/dim]")
    console.print(f"Tests found: {result.tests_found} | Tests run: {result.tests_run}")
    console.print(f"Passed: [green]{result.passed}[/green] | Failed: [red]{result.failed}[/red] | Errors: [red]{result.errors}[/red]")
    if result.skipped > 0:
        console.print(f"Skipped: [yellow]{result.skipped}[/yellow]")
    console.print(f"Duration: {result.duration_seconds:.2f}s")
    console.print(f"\n[bold]Summary:[/bold] {result.summary}")

    if result.files_tested:
        console.print(f"\n[dim]Test files executed:[/dim]")
        for tf in result.files_tested:
            console.print(f"  • {tf}")

    if result.tests:
        table = Table(title="Per-Test Details")
        table.add_column("Test", style="cyan")
        table.add_column("Outcome", style="bold")
        table.add_column("Duration", style="dim")
        table.add_column("Message")
        for t in result.tests:
            outcome_color = "green" if t.outcome == "passed" else "red"
            table.add_row(
                t.nodeid,
                f"[{outcome_color}]{t.outcome}[/{outcome_color}]",
                f"{t.duration:.3f}s" if t.duration is not None else "-",
                t.message or "",
            )
        console.print(table)

    if output is not None:
        write_model_json(result, output)
        console.print(f"[green]Saved verification result to {output}[/green]")

    if result.status in ("fail", "error", "timeout"):
        raise typer.Exit(code=1)
