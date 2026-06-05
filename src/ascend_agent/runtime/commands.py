"""Typed slash-command registry for the runtime.

Replaces the ad-hoc if/elif dispatch in the REPL with a structured
registry that can be reused across CLI entry points.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

# Callable signature: handler(runtime, session, permission_mode, config_manager) -> optional str
CommandHandler = Callable[..., str | None]


@dataclass
class Command:
    """A REPL slash-command (e.g., /help, /models, /plan)."""

    name: str
    description: str
    category: str = "general"
    aliases: tuple[str, ...] = ()
    handler: CommandHandler | None = None
    # When True, the runtime does not need to be initialized before this
    # command can run (e.g., /help, /quit).
    needs_runtime: bool = True


class CommandRegistry:
    """Registry of slash-commands for the interactive REPL."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, cmd: Command) -> None:
        """Register a command, including all its aliases."""
        self._commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self._commands[alias] = cmd

    def find(self, name: str) -> Command | None:
        """Look up a command by name or alias, case-sensitive."""
        return self._commands.get(name)

    def list(self) -> list[Command]:
        """Return deduplicated list of registered commands."""
        seen: set[int] = set()
        result: list[Command] = []
        for cmd in self._commands.values():
            if id(cmd) not in seen:
                seen.add(id(cmd))
                result.append(cmd)
        return result

    def help_text(self) -> str:
        """Return formatted help text for all commands."""
        lines: list[str] = ["[bold]Commands[/bold]\n"]
        for cmd in sorted(self.list(), key=lambda c: c.name):
            aliases = f" ({', '.join(cmd.aliases)})" if cmd.aliases else ""
            lines.append(f"  [bold]/{cmd.name}{aliases}[/bold]  {cmd.description}")
        return "\n".join(lines)


def build_default_registry() -> CommandRegistry:
    """Build the registry with all built-in REPL commands.

    This function is separate from the class so that callers that need
    to customise the set of commands can start from an empty registry.
    """
    registry = CommandRegistry()

    # -- exit ---------------------------------------------------------------
    def _quit(runtime, session, permission_mode, cm):
        raise SystemExit(0)

    registry.register(
        Command(
            name="quit",
            description="Exit the REPL",
            category="general",
            aliases=("exit", "q"),
            handler=_quit,
            needs_runtime=False,
        )
    )

    # -- help ---------------------------------------------------------------
    def _help(runtime, session, permission_mode, cm):
        return registry.help_text()

    registry.register(
        Command(
            name="help",
            description="Show this help message",
            category="general",
            handler=_help,
            needs_runtime=False,
        )
    )

    # -- tools --------------------------------------------------------------
    def _tools(runtime, session, permission_mode, cm):
        if runtime.tools:
            return runtime.tools.describe()
        return "No tools registered."

    registry.register(
        Command(
            name="tools",
            description="List available runtime tools",
            category="info",
            handler=_tools,
        )
    )

    # -- permissions --------------------------------------------------------
    def _permissions(runtime, session, permission_mode, cm):
        return (
            f"Current mode: [bold]{permission_mode}[/bold]\n"
            "Modes: default, plan, accept_edits, bypass"
        )

    registry.register(
        Command(
            name="permissions",
            description="Show current permission mode",
            category="info",
            handler=_permissions,
        )
    )

    # -- plan ---------------------------------------------------------------
    def _plan(runtime, session, permission_mode, cm):
        new_mode: Any = "plan"
        runtime.set_permission_mode(new_mode)
        if session is not None:
            session.metadata["permission_mode"] = new_mode
        return ("plan", "[green]Permission mode set to plan.[/green]")

    registry.register(
        Command(
            name="plan",
            description="Enter read-only plan mode",
            category="permissions",
            handler=_plan,
        )
    )

    # -- exit-plan ----------------------------------------------------------
    def _exit_plan(runtime, session, permission_mode, cm):
        new_mode: Any = "default"
        runtime.set_permission_mode(new_mode)
        if session is not None:
            session.metadata["permission_mode"] = new_mode
        return ("exit-plan", "[green]Permission mode set to default.[/green]")

    registry.register(
        Command(
            name="exit-plan",
            description="Return to default permissions",
            category="permissions",
            handler=_exit_plan,
        )
    )

    # -- models -------------------------------------------------------------
    def _models(runtime, session, permission_mode, cm):
        from ascend_agent.cli.models import handle_models_command

        # The command string is everything including and after "models"
        # We reconstruct the args from the parsed command text
        return ("models", None)  # Special-cased in REPL loop

    registry.register(
        Command(
            name="models",
            description="Inspect or switch provider/model configuration",
            category="config",
            handler=_models,
        )
    )

    # -- reset --------------------------------------------------------------
    def _reset(runtime, session, permission_mode, cm):
        return ("reset", None)  # Special-cased in REPL loop

    registry.register(
        Command(
            name="reset",
            description="Start a new conversation session",
            category="general",
            handler=_reset,
        )
    )

    # -- sessions -----------------------------------------------------------
    def _sessions(runtime, session, permission_mode, cm):
        return ("sessions", None)

    registry.register(
        Command(
            name="sessions",
            description="List saved conversation sessions",
            category="general",
            handler=_sessions,
        )
    )

    # -- resume -------------------------------------------------------------
    def _resume(runtime, session, permission_mode, cm):
        return ("resume", None)

    registry.register(
        Command(
            name="resume",
            description="Resume a saved session by thread ID",
            category="general",
            handler=_resume,
        )
    )

    # -- delete-session -----------------------------------------------------
    def _delete_session(runtime, session, permission_mode, cm):
        return ("delete-session", None)

    registry.register(
        Command(
            name="delete-session",
            description="Delete a saved session by thread ID",
            category="general",
            handler=_delete_session,
        )
    )

    # -- clear --------------------------------------------------------------
    def _clear(runtime, session, permission_mode, cm):
        return ("clear", None)

    registry.register(
        Command(
            name="clear",
            description="Clear the terminal screen",
            category="general",
            handler=_clear,
            needs_runtime=False,
        )
    )

    # -- cd -----------------------------------------------------------------
    def _cd(runtime, session, permission_mode, cm):
        return ("cd", None)

    registry.register(
        Command(
            name="cd",
            description="Change the working directory",
            category="general",
            handler=_cd,
        )
    )

    # -- pwd ----------------------------------------------------------------
    def _pwd(runtime, session, permission_mode, cm):
        return ("pwd", None)

    registry.register(
        Command(
            name="pwd",
            description="Print the current working directory",
            category="info",
            handler=_pwd,
        )
    )

    # -- status -------------------------------------------------------------
    def _status(runtime, session, permission_mode, cm):
        return ("status", None)

    registry.register(
        Command(
            name="status",
            description="Show current session status and metadata",
            category="info",
            handler=_status,
        )
    )

    # -- bypass -------------------------------------------------------------
    def _bypass(runtime, session, permission_mode, cm):
        new_mode: Any = "bypass"
        runtime.set_permission_mode(new_mode)
        if session is not None:
            session.metadata["permission_mode"] = new_mode
        return ("bypass", "[green]Permission mode set to bypass.[/green]")

    registry.register(
        Command(
            name="bypass",
            description="Switch to bypass mode (all tools auto-allowed)",
            category="permissions",
            handler=_bypass,
        )
    )

    # -- accept-edits -------------------------------------------------------
    def _accept_edits(runtime, session, permission_mode, cm):
        new_mode: Any = "accept_edits"
        runtime.set_permission_mode(new_mode)
        if session is not None:
            session.metadata["permission_mode"] = new_mode
        return ("accept-edits", "[green]Permission mode set to accept_edits.[/green]")

    registry.register(
        Command(
            name="accept-edits",
            description="Switch to accept_edits mode (auto-approve file edits)",
            category="permissions",
            handler=_accept_edits,
        )
    )

    return registry
