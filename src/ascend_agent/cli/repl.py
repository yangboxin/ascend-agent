from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ascend_agent.providers.config_manager import ConfigManager
from ascend_agent.runtime import (
    PermissionMode,
    Runtime,
    Session,
    list_sessions,
)
from ascend_agent.runtime.commands import build_default_registry

console = Console()


@dataclass
class ReplState:
    """Mutable state shared across the REPL loop and command handlers."""

    provider: str = "openai"
    model: str | None = None
    permission_mode: PermissionMode = "default"
    runtime: Runtime | None = field(default=None, repr=False)
    session: Session | None = field(default=None, repr=False)
    auto_save: bool = True

    def ensure_runtime(self) -> tuple[Runtime, Session]:
        if self.runtime is None:
            self.runtime = Runtime.create(
                provider=self.provider,
                working_dir=Path.cwd(),
                permission_mode=self.permission_mode,
                model=self.model,
            )
        if self.session is None:
            self.session = self.runtime.create_session()
        return self.runtime, self.session

    def refresh_from_config(self, cm: ConfigManager) -> None:
        self.provider = cm.get_active()
        self.model = cm.get_active_model()
        self.runtime = None
        self.session = None


def run_repl(provider: str = "", resume: str | None = None) -> None:
    """Run a runtime-backed interactive session with streaming output."""
    cm = ConfigManager()
    state = ReplState(
        provider=provider or cm.get_active(),
        model=cm.get_active_model(),
    )

    # Resume a previous session if requested
    if resume:
        try:
            state.session = Session.load(resume)
            state.provider = state.session.provider
            state.model = state.session.model
            console.print(f"[green]Resumed session [bold]{resume[:12]}...[/bold][/green]")
        except FileNotFoundError:
            console.print(f"[red]Session {resume[:12]}... not found.[/red]")

    registry = build_default_registry()

    console.print(
        Panel.fit(
            "[bold]Ascend Agent[/bold]\n"
            "Type [bold]/help[/bold] for commands or [bold]/quit[/bold] to exit.\n"
            f"Active model: [cyan]{state.model}[/cyan]",
            border_style="cyan",
        )
    )

    while True:
        try:
            raw = console.input("[bold cyan]ascend>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            _save_and_exit(state)
            return

        if not raw:
            continue

        if raw.startswith("/"):
            _dispatch(raw, cm, state)
            continue

        try:
            state.ensure_runtime()
        except ValueError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            continue

        # Run the agent turn with streaming output
        try:
            asyncio.run(_stream_turn(state, raw))
        except Exception as exc:
            console.print(f"[red]Agent turn failed:[/red] {exc}")
            continue

        # Auto-save after each turn
        if state.auto_save and state.session is not None:
            try:
                state.session.save()
            except Exception:
                pass


async def _stream_turn(state: ReplState, user_input: str) -> None:
    """Run one agent turn with streaming token display."""
    rt = state.runtime
    if rt is None:
        return

    first_content = True
    async for event_type, payload in rt.run_turn(state.session, user_input):  # type: ignore[arg-type]
        if event_type == "user_message":
            pass  # Already displayed by the prompt
        elif event_type == "assistant_message":
            if first_content:
                console.print()  # newline before first output
                first_content = False
            console.print(payload, end="")
        elif event_type == "final":
            if payload:
                if first_content:
                    console.print()
                console.print(f"\n{payload}")
            console.print()
        elif event_type == "tool_call":
            name = payload.get("name", "unknown") if isinstance(payload, dict) else str(payload)
            console.print(f"\n[dim]⏳ Running {name}...[/dim]")
        elif event_type == "tool_result":
            name = payload.get("tool", "?") if isinstance(payload, dict) else "?"
            console.print(f"[dim]✓ {name}[/dim]")
        elif event_type in ("error", "max_turns"):
            console.print(f"\n[yellow]{payload}[/yellow]")


def _save_and_exit(state: ReplState) -> None:
    """Save session before exit."""
    if state.session is not None:
        try:
            filepath = state.session.save()
            console.print(f"\n[yellow]Session saved: {filepath}[/yellow]")
        except Exception:
            pass
    console.print("[yellow]Goodbye![/yellow]")


def _dispatch(line: str, cm: ConfigManager, state: ReplState) -> None:
    """Dispatch a slash-command using the typed registry."""
    parts = line[1:].strip().split(None, 1)
    name = parts[0]
    args = parts[1:] if len(parts) > 1 else []

    # --- quit -------------------------------------------------------------
    if name in ("quit", "exit", "q"):
        _save_and_exit(state)
        raise SystemExit(0)

    # --- help -------------------------------------------------------------
    if name == "help":
        registry = build_default_registry()
        console.print(Panel.fit(registry.help_text(), border_style="green"))
        return

    # --- tools (needs runtime) --------------------------------------------
    if name == "tools":
        state.ensure_runtime()
        text = state.runtime.tools.describe() if state.runtime and state.runtime.tools else ""  # type: ignore[union-attr]
        console.print(Panel(text, title="Tools", border_style="green"))
        return

    # --- permissions ------------------------------------------------------
    if name == "permissions":
        console.print(
            Panel.fit(
                f"Current mode: [bold]{state.permission_mode}[/bold]\n"
                "Modes: default, plan, accept_edits, bypass",
                title="Permissions",
                border_style="green",
            )
        )
        return

    # --- plan / exit-plan -------------------------------------------------
    if name in ("plan", "exit-plan"):
        new_mode: PermissionMode = "plan" if name == "plan" else "default"
        state.permission_mode = new_mode
        if state.runtime is not None:
            state.runtime.set_permission_mode(new_mode)
            if state.session is not None:
                state.session.metadata["permission_mode"] = new_mode
        console.print(f"[green]Permission mode set to {new_mode}.[/green]")
        return

    # --- models ------------------------------------------------------------
    if name == "models":
        from ascend_agent.cli.models import handle_models_command
        handle_models_command(args, cm)
        state.refresh_from_config(cm)
        console.print(f"[green]Active model: [cyan]{state.model}[/cyan][/green]")
        return

    # --- sessions ----------------------------------------------------------
    if name == "sessions":
        sessions = list_sessions()
        if not sessions:
            console.print("[dim]No saved sessions.[/dim]")
            return
        table = Table(title="Saved Sessions")
        table.add_column("Thread ID", style="cyan")
        table.add_column("Messages", justify="right")
        table.add_column("First Message")
        table.add_column("Last Updated")
        for s in sessions:
            table.add_row(
                s["thread_id"][:12] + "...",
                str(s["message_count"]),
                s["first_message"],
                s["last_updated"][:19],
            )
        console.print(table)
        return

    # --- reset -------------------------------------------------------------
    if name == "reset":
        state.ensure_runtime()
        state.session = state.runtime.create_session()  # type: ignore[union-attr]
        console.print("[green]Session reset.[/green]")
        return

    # Unknown
    console.print(f"[red]Unknown command:[/red] /{name}")
