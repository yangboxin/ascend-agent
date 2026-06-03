"""Main TUI Application — full-screen immersive terminal interface.

Wires together all components into a Claude Code-like experience:
- Alternate screen buffer (full-screen mode)
- Fixed-bottom input bar
- Scrollable content area
- Status line
- Keyboard shortcuts
- Streaming response support

Architecture:
  HSplit
  ├── StatusLine window     (height=1, top)
  ├── ContentArea window    (flex_weight=1, scrollable)
  ├── Separator line        (height=1, "───")
  └── InputBar window       (height=3, bottom)
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
import signal
import shlex
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

from prompt_toolkit import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion, CompleteEvent, PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    Layout,
    HSplit,
    VSplit,
    Window,
    Dimension,
    FloatContainer,
    Float,
)
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style
from prompt_toolkit.mouse_events import MouseEventType, MouseEvent

from ascend_agent.cli.tui.hooks.use_command_history import CommandHistory
from ascend_agent.cli.tui.hooks.use_streaming import StreamingManager, StreamBuffer
from ascend_agent.cli.tui.hooks.use_terminal_size import get_terminal_size_watcher
from ascend_agent.cli.tui.components.message_bubble import Message, format_messages
from ascend_agent.cli.tui.components.status_line import StatusLine
from ascend_agent.cli.tui.utils.terminal import (
    enter_alternate_screen,
    exit_alternate_screen,
)
from ascend_agent.context.models import ContextDocument
from ascend_agent.diagnosis.models import (
    DiagnosisOutput,
    DiagnosisResult,
    FixGenerationResult,
    ReproductionResult,
    VerificationResult,
)


SLASH_COMMANDS: tuple[tuple[str, str], ...] = (
    ("/models", "Open model selector"),
    ("/models list", "List model IDs"),
    ("/models status", "Show active model and credential hints"),
    ("/models use ", "Select a model by provider/model"),
    ("/diagnose ", "Diagnose a repo: /diagnose <repo> --trace-text '...'"),
    ("/fix", "Generate fixes from the last diagnosis"),
    ("/fix apply", "Apply generated fixes"),
    ("/reproduce", "Reproduce the last diagnosis"),
    ("/verify", "Verify the last reproduction"),
    ("/chat ", "Send a chat message"),
    ("/clear", "Clear the screen"),
    ("/reset-chat", "Clear chat history"),
    ("/help", "Show command help"),
    ("/quit", "Exit the session"),
)


class SlashCommandCompleter(Completer):
    """Claude-style slash command and path completions for the TUI input buffer."""

    def __init__(self) -> None:
        self._path_completer = PathCompleter(expanduser=True)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return

        if " " not in text:
            for command, description in SLASH_COMMANDS:
                if " " in command.strip():
                    continue
                if command.startswith(text):
                    yield Completion(
                        command + (" " if command not in ("/help", "/quit", "/reset-chat") else ""),
                        start_position=-len(text),
                        display=command,
                        display_meta=description,
                    )
            return

        if text.startswith("/models use "):
            prefix = text.removeprefix("/models use ")
            for model_id in _available_model_ids():
                if model_id.startswith(prefix):
                    yield Completion(
                        model_id,
                        start_position=-len(prefix),
                        display=model_id,
                        display_meta="Select model",
                    )
            return

        first, remainder = text.split(" ", 1)
        prefix = f"{first} {remainder}"
        matched_command = False
        for command, description in SLASH_COMMANDS:
            if command.startswith(prefix) and command != prefix:
                matched_command = True
                yield Completion(
                    command,
                    start_position=-len(prefix),
                    display=command,
                    display_meta=description,
                )
        if matched_command:
            return

        yield from self._path_completions(text)

    def _path_completions(self, text: str):
        """Complete the current whitespace-delimited argument as a path."""
        if text.startswith("/models "):
            return
        current = "" if text[-1].isspace() else text.rsplit(maxsplit=1)[-1]
        if current.startswith("--"):
            return
        path_document = Document(current, len(current))
        yield from self._path_completer.get_completions(path_document, CompleteEvent(completion_requested=True))


def _available_model_ids() -> list[str]:
    try:
        from ascend_agent.cli.config_manager import ConfigManager
        from ascend_agent.cli.model_catalog import PROVIDER_PRESETS, full_model_id

        result = []
        for provider in ConfigManager().list_providers():
            preset = PROVIDER_PRESETS.get(provider.name)
            models = list(preset.models) if preset else [provider.default_model]
            result.extend(full_model_id(provider.name, model) for model in models)
        return result
    except Exception:
        return []


# ---- Style Definition ----

TUI_STYLE = Style.from_dict({
    # Content area
    "content": "fg:#839496 bg:default",
    # Input area
    "input": "fg:#93a1a1 bg:#002b36",
    "input.border": "fg:#586e75",
    "input.prompt": "fg:#268bd2 bold",
    # Status bar
    "status": "bg:#073642 fg:#839496",
    "status.brand": "bg:#073642 fg:#b58900 bold",
    "status.key": "bg:#073642 fg:#586e75",
    # Messages
    "user.prompt": "fg:#859900 bold",
    "assistant.prompt": "fg:#268bd2 bold",
    "system": "fg:#b58900 italic",
    # Separator
    "separator": "fg:#586e75",
})


# ---- Separator Component ----

def _create_separator(width: int = 80) -> Window:
    """Create a horizontal separator line between content and input."""
    def get_text():
        cols = get_app().output.get_size().columns if get_app().output else width
        return FormattedText([("class:separator", "─" * cols)])
    return Window(
        content=FormattedTextControl(text=get_text),
        height=1,
        style="class:separator",
    )


# ---- Main App Class ----

class AscendTUI:
    """Immersive terminal application for Ascend Agent.

    Usage:
        tui = AscendTUI(provider="openai", model="claude-sonnet-4-6")
        tui.run()

    The application takes over the terminal (alternate screen buffer),
    shows a full-screen layout with scrollable messages and a fixed
    bottom input bar. Exit with Ctrl+D or /quit.
    """

    def __init__(
        self,
        provider: str = "",
        model: str = "",
        history_file: str | None = None,
        max_messages: int = 1000,
    ) -> None:
        # --- State ---
        self._provider = provider
        self._model = model
        self._messages: list[Message] = []
        self._max_messages = max_messages
        self._running = False
        self._interrupted = False
        self._model_picker_active = False
        self._model_choices: list[tuple[str, str, bool]] = []
        self._model_picker_index = 0
        self._last_diagnosis: DiagnosisOutput | None = None
        self._last_fixes: FixGenerationResult | None = None
        self._last_reproduction: ReproductionResult | None = None
        self._last_verification: VerificationResult | None = None
        self._working_message_id: str | None = None
        self._task_running = False

        # --- Hooks / Managers ---
        self._history = CommandHistory(history_file=history_file)
        self._status = StatusLine()
        self._status.set_provider(provider)
        self._status.set_model(model)
        self._stream_buffer = StreamBuffer()

        # --- Streaming callback ---
        self._on_stream_chunk: Optional[Callable] = None
        self._on_stream_done: Optional[Callable] = None
        self._streaming_manager: Optional[StreamingManager] = None

        # --- Layout will be built in _build_app ---
        self._app: Optional[Application] = None

    # ==================================================================
    # Public API
    # ==================================================================

    def run(self) -> None:
        """Run the TUI application (blocking)."""
        self._build_app()
        self._running = True
        try:
            self._app.run()
        finally:
            self._running = False
            self._history.save()

    async def run_async(self) -> None:
        """Run the TUI application (async, for use within an event loop)."""
        self._build_app()
        self._running = True
        try:
            await self._app.run_async()
        finally:
            self._running = False
            self._history.save()

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation and refresh the UI."""
        self._messages.append(message)
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages:]
        self._invalidate()

    def add_user_message(self, text: str) -> None:
        """Add a user message."""
        self.add_message(Message(role="user", content=text))

    def add_assistant_message(self, text: str) -> None:
        """Add a complete assistant message."""
        self.add_message(Message(role="assistant", content=text))

    def append_to_assistant(self, chunk: str) -> None:
        """Append text to the last assistant message (streaming)."""
        if self._messages and self._messages[-1].is_assistant:
            self._messages[-1].content += chunk
        else:
            self._messages.append(Message(role="assistant", content=chunk))
        self._invalidate()

    def update_last_assistant(self, content: str) -> None:
        """Replace the content of the last assistant message."""
        if self._messages and self._messages[-1].is_assistant:
            self._messages[-1].content = content
        else:
            self._messages.append(Message(role="assistant", content=content))
        self._invalidate()

    def clear_messages(self) -> None:
        """Clear all messages."""
        self._messages.clear()
        self._invalidate()

    def set_status(self, provider: str = "", model: str = "",
                   streaming: bool = False, tokens: int = 0) -> None:
        """Update the status line."""
        if provider:
            self._status.set_provider(provider)
        if model:
            self._status.set_model(model)
        self._status.set_streaming(streaming)
        if tokens:
            self._status.set_token_count(tokens)
        self._invalidate()

    def request_interrupt(self) -> None:
        """Request interruption of the current operation."""
        self._interrupted = True
        if self._streaming_manager:
            self._streaming_manager.request_interrupt()

    # ==================================================================
    # Streaming Support
    # ==================================================================

    def start_stream(self) -> tuple[StreamingManager, StreamBuffer]:
        """Start a streaming response context.

        Returns:
            (StreamingManager, StreamBuffer) for the caller to feed
            chunks into and manage.
        """
        self._stream_buffer.reset()
        self._interrupted = False

        self._streaming_manager = StreamingManager(
            on_chunk=lambda text: self._handle_stream_chunk(text),
            on_complete=lambda: self._handle_stream_complete(),
            on_error=lambda e: self._handle_stream_error(e),
        )
        return self._streaming_manager, self._stream_buffer

    async def stream_response(self, stream_generator) -> None:
        """Stream an AI response through the TUI.

        Args:
            stream_generator: An async generator yielding string chunks,
                              or an async callable that returns chunks.
        """
        if not self._streaming_manager:
            self._streaming_manager, _ = self.start_stream()

        await self._streaming_manager.consume(stream_generator)

    # ==================================================================
    # Internal: Build Application
    # ==================================================================

    def _build_app(self) -> None:
        """Construct the prompt_toolkit Application with all layout and bindings."""

        # --- Input Buffer ---
        self._input_buffer = Buffer(
            completer=SlashCommandCompleter(),
            complete_while_typing=Condition(lambda: self._input_buffer.text.startswith("/")),
            multiline=True,
            accept_handler=self._handle_input_accept,
            name="ascend_input",
        )

        # --- Content Text ---
        def get_content_text():
            if self._model_picker_active:
                return FormattedText(self._render_model_picker())
            if not self._messages:
                return FormattedText([
                    ("class:content", ""),
                    ("fg:#586e75", ""),
                    ("fg:#839496", "Welcome to Ascend Agent TUI.\n"),
                    ("fg:#657b83 dim", ""),
                    ("fg:#657b83 dim", "Type a message or /help for commands.\n"),
                    ("fg:#657b83 dim", "Enter send  Ctrl+J newline  Ctrl+C interrupt  Ctrl+D quit.\n"),
                    ("", ""),
                ])
            return format_messages(self._messages)

        # --- Layout ---
        content_window = Window(
            content=FormattedTextControl(
                text=lambda: get_content_text(),
                focusable=False,
            ),
            wrap_lines=True,
            allow_scroll_beyond_bottom=True,
            cursorline=False,
            always_hide_cursor=True,
        )

        input_window = Window(
            content=BufferControl(
                buffer=self._input_buffer,
                input_processors=[BeforeInput("> ")],
            ),
            height=3,
            wrap_lines=True,
            cursorline=True,
            style="class:input",
        )

        status_window = self._status.create_window()

        root_container = HSplit([
            # Status bar at top
            status_window,
            # Scrollable content area (takes remaining space)
            content_window,
            # Separator between content and input
            _create_separator(),
            # Fixed bottom input
            input_window,
        ])

        root_container = FloatContainer(
            content=root_container,
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(max_height=8, scroll_offset=1),
                )
            ],
        )

        # --- Key Bindings ---
        kb = self._build_keybindings()

        # --- Application ---
        self._app = Application(
            layout=Layout(root_container),
            key_bindings=kb,
            style=TUI_STYLE,
            full_screen=True,         # Alternate screen buffer
            mouse_support=True,       # Mouse click, selection
            enable_page_navigation_bindings=True,
        )

    def _build_keybindings(self) -> KeyBindings:
        """Create all keyboard shortcuts."""
        kb = KeyBindings()

        @kb.add(Keys.ControlC)
        def _interrupt(event):
            """Ctrl+C: interrupt current operation, don't exit."""
            if self._model_picker_active:
                self._model_picker_active = False
                self._invalidate()
                return
            self._interrupted = True
            if self._streaming_manager:
                self._streaming_manager.request_interrupt()

        @kb.add("enter", eager=True)
        def _enter(event):
            """Enter: select completion/model item or submit input."""
            if self._model_picker_active:
                self._select_highlighted_model()
                return
            complete_state = self._input_buffer.complete_state
            if complete_state and complete_state.current_completion:
                self._apply_completion(complete_state.current_completion)
                return
            if self._slash_completion_active() and len(complete_state.completions) == 1:
                self._apply_completion(complete_state.completions[0])
                return
            self._input_buffer.validate_and_handle()

        @kb.add(Keys.ControlD)
        def _quit(event):
            """Ctrl+D: quit the application."""
            event.app.exit()

        @kb.add("c-j")
        def _insert_newline(event):
            """Ctrl+J: insert a newline without submitting."""
            self._input_buffer.insert_text("\n")

        @kb.add("tab", eager=True)
        def _tab_complete(event):
            """Tab: open or accept command/path completion."""
            complete_state = self._input_buffer.complete_state
            if complete_state and complete_state.current_completion:
                self._apply_completion(complete_state.current_completion)
                return
            try:
                self._input_buffer.start_completion(select_first=True)
            except RuntimeError:
                self._refresh_slash_completions(select_first=True)

        @kb.add(Keys.ControlL)
        def _clear_screen(event):
            """Ctrl+L: clear messages."""
            self.clear_messages()

        @kb.add("/", eager=True)
        def _slash(event):
            """Slash: insert and open the command completion menu."""
            self._input_buffer.insert_text("/")
            try:
                self._input_buffer.start_completion(select_first=False)
            except RuntimeError:
                self._refresh_slash_completions()

        @kb.add(Keys.Escape, eager=True)
        def _cancel(event):
            """Escape: cancel current operation."""
            if self._model_picker_active:
                self._model_picker_active = False
                self._invalidate()
                return
            if self._input_buffer.complete_state:
                self._input_buffer.cancel_completion()
                return
            self._interrupted = True
            if self._streaming_manager:
                self._streaming_manager.request_interrupt()

        @kb.add("up", eager=True)
        def _history_up(event):
            """Up arrow: completion menu first, otherwise history/model picker."""
            if self._model_picker_active:
                self._model_picker_index = max(0, self._model_picker_index - 1)
                self._invalidate()
                return
            if self._slash_completion_active():
                self._input_buffer.complete_previous()
                return
            current = self._input_buffer.text
            result = self._history.navigate_up(current)
            if result is not None:
                self._input_buffer.text = result
                self._input_buffer.cursor_position = len(result)

        @kb.add("down", eager=True)
        def _history_down(event):
            """Down arrow: completion menu first, otherwise history/model picker."""
            if self._model_picker_active:
                self._model_picker_index = min(
                    len(self._model_choices) - 1,
                    self._model_picker_index + 1,
                )
                self._invalidate()
                return
            if self._slash_completion_active():
                self._input_buffer.complete_next()
                return
            result = self._history.navigate_down()
            if result is not None:
                self._input_buffer.text = result
                self._input_buffer.cursor_position = len(result)

        return kb

    # ==================================================================
    # Internal: Handlers
    # ==================================================================

    def _handle_input_accept(self, buffer: Buffer) -> bool:
        """Called when user presses Enter to submit input.

        Returns:
            True to keep the buffer text, False to clear it.
        """
        text = buffer.text.strip()
        if not text:
            return False  # Clear empty input

        # Add to history
        self._history.add(text)

        # Handle slash commands
        if text.startswith("/"):
            self.add_user_message(text)
            self._handle_slash_command(text)
            return False  # Clear

        # Regular message
        self._handle_text_input(text)
        return False  # Clear

    def _handle_slash_command(self, text: str) -> None:
        """Process slash commands like /quit, /help, /models, etc."""
        try:
            parts = shlex.split(text)
        except ValueError as exc:
            self.add_message(Message(role="system", content=f"Command parse error: {exc}"))
            return
        cmd = parts[0].lstrip("/").lower()
        args = parts[1:]

        if cmd in ("quit", "exit", "q"):
            if self._app:
                self._app.exit()
            return

        elif cmd == "help":
            help_text = (
                "Available Commands\n\n"
                "  /models                    Open model selector\n"
                "  /models list|status        Show model information\n"
                "  /models use <provider/model>\n"
                "  /diagnose <repo> [--trace file | --trace-text 'text'] [--output file]\n"
                "  /fix [diagnosis.json] [--output file]\n"
                "  /fix apply [--output file]\n"
                "  /reproduce [diagnosis.json] [--output file]\n"
                "  /verify [reproduction.json] [--output file]\n"
                "  /chat <message>            Chat with the active LLM provider\n"
                "  /clear                     Clear the screen\n"
                "  /reset-chat                Clear chat history\n"
                "  /help                      Show this help\n"
                "  /quit                      Exit the session\n\n"
                "Keyboard shortcuts:\n"
                "  Enter   Send message or command\n"
                "  Ctrl+J  Insert newline in the input\n"
                "  Ctrl+C  Interrupt current operation\n"
                "  Ctrl+D  Quit application\n"
                "  Ctrl+L  Clear screen\n"
                "  ↑/↓     Browse command history\n"
                "  Esc     Cancel current operation"
            )
            self.add_message(Message(role="system", content=help_text))

        elif cmd in ("clear", "cls"):
            self.clear_messages()

        elif cmd == "reset-chat":
            self.clear_messages()
            self.add_message(Message(role="system", content=" Chat history cleared."))

        elif cmd == "models":
            self._handle_models_command(args)

        elif cmd == "diagnose":
            self._run_diagnose_command(args)

        elif cmd == "fix":
            self._run_fix_command(args)

        elif cmd == "reproduce":
            self._run_reproduce_command(args)

        elif cmd == "verify":
            self._run_verify_command(args)

        elif cmd == "chat":
            message = " ".join(args).strip()
            if not message:
                self.add_message(Message(role="system", content="Usage: /chat <message>"))
            else:
                self._handle_text_input(message)

        else:
            self.add_message(Message(
                role="system",
                content=f"[red]Unknown command:[/red] /{cmd}\n"
                        f"  Type [bold]/help[/bold] for available commands."
            ))

    def _handle_text_input(self, text: str) -> None:
        """Handle a regular (non-slash) text input as a user message."""
        self.add_user_message(text)
        if self._on_user_input_callback:
            self._show_working_message()

            def run_callback() -> None:
                try:
                    self._on_user_input_callback(text)
                except Exception as exc:
                    self.add_message(Message(role="system", content=f"[red]Error:[/red] {exc}"))
                finally:
                    self._clear_working_message()
                    self.set_status(streaming=False)

            self.set_status(streaming=True)
            threading.Thread(target=run_callback, daemon=True).start()

    def _handle_stream_chunk(self, text: str) -> None:
        """Called for each chunk of streaming response."""
        self._clear_working_message()
        self.append_to_assistant(text)

    def _handle_stream_complete(self) -> None:
        """Called when streaming is complete."""
        self._status.set_streaming(False)
        self._invalidate()

    def _handle_stream_error(self, error: Exception) -> None:
        """Called when streaming encounters an error."""
        self._status.set_streaming(False)
        self._clear_working_message()
        self.add_message(Message(
            role="system",
            content=f"[red]Stream error:[/red] {error}"
        ))

    def _show_working_message(self) -> None:
        """Display a lightweight pending indicator while the backend starts."""
        if self._working_message_id is not None:
            return
        message = Message(role="system", content="Working...")
        self._working_message_id = message.id
        self.add_message(message)

    def _clear_working_message(self) -> None:
        """Remove the pending indicator once output or an error arrives."""
        if self._working_message_id is None:
            return
        self._messages = [msg for msg in self._messages if msg.id != self._working_message_id]
        self._working_message_id = None
        self._invalidate()

    def _invalidate(self) -> None:
        """Request a UI redraw from the application."""
        if self._app and self._running:
            try:
                self._app.invalidate()
            except Exception:
                pass

    # ==================================================================
    # Callbacks
    # ==================================================================

    def set_on_user_input(self, callback: Callable) -> None:
        """Set callback for when user submits non-command text.

        Args:
            callback: Called with the submitted text string.
        """
        self._on_user_input_callback = callback

    _on_user_input_callback: Optional[Callable] = None

    # ==================================================================
    # Slash Command Implementations
    # ==================================================================

    def _slash_completion_active(self) -> bool:
        """Return true only when the slash completion menu should own arrows."""
        return bool(
            self._input_buffer.complete_state
            and self._input_buffer.text.startswith("/")
        )

    def _refresh_slash_completions(self, *, select_first: bool = False) -> None:
        """Refresh slash completions without selecting or inserting a candidate."""
        if not hasattr(self, "_input_buffer"):
            return
        text = self._input_buffer.text
        if not text.startswith("/") or "\n" in text:
            if self._input_buffer.complete_state:
                self._input_buffer.cancel_completion()
            return

        completions = list(
            SlashCommandCompleter().get_completions(
                Document(text, len(text)),
                CompleteEvent(text_inserted=True),
            )
        )
        if completions:
            state = self._input_buffer._set_completions(completions)
            if select_first and state.completions:
                state.go_to_index(0)
        elif self._input_buffer.complete_state:
            self._input_buffer.cancel_completion()

    def _apply_completion(self, completion: Completion) -> None:
        """Apply a completion without immediately reopening completions."""
        complete_while_typing = self._input_buffer.complete_while_typing
        self._input_buffer.complete_while_typing = Condition(lambda: False)
        try:
            self._input_buffer.apply_completion(completion)
        finally:
            self._input_buffer.complete_while_typing = complete_while_typing

    def _parse_args(self, args: list[str]) -> dict[str, str | bool | list[str]]:
        parsed: dict[str, str | bool | list[str]] = {"_": []}
        positionals: list[str] = []
        i = 0
        while i < len(args):
            token = args[i]
            if token.startswith("--"):
                key = token[2:].replace("-", "_")
                if i + 1 < len(args) and not args[i + 1].startswith("--"):
                    parsed[key] = args[i + 1]
                    i += 2
                else:
                    parsed[key] = True
                    i += 1
            else:
                positionals.append(token)
                i += 1
        parsed["_"] = positionals
        return parsed

    def _run_with_status(self, label: str, func: Callable[[], None]) -> None:
        if self._task_running:
            self.add_message(Message(
                role="system",
                content="Another command is already running. Press Ctrl+C to request interrupt.",
            ))
            return

        self._task_running = True
        self.add_message(Message(role="system", content=label))
        self.set_status(streaming=True)

        def run_task() -> None:
            stdout = io.StringIO()
            stderr = io.StringIO()
            logs = io.StringIO()
            log_handler = logging.StreamHandler(logs)
            log_handler.setLevel(logging.WARNING)
            log_handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
            root_logger = logging.getLogger()
            root_logger.addHandler(log_handler)
            redirected_handlers: list[tuple[logging.StreamHandler, object]] = []
            for logger_name in ("", "ascend_agent"):
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers:
                    if not isinstance(handler, logging.StreamHandler) or handler is log_handler:
                        continue
                    stream = getattr(handler, "stream", None)
                    if stream in (sys.stderr, sys.__stderr__, sys.stdout, sys.__stdout__):
                        redirected_handlers.append((handler, stream))
                        handler.setStream(stderr)
            try:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    func()
            except Exception as exc:
                self.add_message(Message(role="system", content=f"Error: {exc}"))
            finally:
                for handler, stream in redirected_handlers:
                    handler.setStream(stream)
                root_logger.removeHandler(log_handler)
                captured = "\n".join(
                    item.strip()
                    for item in (stdout.getvalue(), stderr.getvalue(), logs.getvalue())
                    if item.strip()
                )
                if captured:
                    if len(captured) > 4000:
                        captured = captured[-4000:]
                        captured = "[truncated]\n" + captured
                    self.add_message(Message(role="system", content=f"Command output:\n{captured}"))
                self._task_running = False
                self.set_status(streaming=False)

        threading.Thread(target=run_task, daemon=True).start()

    def _active_provider(self) -> str:
        if self._provider:
            return self._provider
        try:
            from ascend_agent.cli.config_manager import ConfigManager
            return ConfigManager().get_active()
        except Exception:
            return "openai"

    def _handle_models_command(self, args: list[str]) -> None:
        from ascend_agent.cli.config_manager import ConfigManager
        from ascend_agent.cli.model_catalog import PROVIDER_PRESETS, full_model_id
        from ascend_agent.cli.models import use_model

        cm = ConfigManager()
        action = args[0] if args else ""
        if action in ("use", "select") and len(args) >= 2:
            try:
                selected = use_model(cm, args[1])
            except ValueError as exc:
                self.add_message(Message(role="system", content=f"Model error: {exc}"))
                return
            provider, _ = selected.split("/", 1)
            self._provider = provider
            self._model = selected
            self.set_status(provider=provider, model=selected)
            self.add_message(Message(role="system", content=f"Model selected: {selected}"))
            return

        if action == "status":
            self.add_message(Message(role="system", content=self._format_model_status(cm)))
            return

        if action in ("list", "ls", "show"):
            self.add_message(Message(role="system", content=self._format_model_list(cm)))
            return

        choices: list[tuple[str, str, bool]] = []
        active = cm.get_active_model()
        for provider in cm.list_providers():
            preset = PROVIDER_PRESETS.get(provider.name)
            models = list(preset.models) if preset else [provider.default_model]
            for model in models:
                model_id = full_model_id(provider.name, model)
                choices.append((model_id, provider.name, model_id == active))
        self._model_choices = choices
        self._model_picker_index = max(
            0,
            next((i for i, (model_id, _, _) in enumerate(choices) if model_id == active), 0),
        )
        self._model_picker_active = True
        self._invalidate()

    def _format_model_list(self, cm) -> str:
        from ascend_agent.cli.model_catalog import PROVIDER_PRESETS, full_model_id
        from ascend_agent.cli.models import _is_configured

        active = cm.get_active_model()
        lines = [f"Current model: {active}", "", "Available models:"]
        for provider in cm.list_providers():
            preset = PROVIDER_PRESETS.get(provider.name)
            models = list(preset.models) if preset else [provider.default_model]
            status = "configured" if _is_configured(provider) else "needs key"
            lines.append(f"{provider.name} ({status})")
            for model in models:
                model_id = full_model_id(provider.name, model)
                marker = "*" if model_id == active else " "
                lines.append(f"  {marker} {model_id}")
        lines.append("")
        lines.append("Use /models to open the selector or /models use <provider/model>.")
        return "\n".join(lines)

    def _format_model_status(self, cm) -> str:
        from ascend_agent.cli.config_manager import CONFIG_FILE
        from ascend_agent.cli.model_catalog import split_model_id
        from ascend_agent.cli.models import _is_configured

        active = cm.get_active_model()
        provider_name, _ = split_model_id(active)
        provider = cm.get_provider(provider_name)
        configured = _is_configured(provider) if provider else False
        env_name = f"ASCEND_{provider_name.upper()}_API_KEY"
        if provider_name == "openai":
            env_name += " or OPENAI_API_KEY"
        return "\n".join([
            f"model: {active}",
            f"provider: {provider_name}",
            f"configured: {'yes' if configured else 'no'}",
            f"config: {CONFIG_FILE}",
            f"env: {env_name}",
        ])

    def _render_model_picker(self) -> list[tuple[str, str]]:
        lines: list[tuple[str, str]] = [
            ("bold fg:cyan", " Select Model\n"),
            ("fg:#657b83", " Use Up/Down to navigate, Enter to select, Esc to cancel.\n\n"),
        ]
        for i, (model_id, provider, active) in enumerate(self._model_choices):
            selected = i == self._model_picker_index
            prefix = ">" if selected else " "
            active_marker = " *" if active else ""
            style = "bold fg:#b58900" if selected else ("fg:green" if active else "fg:#839496")
            lines.append((style, f" {prefix} {model_id}{active_marker}\n"))
        return lines

    def _select_highlighted_model(self) -> None:
        if not self._model_choices:
            self._model_picker_active = False
            self._invalidate()
            return
        model_id, provider, _ = self._model_choices[self._model_picker_index]
        try:
            from ascend_agent.cli.config_manager import ConfigManager
            from ascend_agent.cli.models import use_model

            selected = use_model(ConfigManager(), model_id)
        except ValueError as exc:
            self.add_message(Message(role="system", content=f"Model error: {exc}"))
            self._model_picker_active = False
            self._invalidate()
            return
        self._provider = provider
        self._model = selected
        self._model_picker_active = False
        self.set_status(provider=provider, model=selected)
        self.add_message(Message(role="system", content=f"Model selected: {selected}"))

    def _run_diagnose_command(self, args: list[str]) -> None:
        parsed = self._parse_args(args)
        positionals = parsed["_"]
        if not isinstance(positionals, list) or not positionals:
            self.add_message(Message(
                role="system",
                content="Usage: /diagnose <repo> [--trace file | --trace-text 'text'] [--output file]",
            ))
            return

        def work() -> None:
            from ascend_agent.cli.diagnose import render_context, render_diagnosis
            from ascend_agent.config import settings
            from ascend_agent.context.models import ConfigEnv, ContextDocument
            from ascend_agent.context.repo import RepoScanner
            from ascend_agent.context.trace import trace_from_file, trace_from_text
            from ascend_agent.diagnosis.engine import Engine
            from ascend_agent.diagnosis.router import create_router
            from ascend_agent.diagnosis.tool_client import create_tool_client

            repo = str(positionals[0])
            trace_text = parsed.get("trace_text")
            trace_path = parsed.get("trace")
            if not trace_text and not trace_path and len(positionals) > 1:
                trace_text = " ".join(str(item) for item in positionals[1:])
            self.add_message(Message(role="system", content="Building context..."))
            repo_info = RepoScanner().scan(repo)
            trace_info = None
            if isinstance(trace_path, str):
                trace_info = trace_from_file(trace_path)
            elif isinstance(trace_text, str):
                trace_info = trace_from_text(trace_text)
            doc = ContextDocument(
                repo=repo_info,
                trace=trace_info,
                config_env=ConfigEnv(
                    python_version=settings.python_version,
                    platform=settings.platform,
                    env_vars=settings.env_vars,
                ),
            )
            self.add_message(Message(role="assistant", content=render_context(doc)))
            self.add_message(Message(role="system", content="Running diagnosis..."))
            router = create_router(provider=self._active_provider())
            tool_output = io.StringIO()
            tool_client = create_tool_client(errlog=tool_output)
            result = Engine(router=router, repo_path=repo, search_tool=tool_client.search_code).diagnose(doc)
            output = DiagnosisOutput(context_doc=doc, diagnosis_result=result)
            self._last_diagnosis = output
            captured_tool_output = tool_output.getvalue().strip()
            if captured_tool_output:
                self.add_message(Message(role="system", content=f"Command output:\n{captured_tool_output}"))
            output_path = parsed.get("output")
            saved = ""
            if isinstance(output_path, str):
                Path(output_path).write_text(output.model_dump_json(indent=2))
                saved = f"\nSaved diagnosis JSON: {output_path}"
            self.add_message(Message(role="assistant", content=render_diagnosis(result) + saved))

        self._run_with_status("Running diagnosis...", work)

    def _format_context(self, doc: ContextDocument) -> str:
        lines = ["Context"]
        if doc.repo:
            lines.extend(
                [
                    "",
                    "Repository Info",
                    f"Path: {doc.repo.path}",
                    f"Language: {doc.repo.language}",
                    f"Files: {doc.repo.file_count}",
                ]
            )
            structure_preview = ", ".join(doc.repo.structure[:20])
            if len(doc.repo.structure) > 20:
                structure_preview += ", ..."
            if structure_preview:
                lines.append(f"Structure: {structure_preview}")

        if doc.trace:
            lines.append("")
            if doc.trace.error_type:
                lines.append(f"Error: {doc.trace.error_type}")
                if doc.trace.error_message:
                    lines.append(doc.trace.error_message)
            else:
                lines.append("Error: not detected")
                if doc.trace.parse_warnings:
                    lines.append(", ".join(doc.trace.parse_warnings))
            if doc.trace.signal_candidates:
                signals = ", ".join(
                    f"{candidate.kind}={candidate.value} ({candidate.confidence:.2f})"
                    for candidate in doc.trace.signal_candidates[:5]
                )
                lines.append(f"Uncertain signals: {signals}")
            if doc.trace.error_events:
                lines.append("Parsed error events:")
                for event in doc.trace.error_events[:5]:
                    lines.append(
                        f"- {event.kind} line {event.source_line}: "
                        f"{event.message} ({event.confidence:.2f})"
                    )
            if doc.trace.frames:
                lines.append("Stack Trace:")
                for i, frame in enumerate(doc.trace.frames[:10], 1):
                    lines.append(f"- {i}. {frame.file}:{frame.line} in {frame.function}")
                if len(doc.trace.frames) > 10:
                    lines.append(f"... {len(doc.trace.frames) - 10} more frames")

        lines.append("")
        lines.append(
            f"Environment: Python {doc.config_env.python_version[:6]} "
            f"on {doc.config_env.platform}"
        )
        return "\n".join(lines)

    def _format_diagnosis(self, result: DiagnosisResult) -> str:
        lines = ["Diagnosis Results", f"Search iterations used: {result.iterations_used}/3"]
        if result.errors:
            lines.append("")
            lines.append("Partial failures:")
            for error in result.errors:
                lines.append(f"- {error.stage}: {error.reason}")
                if error.details:
                    lines.append(f"  {error.details}")
        if not result.hypotheses:
            lines.append("")
            lines.append("No hypotheses could be generated.")
            return "\n".join(lines)
        for i, hyp in enumerate(result.hypotheses, 1):
            lines.append("")
            lines.append(f"Hypothesis #{i} ({hyp.confidence:.0%})")
            lines.append(hyp.root_cause)
            for ev in hyp.evidence:
                lines.append(f"- {ev.file_path}:{ev.line_number} {ev.relevance}")
                if ev.code_snippet:
                    lines.append("```")
                    lines.append(ev.code_snippet.rstrip())
                    lines.append("```")
        return "\n".join(lines)

    def _load_diagnosis(self, path: str | None) -> DiagnosisOutput:
        if path:
            return DiagnosisOutput.model_validate_json(Path(path).read_text())
        if self._last_diagnosis is None:
            raise ValueError("No diagnosis available. Run /diagnose first or pass a diagnosis JSON path.")
        return self._last_diagnosis

    def _run_fix_command(self, args: list[str]) -> None:
        parsed = self._parse_args(args)
        positionals = parsed["_"]
        if isinstance(positionals, list) and positionals and positionals[0] == "apply":
            self._apply_last_fixes(parsed.get("output") if isinstance(parsed.get("output"), str) else None)
            return
        diagnosis_path = positionals[0] if isinstance(positionals, list) and positionals else None

        def work() -> None:
            from ascend_agent.diagnosis.fix_engine import FixEngine
            from ascend_agent.diagnosis.router import create_router

            diagnosis = self._load_diagnosis(str(diagnosis_path) if diagnosis_path else None)
            repo_path = diagnosis.context_doc.repo.path
            router = create_router(provider=self._active_provider())
            result = FixEngine(router=router, repo_path=repo_path).generate_fixes(diagnosis.diagnosis_result)
            self._last_fixes = result
            output_path = parsed.get("output")
            saved = ""
            if isinstance(output_path, str):
                Path(output_path).write_text(result.model_dump_json(indent=2))
                saved = f"\nSaved fix suggestions JSON: {output_path}"
            self.add_message(Message(role="assistant", content=self._format_fixes(result) + saved))

        self._run_with_status("Generating fix suggestions...", work)

    def _format_fixes(self, result: FixGenerationResult) -> str:
        lines = [
            "Fix Generation Complete",
            f"Generated {len(result.suggestions)} suggestions for {result.total_hypotheses} hypotheses",
        ]
        if result.errors:
            lines.append("")
            lines.append("Partial failures:")
            for error in result.errors:
                lines.append(f"- {error.stage}: {error.reason}")
        for i, suggestion in enumerate(result.suggestions, 1):
            lines.append("")
            lines.append(f"Fix #{i}: {suggestion.file_path}")
            lines.append(suggestion.explanation)
            lines.append(suggestion.diff_patch)
        if result.suggestions:
            lines.append("")
            lines.append("Use /fix apply to apply all generated suggestions.")
        return "\n".join(lines)

    def _apply_last_fixes(self, output_path: str | None = None) -> None:
        if self._last_fixes is None or not self._last_fixes.suggestions:
            self.add_message(Message(role="system", content="No generated fixes available. Run /fix first."))
            return
        if self._last_diagnosis is None:
            self.add_message(Message(role="system", content="No diagnosis context available for repo path."))
            return

        def work() -> None:
            from ascend_agent.tools.file_edit import edit_file

            repo_path = self._last_diagnosis.context_doc.repo.path
            by_file: dict[str, list[dict]] = defaultdict(list)
            for suggestion in self._last_fixes.suggestions:
                for replacement in suggestion.replacements:
                    by_file[suggestion.file_path].append(
                        {"old_text": replacement.old_text, "new_text": replacement.new_text}
                    )
            applied = 0
            failed: list[str] = []
            for file_path, ops in by_file.items():
                result = asyncio.run(edit_file(str(Path(repo_path) / file_path), ops, repo_path=repo_path))
                data = json.loads(result)
                if data.get("status") == "ok":
                    applied += 1
                else:
                    failed.append(f"{file_path}: {data.get('error', 'unknown error')}")
            if output_path:
                Path(output_path).write_text(self._last_fixes.model_dump_json(indent=2))
            lines = [f"Applied fixes to {applied} file(s)."]
            if failed:
                lines.append("Failed:")
                lines.extend(f"- {item}" for item in failed)
            if output_path:
                lines.append(f"Saved applied fix suggestions JSON: {output_path}")
            self.add_message(Message(role="assistant", content="\n".join(lines)))

        self._run_with_status("Applying generated fixes...", work)

    def _run_reproduce_command(self, args: list[str]) -> None:
        parsed = self._parse_args(args)
        positionals = parsed["_"]
        diagnosis_path = positionals[0] if isinstance(positionals, list) and positionals else None

        def work() -> None:
            from ascend_agent.config import settings
            from ascend_agent.diagnosis.router import create_router
            from ascend_agent.reproduction.engine import ReproductionEngine

            diagnosis = self._load_diagnosis(str(diagnosis_path) if diagnosis_path else None)
            repo_path = diagnosis.context_doc.repo.path
            router = create_router(provider=self._active_provider())
            result = asyncio.run(
                ReproductionEngine(router=router, repo_path=repo_path, settings=settings).reproduce(
                    diagnosis.diagnosis_result,
                    trace=diagnosis.context_doc.trace,
                )
            )
            result.repo_path = repo_path
            self._last_reproduction = result
            output_path = parsed.get("output")
            saved = ""
            if isinstance(output_path, str):
                Path(output_path).write_text(result.model_dump_json(indent=2))
                saved = f"\nSaved reproduction JSON: {output_path}"
            self.add_message(Message(role="assistant", content=self._format_reproduction(result) + saved))

        self._run_with_status("Running reproduction...", work)

    def _format_reproduction(self, result: ReproductionResult) -> str:
        lines = [
            "Reproduction Result",
            f"Status: {result.status}",
            f"Command: {result.command}",
            f"Exit code: {result.exit_code}",
            f"Duration: {result.duration_seconds:.2f}s",
            f"Hypothesis tested: {result.hypothesis_id_tested}",
            f"Reproduced: {'yes' if result.reproduced else 'no'}",
        ]
        if result.repro_file:
            lines.append(f"Bad case: {result.repro_file}")
        if result.matched_error_signal:
            lines.append(f"Matched signal: {result.matched_error_signal}")
        if result.attempts:
            lines.append("Attempts:")
            for attempt in result.attempts:
                label = attempt.kind.replace("_", " ")
                lines.append(
                    f"- {label}: {attempt.status} exit={attempt.exit_code} "
                    f"matched={'yes' if attempt.matched_error else 'no'}"
                )
                if attempt.repro_file:
                    lines.append(f"  file: {attempt.repro_file}")
        if result.stdout:
            lines.append(f"\nstdout:\n{result.stdout}")
        if result.stderr:
            lines.append(f"\nstderr:\n{result.stderr}")
        return "\n".join(lines)

    def _run_verify_command(self, args: list[str]) -> None:
        parsed = self._parse_args(args)
        positionals = parsed["_"]
        reproduction_path = positionals[0] if isinstance(positionals, list) and positionals else None

        def work() -> None:
            from ascend_agent.config import settings
            from ascend_agent.diagnosis.router import create_router
            from ascend_agent.verification.engine import VerificationEngine

            if reproduction_path:
                reproduction = ReproductionResult.model_validate_json(Path(str(reproduction_path)).read_text())
            elif self._last_reproduction is not None:
                reproduction = self._last_reproduction
            else:
                raise ValueError("No reproduction available. Run /reproduce first or pass a reproduction JSON path.")
            repo_path = reproduction.repo_path or settings.repo_path or "."
            router = create_router(provider=self._active_provider())
            result = asyncio.run(
                VerificationEngine(router=router, repo_path=repo_path, settings=settings).verify(reproduction)
            )
            self._last_verification = result
            output_path = parsed.get("output")
            saved = ""
            if isinstance(output_path, str):
                Path(output_path).write_text(result.model_dump_json(indent=2))
                saved = f"\nSaved verification JSON: {output_path}"
            self.add_message(Message(role="assistant", content=self._format_verification(result) + saved))

        self._run_with_status("Running verification...", work)

    def _format_verification(self, result: VerificationResult) -> str:
        lines = [
            "Verification Result",
            f"Status: {result.status}",
            f"Framework: {result.framework or 'none detected'}",
            f"Command: {result.command}",
            f"Tests found: {result.tests_found} | Tests run: {result.tests_run}",
            f"Passed: {result.passed} | Failed: {result.failed} | Errors: {result.errors}",
            f"Duration: {result.duration_seconds:.2f}s",
            f"Summary: {result.summary}",
        ]
        if result.files_tested:
            lines.append("")
            lines.append("Test files executed:")
            lines.extend(f"- {path}" for path in result.files_tested)
        return "\n".join(lines)


# ==================================================================
# Factory function
# ==================================================================

def run_tui(
    provider: str = "",
    model: str = "",
    on_input: Optional[Callable] = None,
    history_file: str | None = None,
) -> None:
    """Create and run the Ascend TUI application.

    This is the main entry point — call it to launch the immersive
    terminal interface.

    Args:
        provider: LLM provider name (e.g., 'openai', 'deepseek').
        model: Model name to display in the status bar.
        on_input: Optional callback for user text input (non-commands).
                  Receives the text string. Use this to integrate with
                  your AI backend for streaming responses.
        history_file: Path to command history file.

    Example:
        from ascend_agent.cli.tui import run_tui

        def handle_input(text):
            # Send to AI, stream response back
            ...

        run_tui(provider="openai", model="gpt-5.5", on_input=handle_input)
    """
    tui = AscendTUI(
        provider=provider,
        model=model,
        history_file=history_file,
    )
    if on_input:
        tui.set_on_user_input(on_input)
    tui.run()
