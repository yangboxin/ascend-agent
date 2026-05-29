from __future__ import annotations

import json
import sys
from typing import Optional

import typer
from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from ascend_agent.config import settings
from ascend_agent.context.models import ConfigEnv, ContextDocument
from ascend_agent.context.repo import RepoScanner
from ascend_agent.context.trace import trace_from_file, trace_from_stdin, trace_from_text
from ascend_agent.diagnosis.engine import Engine
from ascend_agent.diagnosis.models import DiagnosisOutput, DiagnosisResult, Hypothesis, Evidence, PartialFailure
from ascend_agent.diagnosis.router import create_router
from ascend_agent.diagnosis.tool_client import create_tool_client

console = Console()
diagnose_app = typer.Typer(name="diagnose", help="Diagnose an issue from a stack trace against a code repository")


@diagnose_app.command(name="run")
def diagnose_run(
    ctx: typer.Context,
    repo: str = typer.Argument(..., help="Path to local repository"),
    trace: Optional[str] = typer.Option(None, "--trace", help="Path to trace/log file"),
    trace_text: Optional[str] = typer.Option(None, "--trace-text", help="Inline pasted trace text"),
    output: Optional[str] = typer.Option(None, "--output", help="Path to write context as JSON"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Start interactive REPL mode"),
    provider: Optional[str] = typer.Option(None, "--provider", help="LLM provider (overrides root --provider)"),
):
    """Analyze a stack trace against a code repository.

    Provide the trace as a file (--trace), inline text (--trace-text), or pipe via stdin.
    The repository path is required and must be a local directory.
    """
    resolved_provider = provider or (ctx.obj.get("provider", "openai") if ctx.obj else "openai")

    if interactive:
        _repl_mode(repo)
        return

    _one_shot_mode(repo, trace, trace_text, output, resolved_provider)


def _one_shot_mode(
    repo: str,
    trace_path: str | None,
    trace_text_arg: str | None,
    output_path: str | None,
    provider: str = "openai",
):
    console.print("[bold]Ascend Diagnostic Agent[/bold]")
    console.print("[cyan]Building context...[/cyan]")

    try:
        repo_info = RepoScanner().scan(repo)
    except OSError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    trace_info = None
    if trace_path is not None:
        trace_info = trace_from_file(trace_path)
    elif trace_text_arg is not None:
        trace_info = trace_from_text(trace_text_arg)
    elif not sys.stdin.isatty():
        trace_info = trace_from_stdin()

    config_env = ConfigEnv(
        python_version=settings.python_version,
        platform=settings.platform,
        env_vars=settings.env_vars,
    )
    doc = ContextDocument(repo=repo_info, trace=trace_info, config_env=config_env)

    _display_context(doc)

    console.print("\n[bold cyan]Running diagnosis...[/bold cyan]")
    try:
        router = create_router(provider=provider)
        tool_client = create_tool_client()
        engine = Engine(
            router=router,
            repo_path=repo,
            search_tool=tool_client.search_code,
        )
        result = engine.diagnose(doc)
        _display_diagnosis(result)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print(f"[yellow]Hint: Set the appropriate API key environment variable for provider '{provider}'.[/yellow]")
        raise typer.Exit(code=1)

    if output_path is not None:
        output_wrapper = DiagnosisOutput(context_doc=doc, diagnosis_result=result)
        with open(output_path, "w") as f:
            f.write(output_wrapper.model_dump_json(indent=2))


def _repl_mode(repo: str):
    console.print("[bold]Ascend Diagnostic Agent — REPL mode[/bold]")
    console.print("Type a stack trace or ':help' for commands.")

    try:
        repo_info = RepoScanner().scan(repo)
    except OSError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    config_env = ConfigEnv(
        python_version=settings.python_version,
        platform=settings.platform,
        env_vars=settings.env_vars,
    )
    current_doc = ContextDocument(repo=repo_info, config_env=config_env)

    while True:
        prompt = console.input("[cyan]>[/cyan] ")
        if prompt.startswith(":"):
            cmd = prompt[1:].strip()
            if cmd in ("quit", "exit"):
                break
            elif cmd == "help":
                console.print("Commands:")
                console.print("  :help        Show this help")
                console.print("  :repo <path> Rescan with new repo path")
                console.print("  :output      Print JSON of current context")
                console.print("  :quit/:exit  Exit REPL")
            elif cmd == "output":
                console.print(current_doc.model_dump_json(indent=2))
            elif cmd.startswith("repo "):
                new_path = cmd[5:].strip()
                try:
                    current_doc.repo = RepoScanner().scan(new_path)
                    console.print(f"[green]Rescanned: {new_path}[/green]")
                except OSError as e:
                    console.print(f"[red]Error:[/red] {e}")
            else:
                console.print(f"[red]Unknown command:[/red] :{cmd}")
        else:
            trace_info = trace_from_text(prompt)
            current_doc.trace = trace_info
            _display_context(current_doc)


def _display_context(doc: ContextDocument):
    if doc.repo:
        table = Table(title="Repository Info")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Path", doc.repo.path)
        table.add_row("Language", doc.repo.language)
        table.add_row("Files", str(doc.repo.file_count))
        structure_preview = ", ".join(doc.repo.structure[:10])
        if len(doc.repo.structure) > 10:
            structure_preview += ", ..."
        table.add_row("Structure", structure_preview)
        console.print(table)

    if doc.trace:
        console.print(f"\n[bold red]Error:[/bold red] {doc.trace.error_type}")
        console.print(f"[red]{doc.trace.error_message}[/red]")
        console.print("\n[bold]Stack Trace:[/bold]")
        for i, frame in enumerate(doc.trace.frames):
            if i >= 10:
                console.print(f"  [dim]... {len(doc.trace.frames) - 10} more frames[/dim]")
                break
            console.print(f"  [dim]{frame.file}:{frame.line}[/dim] [yellow]{frame.function}[/yellow]")

    console.print(f"\n[dim]Environment: Python {doc.config_env.python_version[:6]} on {doc.config_env.platform}[/dim]")


def _display_diagnosis(result: DiagnosisResult):
    console.print("\n[bold]Diagnosis Results[/bold]")
    console.print(f"[cyan]Search iterations used: {result.iterations_used}/3[/cyan]")

    if result.errors:
        error_text = "\n".join(
            f"[red]{e.stage}:[/red] {e.reason}" + (f"\n[dim]{e.details}[/dim]" if e.details else "")
            for e in result.errors
        )
        console.print(Panel(error_text, title="Partial Failures", border_style="red"))

    if not result.hypotheses:
        console.print("[yellow]No hypotheses could be generated.[/yellow]")
        if result.errors:
            console.print("[dim]See Partial Failures above for details.[/dim]")
    else:
        for i, hyp in enumerate(result.hypotheses, 1):
            border = "green" if hyp.confidence >= 0.7 else ("yellow" if hyp.confidence >= 0.4 else "red")
            panel = Panel(
                "",
                title=f"Hypothesis #{i} — Confidence: {hyp.confidence:.0%}",
                border_style=border,
            )
            console.print(panel)
            console.print(f"[bold]Root Cause:[/bold] {hyp.root_cause}")
            for ev in hyp.evidence:
                console.print(f"[blue]File: {ev.file_path}:{ev.line_number}[/blue]")
                console.print(Syntax(ev.code_snippet, "python", theme="monokai", line_numbers=True))
                console.print(f"[italic]{ev.relevance}[/italic]")

    console.print("\n[dim]Diagnosis complete.[/dim]")
