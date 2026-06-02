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
import signal
import sys
import time
from typing import Callable, Optional

from prompt_toolkit import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, Dimension
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
            multiline=True,
            accept_handler=self._handle_input_accept,
            name="ascend_input",
        )

        # --- Content Text ---
        def get_content_text():
            if not self._messages:
                return FormattedText([
                    ("class:content", ""),
                    ("fg:#586e75", ""),
                    ("fg:#839496", "Welcome to Ascend Agent TUI.\n"),
                    ("fg:#657b83 dim", ""),
                    ("fg:#657b83 dim", "Type a message or /help for commands.\n"),
                    ("fg:#657b83 dim", "Ctrl+C interrupt  Ctrl+D quit  /help for more.\n"),
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
            self._interrupted = True
            if self._streaming_manager:
                self._streaming_manager.request_interrupt()

        @kb.add(Keys.ControlD)
        def _quit(event):
            """Ctrl+D: quit the application."""
            event.app.exit()

        @kb.add(Keys.ControlL)
        def _clear_screen(event):
            """Ctrl+L: clear messages."""
            self.clear_messages()

        @kb.add(Keys.Escape, eager=True)
        def _cancel(event):
            """Escape: cancel current operation."""
            self._interrupted = True
            if self._streaming_manager:
                self._streaming_manager.request_interrupt()

        @kb.add(Keys.Up, eager=True)
        def _history_up(event):
            """Up arrow: navigate command history backward."""
            if self._history:
                current = self._input_buffer.text
                result = self._history.navigate_up(current)
                if result is not None:
                    self._input_buffer.text = result
                    self._input_buffer.cursor_position = len(result)

        @kb.add(Keys.Down, eager=True)
        def _history_down(event):
            """Down arrow: navigate command history forward."""
            if self._history:
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
        if self._history:
            self._history.add(text)

        # Handle slash commands
        if text.startswith("/"):
            self._handle_slash_command(text)
            return False  # Clear

        # Regular message
        self._handle_text_input(text)
        return False  # Clear

    def _handle_slash_command(self, text: str) -> None:
        """Process slash commands like /quit, /help, /models, etc."""
        parts = text.split()
        cmd = parts[0].lstrip("/").lower()
        args = parts[1:]

        if cmd in ("quit", "exit", "q"):
            if self._app:
                self._app.exit()
            return

        elif cmd == "help":
            help_text = (
                "[bold]Available Commands[/bold]\n\n"
                "  [bold]/models[/bold]          Show current model and available model IDs\n"
                "  [bold]/models use <id>[/bold] Select a model\n"
                "  [bold]/chat <message>[/bold]  Chat with the active LLM provider\n"
                "  [bold]/reset-chat[/bold]      Clear chat history\n"
                "  [bold]/help[/bold]            Show this help\n"
                "  [bold]/quit[/bold]            Exit the session\n"
                "  [bold]/exit[/bold]            Same as /quit\n\n"
                "[dim]Keyboard shortcuts:[/dim]\n"
                "  Ctrl+C  Interrupt current operation\n"
                "  Ctrl+D  Quit application\n"
                "  Ctrl+L  Clear screen\n"
                "  ↑/↓     Browse command history\n"
                "  Esc     Cancel current operation"
            )
            self.add_message(Message(role="system", content=help_text))

        elif cmd == "reset-chat":
            self.clear_messages()
            self.add_message(Message(role="system", content=" Chat history cleared."))

        elif cmd == "models":
            self.add_message(Message(
                role="system",
                content="[bold]Active model:[/bold] " + (self._model or "unknown") +
                        "\nUse [bold]/models use <id>[/bold] to switch models."
            ))

        else:
            self.add_message(Message(
                role="system",
                content=f"[red]Unknown command:[/red] /{cmd}\n"
                        f"  Type [bold]/help[/bold] for available commands."
            ))

    def _handle_text_input(self, text: str) -> None:
        """Handle a regular (non-slash) text input as a user message."""
        self.add_user_message(text)
        # The actual AI response will be handled by external streaming
        # Call the on_user_input callback if set
        if self._on_user_input_callback:
            try:
                self._on_user_input_callback(text)
            except Exception:
                pass

    def _handle_stream_chunk(self, text: str) -> None:
        """Called for each chunk of streaming response."""
        self.append_to_assistant(text)

    def _handle_stream_complete(self) -> None:
        """Called when streaming is complete."""
        self._status.set_streaming(False)
        self._invalidate()

    def _handle_stream_error(self, error: Exception) -> None:
        """Called when streaming encounters an error."""
        self._status.set_streaming(False)
        self.add_message(Message(
            role="system",
            content=f"[red]Stream error:[/red] {error}"
        ))

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
