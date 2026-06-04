from __future__ import annotations

import json
import io
import sys
from typing import Optional

import typer
from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from ascend_agent.config import settings
from ascend_agent.config import Settings
from ascend_agent.context.models import ConfigEnv, ContextDocument
from ascend_agent.context.repo import RepoScanner
from ascend_agent.context.trace import (
    trace_bundle_from_dir,
    trace_bundle_from_files,
    trace_from_stdin,
    trace_from_text,
)
from ascend_agent.diagnosis.engine import Engine
from ascend_agent.diagnosis.models import DiagnosisOutput, DiagnosisResult, Hypothesis, Evidence, PartialFailure
from ascend_agent.diagnosis.router import create_router
from ascend_agent.diagnosis.tool_client import create_tool_client

console = Console()
diagnose_app = typer.Typer(name="diagnose", help="Diagnose an issue from a stack trace against a code repository")


def render_context(doc: ContextDocument, width: int = 120) -> str:
    """Render the CLI context display as plain text for non-CLI surfaces."""
    buffer = io.StringIO()
    render_console = Console(file=buffer, force_terminal=False, width=width)
    _display_context(doc, target_console=render_console)
    return buffer.getvalue().rstrip()


def render_diagnosis(result: DiagnosisResult, width: int = 120) -> str:
    """Render the CLI diagnosis display as plain text for non-CLI surfaces."""
    buffer = io.StringIO()
    render_console = Console(file=buffer, force_terminal=False, width=width)
    _display_diagnosis(result, target_console=render_console)
    return buffer.getvalue().rstrip()


@diagnose_app.command(name="run")
def diagnose_run(
    ctx: typer.Context,
    repo: str = typer.Argument(..., help="Path to local repository"),
    trace: Optional[list[str]] = typer.Option(None, "--trace", help="Path to trace/log file (repeatable)"),
    trace_dir: Optional[str] = typer.Option(None, "--trace-dir", help="Directory containing trace/log files"),
    trace_text: Optional[str] = typer.Option(None, "--trace-text", help="Inline pasted trace text"),
    output: Optional[str] = typer.Option(None, "--output", help="Path to write context as JSON"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Start interactive REPL mode"),
    provider: Optional[str] = typer.Option(None, "--provider", help="LLM provider (overrides root --provider)"),
    tool_backend: Optional[str] = typer.Option(None, "--tool-backend", help="Diagnosis tool backend: auto|local|mcp"),
    show_tool_logs: bool = typer.Option(False, "--show-tool-logs", help="Show captured MCP/tool logs"),
):
    """Analyze a stack trace against a code repository.

    Provide the trace as file(s) (--trace), a directory (--trace-dir),
    inline text (--trace-text), or pipe via stdin.
    The repository path is required and must be a local directory.
    """
    resolved_provider = provider or (ctx.obj.get("provider", "openai") if ctx.obj else "openai")

    if interactive:
        _repl_mode(repo, resolved_provider)
        return

    _one_shot_mode(repo, trace, trace_dir, trace_text, output, resolved_provider, tool_backend, show_tool_logs)


def _one_shot_mode(
    repo: str,
    trace_paths: list[str] | None,
    trace_dir: str | None,
    trace_text_arg: str | None,
    output_path: str | None,
    provider: str = "openai",
    tool_backend: str | None = None,
    show_tool_logs: bool = False,
):
    console.print("[bold]Ascend Diagnostic Agent[/bold]")
    console.print("[cyan]Building context...[/cyan]")

    try:
        repo_info = RepoScanner().scan(repo)
    except OSError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    explicit_trace_inputs = sum(
        bool(value)
        for value in (trace_paths, trace_dir, trace_text_arg)
    )
    if explicit_trace_inputs > 1:
        console.print("[red]Error:[/red] Use only one trace input method: --trace, --trace-dir, or --trace-text")
        raise typer.Exit(code=1)

    trace_info = None
    trace_bundle = None
    if trace_dir is not None:
        trace_bundle = trace_bundle_from_dir(trace_dir)
        trace_info = trace_bundle.to_trace_info()
    elif trace_paths:
        if len(trace_paths) == 1:
            trace_bundle = trace_bundle_from_files(trace_paths)
            trace_info = trace_bundle.sources[0].trace
        else:
            trace_bundle = trace_bundle_from_files(trace_paths)
            trace_info = trace_bundle.to_trace_info()
    elif trace_text_arg is not None:
        trace_info = trace_from_text(trace_text_arg)
    elif not sys.stdin.isatty():
        trace_info = trace_from_stdin()

    config_env = ConfigEnv(
        python_version=settings.python_version,
        platform=settings.platform,
        env_vars=settings.env_vars,
    )
    doc = ContextDocument(
        repo=repo_info,
        trace=trace_info,
        trace_bundle=trace_bundle,
        config_env=config_env,
    )

    _display_context(doc)

    console.print("\n[bold cyan]Running diagnosis...[/bold cyan]")
    try:
        router = create_router(provider=provider)
        tool_log = io.StringIO()
        tool_settings = None
        if tool_backend is not None:
            tool_settings = Settings(diagnosis_tool_backend=tool_backend)
        tool_client = create_tool_client(settings=tool_settings, errlog=tool_log)

        async def search_code_with_log(pattern: str, path: str) -> str:
            tool_log.write(f"code_search pattern={pattern!r} path={path}\n")
            result_text = await tool_client.search_code(pattern, path)
            first_line = result_text.splitlines()[0] if result_text else ""
            if first_line:
                tool_log.write(f"code_search result={first_line[:300]}\n")
            return result_text

        engine = Engine(
            router=router,
            repo_path=repo,
            search_tool=search_code_with_log,
        )
        result = engine.diagnose(doc)
        if show_tool_logs:
            captured_tool_log = tool_log.getvalue().strip()
            if captured_tool_log:
                console.print(Panel(captured_tool_log, title="Tool Logs", border_style="dim"))
        _display_diagnosis(result)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print(f"[yellow]Hint: Set the appropriate API key environment variable for provider '{provider}'.[/yellow]")
        raise typer.Exit(code=1)

    if output_path is not None:
        output_wrapper = DiagnosisOutput(context_doc=doc, diagnosis_result=result)
        with open(output_path, "w") as f:
            f.write(output_wrapper.model_dump_json(indent=2))


def _repl_mode(repo: str, provider: str = "openai"):
    console.print("[bold]Ascend Diagnostic Agent — REPL mode[/bold]")
    console.print("Type a stack trace or ':help' for commands.")
    console.print(f"[dim]Active LLM provider: {provider}[/dim]")

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
    router = None
    chat_messages = [
        {
            "role": "system",
            "content": (
                "You are the currently selected Ascend Diagnostic Agent LLM. "
                "Answer concisely and use the current diagnostic context when provided."
            ),
        }
    ]

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
                console.print("  :chat <msg>  Chat with the active LLM provider")
                console.print("  :reset-chat  Clear LLM chat history")
                console.print("  :quit/:exit  Exit REPL")
            elif cmd == "output":
                console.print(current_doc.model_dump_json(indent=2))
            elif cmd.startswith("chat "):
                user_message = cmd[5:].strip()
                if not user_message:
                    console.print("[yellow]Usage:[/yellow] :chat <message>")
                    continue
                if router is None:
                    try:
                        router = create_router(provider=provider)
                    except ValueError as e:
                        console.print(f"[red]Error:[/red] {e}")
                        continue
                context = current_doc.model_dump_json(indent=2)
                chat_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Current diagnostic context JSON:\n"
                            f"{context}\n\nUser message:\n{user_message}"
                        ),
                    }
                )
                try:
                    response = router.chat(chat_messages)
                except Exception as e:
                    console.print(f"[red]LLM chat failed:[/red] {e}")
                    chat_messages.pop()
                    continue
                chat_messages.append({"role": "assistant", "content": response})
                console.print(Panel(response, title=f"LLM ({provider})", border_style="cyan"))
            elif cmd == "reset-chat":
                chat_messages = chat_messages[:1]
                console.print("[green]LLM chat history cleared.[/green]")
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


def _display_context(doc: ContextDocument, target_console: Console | None = None):
    out = target_console or console
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
        out.print(table)

    if doc.trace_bundle:
        table = Table(title="Trace Bundle")
        table.add_column("Source", style="cyan")
        table.add_column("Lines", style="green")
        table.add_column("Primary Error", style="yellow")
        for source in doc.trace_bundle.sources[:10]:
            trace = source.trace
            table.add_row(
                source.path,
                str(source.line_count),
                f"{trace.error_type or 'unknown'}: {trace.error_message or 'unknown'}",
            )
        if len(doc.trace_bundle.sources) > 10:
            table.add_row(f"... {len(doc.trace_bundle.sources) - 10} more", "", "")
        out.print(table)

    if doc.trace:
        if doc.trace.error_type:
            out.print(f"\n[bold red]Error:[/bold red] {doc.trace.error_type}")
            out.print(f"[red]{doc.trace.error_message or ''}[/red]")
        else:
            out.print("\n[bold yellow]Error:[/bold yellow] not detected")
            if doc.trace.parse_warnings:
                out.print(f"[dim]{', '.join(doc.trace.parse_warnings)}[/dim]")
        if doc.trace.signal_candidates:
            preview = ", ".join(
                f"{candidate.kind}={candidate.value} ({candidate.confidence:.2f})"
                for candidate in doc.trace.signal_candidates[:5]
            )
            out.print(f"[yellow]Uncertain signals:[/yellow] {preview}")
        out.print("\n[bold]Stack Trace:[/bold]")
        for i, frame in enumerate(doc.trace.frames):
            if i >= 10:
                out.print(f"  [dim]... {len(doc.trace.frames) - 10} more frames[/dim]")
                break
            out.print(f"  [dim]{frame.file}:{frame.line}[/dim] [yellow]{frame.function}[/yellow]")

    out.print(f"\n[dim]Environment: Python {doc.config_env.python_version[:6]} on {doc.config_env.platform}[/dim]")


def _display_diagnosis(result: DiagnosisResult, target_console: Console | None = None):
    out = target_console or console
    out.print("\n[bold]Diagnosis Results[/bold]")
    out.print(f"[cyan]Search iterations used: {result.iterations_used}/3[/cyan]")

    if result.errors:
        error_text = "\n".join(
            f"[red]{e.stage}:[/red] {e.reason}" + (f"\n[dim]{e.details}[/dim]" if e.details else "")
            for e in result.errors
        )
        out.print(Panel(error_text, title="Partial Failures", border_style="red"))

    if not result.hypotheses:
        out.print("[yellow]No hypotheses could be generated.[/yellow]")
        if result.errors:
            out.print("[dim]See Partial Failures above for details.[/dim]")
    else:
        for i, hyp in enumerate(result.hypotheses, 1):
            border = "green" if hyp.confidence >= 0.7 else ("yellow" if hyp.confidence >= 0.4 else "red")
            panel = Panel(
                "",
                title=f"Hypothesis #{i} — Confidence: {hyp.confidence:.0%}",
                border_style=border,
            )
            out.print(panel)
            out.print(f"[bold]Root Cause:[/bold] {hyp.root_cause}")
            for ev in hyp.evidence:
                out.print(f"[blue]File: {ev.file_path}:{ev.line_number}[/blue]")
                out.print(Syntax(ev.code_snippet, "python", theme="monokai", line_numbers=True))
                out.print(f"[italic]{ev.relevance}[/italic]")

    out.print("\n[dim]Diagnosis complete.[/dim]")
