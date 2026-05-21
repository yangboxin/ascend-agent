import json
import os
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax

from ascend_agent.diagnosis.fix_engine import FixEngine
from ascend_agent.diagnosis.models import DiagnosisOutput, FixSuggestion, FixGenerationResult, PartialFailure
from ascend_agent.diagnosis.router import ModelRouter

console = Console()
fix_app = typer.Typer(name="fix", help="Generate fixes based on diagnosis findings")


@fix_app.command(name="run")
def fix_run(
    diagnosis_file: str | None = typer.Argument(
        None, help="Path to diagnosis JSON file (reads from stdin if not provided)"
    ),
    output: str | None = typer.Option(None, "--output", help="Path to write accepted fixes as JSON"),
):
    """Generate fix suggestions for a diagnosis result. Provide a diagnosis JSON file or pipe via stdin."""
    # ── 1. Read diagnosis JSON (D-17: file path or stdin) ──
    try:
        if diagnosis_file is not None:
            with open(diagnosis_file) as f:
                data = f.read()
        elif not sys.stdin.isatty():
            data = sys.stdin.read()
        else:
            console.print("[red]Error:[/red] No diagnosis input provided. "
                          "Provide a file path or pipe JSON via stdin.")
            raise typer.Exit(code=1)

        diagnosis_output = DiagnosisOutput.model_validate_json(data)
    except (json.JSONDecodeError, Exception) as e:
        console.print(f"[red]Error:[/red] Failed to parse diagnosis JSON: {e}")
        raise typer.Exit(code=1)

    # ── 2. Extract repo path (D-18) ──
    repo_path = diagnosis_output.context_doc.repo.path

    # ── 3. Initialize FixEngine (D-07: ASCEND_FIX_MODEL) ──
    try:
        router = ModelRouter(model=os.environ.get("ASCEND_FIX_MODEL", "gpt-4o"))
        engine = FixEngine(router=router, repo_path=repo_path)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print(
            "[yellow]Hint: Set the OPENAI_API_KEY environment variable to use the fix engine.[/yellow]"
        )
        raise typer.Exit(code=1)

    # ── 4. Generate fixes ──
    console.print("\n[bold cyan]Generating fix suggestions...[/bold cyan]")
    try:
        result = engine.generate_fixes(diagnosis_output.diagnosis_result)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    # ── 5. Display summary ──
    _display_fix_summary(result)

    if not result.suggestions:
        console.print("[yellow]No fix suggestions could be generated.[/yellow]")
        return

    # ── 6. Review workflow (D-09 through D-11) ──
    accepted = _run_review_workflow(result.suggestions, repo_path)

    # ── 7. Batch apply (D-12) ──
    if accepted:
        apply_result = _apply_fixes_batch(accepted, repo_path)
    else:
        console.print("\n[yellow]No fixes were accepted. Skipping batch apply.[/yellow]")

    # ── 8. Save output (D-19) ──
    if output and accepted:
        _save_fixes_output(accepted, output)


def _display_fix_summary(result: FixGenerationResult):
    """Display a summary of fix generation results."""
    console.print("\n[bold]Fix Generation Complete[/bold]")
    console.print(f"Generated {len(result.suggestions)} fix suggestions"
                  f" for {result.total_hypotheses} hypotheses")

    if result.errors:
        error_text = "\n".join(
            f"[red]{e.stage}:[/red] {e.reason}" + (
                f"\n[dim]{e.details}[/dim]" if e.details else ""
            )
            for e in result.errors
        )
        console.print(Panel(error_text, title="Partial Failures", border_style="red"))


def _run_review_workflow(suggestions: list[FixSuggestion], repo_path: str) -> list[FixSuggestion]:
    """[STUB — Phase 3 Task 2] Sequential review workflow.

    Shows each fix suggestion one at a time with Rich Panel + Syntax diff,
    prompts Accept/Skip/Reject, returns list of accepted fixes.
    """
    ...


def _apply_fixes_batch(accepted: list[FixSuggestion], repo_path: str) -> dict:
    """[STUB — Phase 3 Task 2] Batch apply accepted fixes.

    Groups fixes by file_path, collapses replacements per file,
    calls edit_file for each group, returns apply summary.
    """
    ...


def _save_fixes_output(accepted: list[FixSuggestion], output_path: str):
    """[STUB — Phase 3 Task 2] Save accepted fixes to JSON file."""
    ...
