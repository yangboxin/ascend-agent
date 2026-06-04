from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from ascend_agent.cli.config_manager import ConfigManager
from ascend_agent.runtime import AgentLoop, QueryEngine, Session, ToolRegistry

console = Console()


def run_repl(provider: str = "") -> None:
    """Run a small runtime-backed interactive session."""
    cm = ConfigManager()
    active_provider = provider or cm.get_active()
    active_model = cm.get_active_model()
    session = Session(working_dir=Path.cwd(), provider=active_provider, model=active_model)
    loop: AgentLoop | None = None

    console.print(
        Panel.fit(
            "[bold]Ascend Agent[/bold]\n"
            "Type [bold]/help[/bold] for commands or [bold]/quit[/bold] to exit.\n"
            f"Active model: [cyan]{active_model}[/cyan]",
            border_style="cyan",
        )
    )

    while True:
        try:
            line = console.input("[bold cyan]ascend>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Goodbye![/yellow]")
            return

        if not line:
            continue
        if line.startswith("/"):
            command = line[1:].strip()
            if command in {"quit", "exit", "q"}:
                console.print("[yellow]Goodbye![/yellow]")
                return
            if command == "help":
                _show_help()
                continue
            if command.startswith("models"):
                from ascend_agent.cli.models import handle_models_command

                handle_models_command(command.split()[1:], cm)
                active_provider = cm.get_active()
                active_model = cm.get_active_model()
                session = Session(working_dir=Path.cwd(), provider=active_provider, model=active_model)
                loop = None
                continue
            if command == "reset":
                session = Session(working_dir=Path.cwd(), provider=active_provider, model=active_model)
                console.print("[green]Session reset.[/green]")
                continue
            console.print(f"[red]Unknown command:[/red] /{command}")
            continue

        if loop is None:
            try:
                registry = ToolRegistry.from_patterns(["impl:ascend:*", "workflow:ascend:*"])
                loop = AgentLoop(QueryEngine.create(active_provider, registry))
            except ValueError as exc:
                console.print(f"[red]Error:[/red] {exc}")
                continue

        try:
            response = loop.run_turn(session, line)
        except Exception as exc:
            console.print(f"[red]Agent turn failed:[/red] {exc}")
            continue
        console.print(Panel(response, title=f"Ascend Agent ({active_provider})", border_style="cyan"))


def _show_help() -> None:
    console.print(
        Panel.fit(
            "[bold]Commands[/bold]\n\n"
            "  [bold]/models[/bold]          Show current model and provider IDs\n"
            "  [bold]/models use <id>[/bold] Select a model, e.g. openai/gpt-5.5\n"
            "  [bold]/models add <provider>[/bold] Connect a provider preset\n"
            "  [bold]/reset[/bold]           Reset this session\n"
            "  [bold]/help[/bold]            Show this help\n"
            "  [bold]/quit[/bold]            Exit",
            border_style="green",
        )
    )
