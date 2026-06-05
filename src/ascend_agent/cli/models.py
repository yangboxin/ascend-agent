from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from ascend_agent.providers.catalog import PROVIDER_PRESETS, full_model_id
from ascend_agent.providers.config_manager import ConfigManager
from ascend_agent.providers.service import (
    add_provider,
    get_model_status,
    is_configured,
    known_models,
    provider_label,
    use_model,
)

models_app = typer.Typer(name="models", help="Configure LLM providers and models.")
console = Console()


def render_models(cm: ConfigManager, *, show_help: bool = True) -> None:
    active_model = cm.get_active_model()

    console.print(
        Panel.fit(
            f"[bold]Current model[/bold]\n[cyan]{active_model}[/cyan]",
            title="Models",
            border_style="cyan",
        )
    )

    for provider in cm.list_providers():
        models = known_models(provider.name) or [provider.default_model]
        status = "connected" if is_configured(provider) else "needs key"
        console.print(f"[bold]{provider_label(provider.name)}[/bold] [dim]{status}[/dim]")
        for index, model in enumerate(models):
            model_id = full_model_id(provider.name, model)
            marker = "[green]*[/green]" if model_id == active_model else " "
            console.print(f"  {marker} {model_id}")
            if index == len(models) - 1:
                console.print(f"    [dim]{provider.base_url}[/dim]")

    if show_help:
        console.print(
            "[dim]Use /models use openai/gpt-5.5, /models add deepseek, "
            "or /models status.[/dim]"
        )


def render_status(cm: ConfigManager) -> None:
    status = get_model_status(cm)

    console.print(
        Panel.fit(
            "\n".join(
                [
                    f"model: [cyan]{status.active_model}[/cyan]",
                    f"provider: {status.provider}",
                    f"configured: {'yes' if status.configured else 'no'}",
                    f"config: {status.config_file}",
                    f"env: {' or '.join(status.env_names)}",
                ]
            ),
            title="Model Status",
            border_style="cyan",
        )
    )


def handle_models_command(args: list[str], cm: ConfigManager) -> bool:
    action = args[0] if args else "show"

    try:
        if action in ("show", "list", "ls"):
            render_models(cm, show_help=True)
        elif action == "status":
            render_status(cm)
        elif action == "use":
            if len(args) < 2:
                console.print("[yellow]Usage:[/yellow] /models use <provider/model>")
                return False
            selected = use_model(cm, args[1])
            console.print(f"[green]Model selected:[/green] {selected}")
            return True
        elif action == "add":
            if len(args) < 2:
                console.print("[yellow]Usage:[/yellow] /models add <provider> [model]")
                return False
            provider = args[1]
            model = args[2] if len(args) > 2 else ""
            preset = PROVIDER_PRESETS.get(provider)
            base_url = preset.base_url if preset else console.input("Base URL: ").strip()
            model = model or (preset.default_model if preset else console.input("Model: ").strip())
            api_key = console.input("API key (empty to use env): ").strip()
            record = add_provider(cm, provider, api_key=api_key, base_url=base_url, model=model)
            console.print(f"[green]Provider connected:[/green] {record.name}/{record.default_model}")
            return True
        else:
            selected = use_model(cm, action)
            console.print(f"[green]Model selected:[/green] {selected}")
            return True
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return False

    return False


@models_app.callback(invoke_without_command=True)
def models_root(ctx: typer.Context):
    """Show the current model and available provider/model IDs."""
    if ctx.invoked_subcommand is None:
        render_models(ConfigManager())


@models_app.command("list")
def models_list():
    """List available provider/model IDs."""
    render_models(ConfigManager(), show_help=False)


@models_app.command("status")
def models_status():
    """Show the active model and credential source hints."""
    render_status(ConfigManager())


@models_app.command("use")
def models_use(model: str = typer.Argument(..., help="Model ID, for example openai/gpt-5.5")):
    """Select the active model."""
    cm = ConfigManager()
    try:
        selected = use_model(cm, model)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    console.print(f"[green]Model selected:[/green] {selected}")


@models_app.command("add")
def models_add(
    provider: str = typer.Argument(..., help="Provider ID, for example openai or deepseek"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name for this provider."),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="OpenAI-compatible base URL."),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key to store in the local config."),
):
    """Connect a provider using a known preset or custom OpenAI-compatible endpoint."""
    cm = ConfigManager()
    preset = PROVIDER_PRESETS.get(provider)
    if api_key is None:
        api_key = typer.prompt("API key (empty to use env)", default="", show_default=False)
    if preset is None:
        if base_url is None:
            base_url = typer.prompt("Base URL")
        if model is None:
            model = typer.prompt("Model")
    try:
        record = add_provider(
            cm,
            provider,
            api_key=api_key,
            base_url=base_url or (preset.base_url if preset else ""),
            model=model or (preset.default_model if preset else ""),
        )
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    console.print(f"[green]Provider connected:[/green] {record.name}/{record.default_model}")
