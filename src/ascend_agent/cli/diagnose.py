import json
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from ascend_agent.config import settings
from ascend_agent.context.models import ConfigEnv, ContextDocument
from ascend_agent.context.repo import RepoScanner
from ascend_agent.context.trace import trace_from_file, trace_from_stdin, trace_from_text

console = Console()
diagnose_app = typer.Typer(name="diagnose", help="Diagnose an issue from a stack trace against a code repository")


@diagnose_app.command(name="run")
def diagnose_run(
    repo: str = typer.Argument(..., help="Path to local repository"),
    trace: str | None = typer.Option(None, "--trace", help="Path to trace/log file"),
    trace_text: str | None = typer.Option(None, "--trace-text", help="Inline pasted trace text"),
    output: str | None = typer.Option(None, "--output", help="Path to write context as JSON"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Start interactive REPL mode"),
):
    """Analyze a stack trace against a code repository.

    Provide the trace as a file (--trace), inline text (--trace-text), or pipe via stdin.
    The repository path is required and must be a local directory.
    """
    if interactive:
        _repl_mode(repo)
        return

    _one_shot_mode(repo, trace, trace_text, output)


def _one_shot_mode(
    repo: str,
    trace_path: str | None,
    trace_text_arg: str | None,
    output_path: str | None,
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

    if output_path is not None:
        with open(output_path, "w") as f:
            f.write(doc.model_dump_json(indent=2))


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
