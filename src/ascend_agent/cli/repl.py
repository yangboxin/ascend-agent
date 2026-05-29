from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel

from ascend_agent.cli.config_manager import ConfigManager

console = Console()


def run_repl(provider: str = ""):
    """Enter the interactive REPL."""
    cm = ConfigManager()

    if not provider:
        provider = cm.get_active()

    console.print(Panel.fit(
        "[bold]Ascend Diagnostic Agent — Interactive Mode[/bold]\n"
        "Type [bold]/help[/bold] for commands or [bold]/quit[/bold] to exit.",
        border_style="cyan",
    ))

    while True:
        try:
            line = console.input("[bold cyan]ascend>[/bold cyan] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Goodbye![/yellow]")
            break

        line = line.strip()
        if not line:
            continue

        if line.startswith("/"):
            _handle_command(line[1:].strip(), cm)
        else:
            _handle_text_input(line)


def _handle_command(raw: str, cm: ConfigManager):
    parts = raw.split()
    if not parts:
        return

    cmd = parts[0]
    args = parts[1:]

    if cmd in ("quit", "exit", "q"):
        console.print("[yellow]Goodbye![/yellow]")
        sys.exit(0)

    elif cmd == "help":
        _show_help()

    elif cmd == "models":
        _handle_models(args, cm)

    else:
        console.print(f"[red]Unknown command:[/red] /{cmd}")
        console.print("  Type [bold]/help[/bold] for available commands.")


def _handle_text_input(text: str):
    console.print("[dim]Enter a slash command or type /help for options.[/dim]")


def _show_help():
    console.print(Panel.fit(
        "[bold]Available Commands[/bold]\n\n"
        "  [bold]/models[/bold]          Open interactive provider & model manager\n"
        "  [bold]/help[/bold]            Show this help\n"
        "  [bold]/quit[/bold]            Exit the interactive session\n"
        "  [bold]/exit[/bold]            Same as /quit",
        border_style="green",
    ))


def _handle_models(args: list[str], cm: ConfigManager):
    from ascend_agent.cli.models_browser import show_provider_browser
    show_provider_browser(cm)
