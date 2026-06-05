from __future__ import annotations

import asyncio
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import (
    Completer,
    Completion,
    PathCompleter,
    merge_completers,
)
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
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
from ascend_agent.runtime.permissions import PermissionContext, PermissionRule
from ascend_agent.runtime.session import _sessions_dir

console = Console()

# ---------------------------------------------------------------------------
# Slash-command completer (driven by the command registry)
# ---------------------------------------------------------------------------


class SlashCompleter(Completer):
    """Tab-complete slash commands at the start of the input line.

    The completion list is built from the command registry so that new
    commands added to ``build_default_registry()`` automatically appear.
    """

    def get_completions(self, document: Any, complete_event: Any) -> Any:
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        word = document.get_word_before_cursor(WORD=True)
        for cmd in _slash_commands():
            if cmd.startswith(word):
                yield Completion(cmd, start_position=-len(word))


def _slash_commands() -> list[str]:
    """Return sorted, deduplicated slash-command names with leading ``/``."""
    registry = build_default_registry()
    seen: set[str] = set()
    result: list[str] = []
    for cmd in registry.list():
        for name in (cmd.name,) + cmd.aliases:
            full = f"/{name}"
            if full not in seen:
                seen.add(full)
                result.append(full)
    result.sort()
    return result


def _build_completer() -> Completer:
    """Merge slash-command and filesystem-path completers."""
    return merge_completers(
        [
            SlashCompleter(),
            PathCompleter(only_directories=False, expanduser=True),
        ]
    )


# ---------------------------------------------------------------------------
# Key bindings
# ---------------------------------------------------------------------------


def _make_key_bindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add(Keys.ControlD, eager=True)
    def _(event: Any) -> None:
        """Ctrl+D exits the REPL."""
        event.app.exit(exception=EOFError("exit"))

    @kb.add(Keys.ControlL, eager=True)
    def _(event: Any) -> None:
        """Ctrl+L clears the screen."""
        event.app.renderer.clear()
        # Redraw by triggering a forced refresh
        event.app.invalidate()

    @kb.add(Keys.Escape, Keys.ControlM, eager=True)
    def _(event: Any) -> None:
        """Alt+Enter inserts a literal newline for multi-line input."""
        event.app.current_buffer.insert_text("\n")

    return kb


# ---------------------------------------------------------------------------
# prompt_toolkit style
# ---------------------------------------------------------------------------

_PROMPT_STYLE = Style.from_dict(
    {
        "mode": "bold ansicyan",
        "model": "ansigreen",
        "path": "ansiyellow",
        "prompt": "bold",
    }
)

# ---------------------------------------------------------------------------
# Confirmation handler (async — uses prompt_toolkit for arrow-key selection)
# ---------------------------------------------------------------------------


def _make_confirm_handler(state: "ReplState") -> Any:
    """Return an async callable that shows an interactive confirmation prompt.

    The user can navigate options with arrow keys or press a hotkey:
      - ``y`` / Enter on *Allow once*  → run this one time
      - ``a`` / Enter on *Always allow this tool*  → auto-allow all future
        calls to this tool (adds a ``PermissionRule``)
      - ``c`` / Enter on *Always allow this command*  → auto-allow this
        exact command (adds a ``PermissionRule`` with a regex pattern)
      - ``n`` / Ctrl+C  → deny
    """

    async def confirm_tool(name: str, arguments: dict[str, Any]) -> bool:
        cmd = arguments.get("command", "")
        if cmd:
            detail = cmd[:120]
        elif arguments:
            for key in ("file_path", "pattern", "diagnosis_json", "reproduction_json"):
                val = arguments.get(key)
                if val:
                    detail = f"{key}={str(val)[:100]}"
                    break
            else:
                detail = str(arguments)[:120]
        else:
            detail = "(no arguments)"

        # Run the prompt_toolkit UI in a thread so it doesn't conflict with
        # the asyncio event loop.  prompt_toolkit's sync ``prompt()`` creates
        # its own temporary event loop for terminal I/O.
        loop = asyncio.get_running_loop()
        choice = await loop.run_in_executor(
            None, _sync_confirm_ui, name, detail, bool(cmd)
        )
        # --- apply "always allow" rules ------------------------------------
        if choice in ("a", "c") and state.runtime is not None:
            perms = state.runtime.tools.permissions  # type: ignore[union-attr]
            if isinstance(perms, PermissionContext):
                if choice == "a":
                    rule = PermissionRule(action="allow", tool=name)
                else:
                    rule = PermissionRule(
                        action="allow",
                        tool=name,
                        command_pattern=re.escape(cmd),
                    )
                perms.rules.append(rule)
                console.print(
                    f"[dim]Added rule: always allow [bold]{name}[/bold]"
                    + (f" with pattern '{cmd[:60]}'" if choice == "c" else "")
                    + "[/dim]"
                )
        return choice in ("y", "a", "c")

    return confirm_tool


def _sync_confirm_ui(name: str, detail: str, has_command: bool) -> str:
    """Show an arrow-key navigable confirmation prompt (blocking).

    Runs in a thread via ``run_in_executor`` so it doesn't block the
    asyncio event loop.  Uses prompt_toolkit's synchronous ``prompt()``.

    Returns one of ``"y"``, ``"n"``, ``"a"`` (always allow tool),
    or ``"c"`` (always allow this command).
    """
    from prompt_toolkit.shortcuts import prompt as pt_prompt

    options: list[tuple[str, str]] = [
        ("n", "Deny"),
        ("y", "Allow once"),
    ]
    if has_command:
        options.append(("c", "Always allow this command"))
    options.append(("a", "Always allow this tool"))

    selected = [0]  # mutable so nested closures can mutate it

    kb = KeyBindings()

    # --- navigation --------------------------------------------------------
    @kb.add(Keys.Left, eager=True)
    def _nav_left(event: Any) -> None:
        selected[0] = max(0, selected[0] - 1)

    @kb.add(Keys.Right, eager=True)
    def _nav_right(event: Any) -> None:
        selected[0] = min(len(options) - 1, selected[0] + 1)

    # --- hotkeys (one per option) ------------------------------------------
    for idx, (key_char, _label) in enumerate(options):
        _add_hotkey(kb, idx, key_char, selected)

    # --- Enter confirms current selection ----------------------------------
    @kb.add(Keys.Enter, eager=True)
    def _on_enter(event: Any) -> None:
        event.app.exit(result=options[selected[0]][0])

    # --- Ctrl+C = deny -----------------------------------------------------
    @kb.add(Keys.ControlC, eager=True)
    def _on_ctrl_c(event: Any) -> None:
        event.app.exit(result="n")

    # --- dynamic toolbar ---------------------------------------------------
    def _toolbar() -> str:
        parts: list[str] = []
        for i, (_key, label) in enumerate(options):
            if i == selected[0]:
                parts.append(f"[> {label} <]")
            else:
                parts.append(f"  {label}  ")
        return "  " + "  │  ".join(parts) + "  "

    try:
        choice = pt_prompt(
            f"\n  ⏳ {name} wants to run:\n    {detail}\n",
            key_bindings=kb,
            bottom_toolbar=_toolbar,
            default="",
        )
    except (EOFError, KeyboardInterrupt):
        return "n"
    return choice or "n"


def _add_hotkey(
    kb: KeyBindings,
    idx: int,
    key_char: str,
    selected: list[int],
) -> None:
    """Register a hotkey that selects option *idx* and exits the prompt.

    Uses a factory function so *idx* and *key_char* are captured by value
    (via default arguments), avoiding late-binding closure bugs.
    """

    def _make_handler(i: int, k: str):
        @kb.add(k, eager=True)
        @kb.add(k.upper(), eager=True)
        def _handler(event: Any) -> None:
            selected[0] = i
            event.app.exit(result=k)

    _make_handler(idx, key_char)


# ---------------------------------------------------------------------------
# Dynamic prompt (status line)
# ---------------------------------------------------------------------------


def _get_prompt(state: "ReplState") -> list[tuple[str, str]]:
    """Build a prompt_toolkit-style prompt with inline status.

    Format: ``[mode] model cwd > ``
    """
    mode_abbrev = state.permission_mode[:4]  # defa, plan, acce, bypa
    model_short = (state.model or "?")[:25]
    if state.runtime is not None:
        wd = state.runtime.working_dir
    else:
        wd = Path.cwd()
    try:
        wd_short = wd.resolve().name
    except Exception:
        wd_short = str(wd)

    return [
        ("class:mode", f"[{mode_abbrev}] "),
        ("class:model", f"{model_short} "),
        ("class:path", f"{wd_short}"),
        ("class:prompt", " > "),
    ]


# ---------------------------------------------------------------------------
# REPL state
# ---------------------------------------------------------------------------


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
            self.runtime.set_confirmation_handler(_make_confirm_handler(self))
        if self.session is None:
            self.session = self.runtime.create_session()
        return self.runtime, self.session

    def refresh_from_config(self, cm: ConfigManager) -> None:
        self.provider = cm.get_active()
        self.model = cm.get_active_model()
        self.runtime = None
        self.session = None


# ---------------------------------------------------------------------------
# prompt_toolkit session (shared across the REPL loop)
# ---------------------------------------------------------------------------


def _create_prompt_session() -> PromptSession:
    history_path = Path.home() / ".ascend_agent_history"
    history: FileHistory | None
    try:
        history = FileHistory(str(history_path))
    except Exception:
        history = None

    return PromptSession(
        completer=_build_completer(),
        history=history,
        key_bindings=_make_key_bindings(),
        style=_PROMPT_STYLE,
        multiline=False,
        wrap_lines=True,
        enable_history_search=True,
    )


# ---------------------------------------------------------------------------
# Main REPL loop
# ---------------------------------------------------------------------------


def run_repl(provider: str = "", resume: str | None = None) -> None:
    """Run a runtime-backed interactive session with streaming output."""
    cm = ConfigManager()
    state = ReplState(
        provider=provider or cm.get_active(),
        model=cm.get_active_model(),
    )

    if resume:
        try:
            state.session = Session.load(resume)
            state.provider = state.session.provider
            state.model = state.session.model
            console.print(
                f"[green]Resumed session [bold]{resume[:12]}...[/bold][/green]"
            )
        except FileNotFoundError:
            console.print(f"[red]Session {resume[:12]}... not found.[/red]")

    _print_banner(state)

    pt_session = _create_prompt_session()

    while True:
        try:
            raw = pt_session.prompt(_get_prompt(state)).strip()
        except KeyboardInterrupt:
            console.print("^C")
            continue
        except (EOFError, SystemExit):
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

        try:
            asyncio.run(_stream_turn(state, raw))
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
            continue
        except Exception as exc:
            console.print(f"[red]Agent turn failed:[/red] {exc}")
            continue

        if state.auto_save and state.session is not None:
            try:
                state.session.save()
            except Exception:
                pass


def _print_banner(state: ReplState) -> None:
    """Print the welcome banner (also used by /clear)."""
    console.print(
        Panel.fit(
            "[bold]Ascend Agent[/bold]\n"
            "Type [bold]/help[/bold] for commands, [bold]Tab[/bold] to complete, "
            "[bold]Ctrl+L[/bold] to clear, [bold]Ctrl+C[/bold] to interrupt, "
            "[bold]Ctrl+D[/bold] to exit.\n"
            f"Active model: [cyan]{state.model}[/cyan]",
            border_style="cyan",
        )
    )


async def _stream_turn(state: ReplState, user_input: str) -> None:
    """Run one agent turn with streaming output + Markdown rendering."""
    rt = state.runtime
    if rt is None:
        return

    first_content = True
    async for event_type, payload in rt.run_turn(state.session, user_input):  # type: ignore[arg-type]
        if event_type == "user_message":
            pass
        elif event_type in ("assistant_message", "final"):
            if payload:
                if first_content:
                    console.print()
                    first_content = False
                console.print(Markdown(str(payload)))
            if event_type == "final":
                console.print()
        elif event_type == "tool_call":
            name = (
                payload.get("name", "unknown")
                if isinstance(payload, dict)
                else str(payload)
            )
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


# ---------------------------------------------------------------------------
# Slash-command dispatch
# ---------------------------------------------------------------------------


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
        text = (
            state.runtime.tools.describe()
            if state.runtime and state.runtime.tools
            else ""
        )  # type: ignore[union-attr]
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

    # --- bypass ------------------------------------------------------------
    if name == "bypass":
        state.permission_mode = "bypass"
        if state.runtime is not None:
            state.runtime.set_permission_mode("bypass")
            if state.session is not None:
                state.session.metadata["permission_mode"] = "bypass"
        console.print("[green]Permission mode set to bypass.[/green]")
        return

    # --- accept-edits ------------------------------------------------------
    if name == "accept-edits":
        state.permission_mode = "accept_edits"
        if state.runtime is not None:
            state.runtime.set_permission_mode("accept_edits")
            if state.session is not None:
                state.session.metadata["permission_mode"] = "accept_edits"
        console.print("[green]Permission mode set to accept_edits.[/green]")
        return

    # --- models ------------------------------------------------------------
    if name == "models":
        from ascend_agent.cli.models import handle_models_command

        handle_models_command(args, cm)
        state.refresh_from_config(cm)
        console.print(
            f"[green]Active model: [cyan]{state.model}[/cyan][/green]"
        )
        return

    # --- sessions ----------------------------------------------------------
    if name == "sessions":
        _print_sessions()
        return

    # --- resume ------------------------------------------------------------
    if name == "resume":
        if not args:
            console.print("[red]Usage: /resume <thread_id>[/red]")
            return
        thread_id = args[0]
        try:
            state.session = Session.load(thread_id)
            state.provider = state.session.provider
            state.model = state.session.model
            state.runtime = Runtime.create(
                provider=state.provider,
                working_dir=state.session.working_dir,
                permission_mode=state.permission_mode,
                model=state.model,
            )
            state.runtime.set_confirmation_handler(_make_confirm_handler(state))
            console.print(
                f"[green]Resumed session [bold]{thread_id[:12]}...[/bold][/green]"
            )
        except FileNotFoundError:
            console.print(
                f"[red]Session {thread_id[:12]}... not found.[/red]"
            )
        return

    # --- delete-session ----------------------------------------------------
    if name == "delete-session":
        if not args:
            console.print("[red]Usage: /delete-session <thread_id>[/red]")
            return
        thread_id = args[0]
        filepath = _sessions_dir() / f"{thread_id}.jsonl"
        if filepath.exists():
            filepath.unlink()
            console.print(
                f"[green]Deleted session [bold]{thread_id[:12]}...[/bold][/green]"
            )
        else:
            console.print(
                f"[red]Session {thread_id[:12]}... not found.[/red]"
            )
        return

    # --- reset -------------------------------------------------------------
    if name == "reset":
        state.ensure_runtime()
        state.session = state.runtime.create_session()  # type: ignore[union-attr]
        console.print("[green]Session reset.[/green]")
        return

    # --- clear -------------------------------------------------------------
    if name == "clear":
        # Clear terminal and reprint banner
        console.clear()
        _print_banner(state)
        return

    # --- pwd ---------------------------------------------------------------
    if name == "pwd":
        wd = state.runtime.working_dir if state.runtime else Path.cwd()
        console.print(str(wd.resolve()))
        return

    # --- cd ----------------------------------------------------------------
    if name == "cd":
        if not args:
            # Show current directory
            wd = state.runtime.working_dir if state.runtime else Path.cwd()
            console.print(str(wd.resolve()))
            return
        target = Path(args[0]).expanduser().resolve()
        if not target.is_dir():
            console.print(f"[red]Not a directory: {target}[/red]")
            return
        # Recreate runtime with the new working directory
        state.runtime = None
        state.session = None
        # Override working_dir for next ensure_runtime()
        _set_cwd(target)
        state.ensure_runtime()
        console.print(f"[green]Working directory: {target}[/green]")
        return

    # --- status ------------------------------------------------------------
    if name == "status":
        state.ensure_runtime()
        rt = state.runtime
        s = state.session
        msg_count = len(s.messages) if s else 0
        thread_id = s.thread_id if s else "—"
        created = ""
        if s and s.transcript:
            created = s.transcript[0].get("timestamp", "")[:19]
        info = (
            f"[bold]Model:[/bold]        {state.model or '?'}\n"
            f"[bold]Provider:[/bold]     {state.provider}\n"
            f"[bold]Permission:[/bold]   {state.permission_mode}\n"
            f"[bold]Working dir:[/bold]  {rt.working_dir if rt else Path.cwd()}\n"
            f"[bold]Thread ID:[/bold]    {thread_id}\n"
            f"[bold]Messages:[/bold]     {msg_count}\n"
            f"[bold]Created:[/bold]      {created or '—'}"
        )
        console.print(Panel.fit(info, title="Session Status", border_style="green"))
        return

    # Unknown
    console.print(f"[red]Unknown command:[/red] /{name}")


def _print_sessions() -> None:
    """Print the saved-sessions table (shared by /sessions and direct call)."""
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


def _set_cwd(path: Path) -> None:
    """Change the process working directory (best-effort)."""
    try:
        import os

        os.chdir(path)
    except Exception:
        pass
