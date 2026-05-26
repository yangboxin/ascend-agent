from __future__ import annotations

import asyncio
import json
import os
from collections import defaultdict
from pathlib import Path
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax

from ascend_agent.diagnosis.fix_engine import FixEngine
from ascend_agent.diagnosis.models import DiagnosisOutput, FixSuggestion, FixGenerationResult, PartialFailure
from typing import Optional

from ascend_agent.diagnosis.router import create_router
from ascend_agent.tools.file_edit import edit_file

console = Console()
fix_app = typer.Typer(name="fix", help="Generate fixes based on diagnosis findings")


@fix_app.command(name="run")
def fix_run(
    ctx: typer.Context,
    diagnosis_file: Optional[str] = typer.Argument(
        None, help="Path to diagnosis JSON file (reads from stdin if not provided)"
    ),
    output: Optional[str] = typer.Option(None, "--output", help="Path to write accepted fixes as JSON"),
    provider: Optional[str] = typer.Option(None, "--provider", help="LLM provider (overrides root --provider)"),
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
    resolved_provider = provider or (ctx.obj.get("provider", "openai") if ctx.obj else "openai")
    try:
        router = create_router(provider=resolved_provider)
        engine = FixEngine(router=router, repo_path=repo_path)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print(
            f"[yellow]Hint: Set the appropriate API key environment variable for provider '{resolved_provider}'.[/yellow]"
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
    """Sequential review workflow (D-09 through D-11).

    Shows each fix suggestion one at a time with Rich Panel + Syntax diff,
    prompts Accept/Skip/Reject, returns list of accepted fixes.
    """
    accepted: list[FixSuggestion] = []
    total = len(suggestions)

    if total == 0:
        return accepted

    for idx, suggestion in enumerate(suggestions, 1):
        # Header
        console.print(
            f"\n[bold cyan]Fix {idx}/{total}[/bold cyan]"
            f" — [bold]{suggestion.file_path}[/bold]"
        )

        # Explanation
        console.print(f"\n[bold]Explanation:[/bold] {suggestion.explanation}")

        # Diff display (D-11: Rich Panel + Syntax with "diff" lexer)
        diff_syntax = Syntax(
            suggestion.diff_patch,
            "diff",
            theme="monokai",
            line_numbers=True,
        )
        console.print(Panel(
            diff_syntax,
            title=f"Suggested Changes — {suggestion.file_path}",
            border_style="blue",
        ))

        # Prompt (D-10: Accept / Skip / Reject)
        action = Prompt.ask(
            "[bold]Action[/bold] ([green]A[/green]ccept / [yellow]S[/yellow]kip / [red]R[/red]eject)",
            choices=["a", "s", "r"],
            default="s",
        )

        if action == "a":
            accepted.append(suggestion)
            console.print("[green]✓ Accepted[/green]")
        elif action == "s":
            console.print("[yellow]→ Skipped[/yellow]")
        elif action == "r":
            console.print("[red]✗ Rejected[/red]")

        console.print()  # blank line for spacing

    return accepted


def _apply_fixes_batch(accepted: list[FixSuggestion], repo_path: str) -> dict:
    """Batch apply accepted fixes (D-12).

    Groups accepted FixSuggestions by file_path (Pitfall 5 mitigation),
    collapses all replacements per file, calls edit_file for each group.
    """
    console.print("\n[bold cyan]Applying accepted fixes...[/bold cyan]")

    # Group by file_path (Pitfall 5 mitigation)
    by_file: dict[str, list[dict]] = defaultdict(list)
    for suggestion in accepted:
        for replacement in suggestion.replacements:
            by_file[suggestion.file_path].append(
                {"old_text": replacement.old_text, "new_text": replacement.new_text}
            )

    applied = 0
    failed = 0

    for file_path, ops_dicts in by_file.items():
        resolved_path = Path(repo_path) / file_path

        try:
            result_str = asyncio.run(edit_file(
                file_path=str(resolved_path),
                operations=ops_dicts,
                repo_path=repo_path,
            ))
            result = json.loads(result_str)
            if result.get("status") == "ok":
                console.print(f"[green]  ✓ {file_path}[/green]")
                applied += 1
            else:
                console.print(f"[red]  ✗ {file_path}: {result.get('error', 'unknown error')}[/red]")
                failed += 1
        except Exception as e:
            console.print(f"[red]  ✗ {file_path}: {e}[/red]")
            failed += 1

    # Summary
    if failed > 0:
        console.print(f"\n[bold green]Applied {applied} file(s)[/bold green]"
                      f"  [bold red]Failed: {failed}[/bold red]")
    else:
        console.print(f"\n[bold green]Applied {applied} file(s)[/bold green]")

    return {"applied": applied, "failed": failed}


def _save_fixes_output(accepted: list[FixSuggestion], output_path: str):
    """Save accepted fixes to JSON file (D-19)."""
    accepted_list = [s.model_dump() for s in accepted]
    with open(output_path, "w") as f:
        json.dump(accepted_list, f, indent=2)
    console.print(f"[green]✓ Saved accepted fixes to {output_path}[/green]")
