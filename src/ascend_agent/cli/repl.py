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
    active_model = cm.get_active_model()
    state = {
        "provider": provider,
        "model": active_model,
        "router": None,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the currently selected Ascend Diagnostic Agent LLM. "
                    "Answer concisely and help with debugging, diagnosis, reproduction, and fixes."
                ),
            }
        ],
    }

    console.print(Panel.fit(
        "[bold]Ascend Diagnostic Agent — Interactive Mode[/bold]\n"
        "Type [bold]/help[/bold] for commands or [bold]/quit[/bold] to exit.\n"
        f"Active model: [cyan]{active_model}[/cyan]",
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
            _handle_command(line[1:].strip(), cm, state)
        else:
            _handle_text_input(line)


def _handle_command(raw: str, cm: ConfigManager, state: dict):
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
        new_model = cm.get_active_model()
        new_provider = cm.get_active()
        if new_model != state["model"]:
            state["provider"] = new_provider
            state["model"] = new_model
            state["router"] = None
            state["messages"] = state["messages"][:1]
            console.print(f"[green]Active model:[/green] {new_model}")

    elif cmd == "chat":
        _handle_chat(" ".join(args), state)

    elif cmd == "reset-chat":
        state["messages"] = state["messages"][:1]
        console.print("[green]LLM chat history cleared.[/green]")

    else:
        console.print(f"[red]Unknown command:[/red] /{cmd}")
        console.print("  Type [bold]/help[/bold] for available commands.")


def _handle_text_input(text: str):
    console.print("[dim]Enter a slash command or type /help for options.[/dim]")


def _show_help():
    console.print(Panel.fit(
        "[bold]Available Commands[/bold]\n\n"
        "  [bold]/models[/bold]          Show current model and available model IDs\n"
        "  [bold]/models use <id>[/bold] Select a model, e.g. openai/gpt-5.5\n"
        "  [bold]/models add <provider>[/bold] Connect a provider preset\n"
        "  [bold]/chat <message>[/bold]  Chat with the active LLM provider\n"
        "  [bold]/reset-chat[/bold]      Clear LLM chat history\n"
        "  [bold]/help[/bold]            Show this help\n"
        "  [bold]/quit[/bold]            Exit the interactive session\n"
        "  [bold]/exit[/bold]            Same as /quit",
        border_style="green",
    ))


def _handle_models(args: list[str], cm: ConfigManager):
    from ascend_agent.cli.models import handle_models_command

    handle_models_command(args, cm)


def _handle_chat(message: str, state: dict):
    if not message.strip():
        console.print("[yellow]Usage:[/yellow] /chat <message>")
        return

    if state["router"] is None:
        try:
            from ascend_agent.diagnosis.router import create_router

            state["router"] = create_router(provider=state["provider"])
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            return

    state["messages"].append({"role": "user", "content": message})
    try:
        response = state["router"].chat(state["messages"])
    except Exception as e:
        console.print(f"[red]LLM chat failed:[/red] {e}")
        state["messages"].pop()
        return
    state["messages"].append({"role": "assistant", "content": response})
    console.print(Panel(response, title=f"LLM ({state['provider']})", border_style="cyan"))
