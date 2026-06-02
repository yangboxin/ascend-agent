"""Input bar component — fixed-bottom multiline input area.

The input bar is always positioned at the bottom of the terminal,
analogous to the input area in Claude Code. It supports:
- Multiline input (up to 3 lines)
- Command history navigation (Up/Down)
- Submit on Enter, newline on Shift+Enter
- Visual border separating it from the content area
"""

from __future__ import annotations

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import Window
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.layout.processors import BeforeInput, ConditionalProcessor


class InputBar:
    """Fixed-bottom text input area with history and multiline support.

    Manages the input buffer, history navigation, and submit handling.
    Designed to occupy the last 3 rows of the terminal.
    """

    def __init__(
        self,
        on_submit: callable = None,
        multiline: bool = True,
        history: object = None,  # CommandHistory instance
    ) -> None:
        self._on_submit = on_submit or (lambda text: None)
        self._history = history
        self._buffer = Buffer(
            multiline=multiline,
            accept_handler=self._handle_accept,
            name="input",
        )
        self._control = BufferControl(
            buffer=self._buffer,
            input_processors=[
                BeforeInput("> "),
                ConditionalProcessor(
                    processor=BeforeInput("... "),
                    condition=lambda: self._buffer.text.count("\n") > 0,
                ),
            ],
        )
        self._window = Window(
            content=self._control,
            height=3,
            wrap_lines=True,
            cursorline=True,
        )
        self._current_input_backup: str = ""

    # ---- buffer access ----

    @property
    def buffer(self) -> Buffer:
        return self._buffer

    @property
    def text(self) -> str:
        return self._buffer.text

    @text.setter
    def text(self, value: str) -> None:
        self._buffer.text = value

    def set_text(self, text: str) -> None:
        """Set input text programmatically."""
        self._buffer.text = text

    def clear(self) -> None:
        """Clear the input buffer."""
        self._buffer.text = ""

    # ---- history navigation ----

    def navigate_history_up(self) -> None:
        """Replace current input with the previous history entry."""
        if self._history is None:
            return

        current = self._buffer.text
        result = self._history.navigate_up(current)
        if result is not None:
            self._buffer.text = result
            # Move cursor to end
            self._buffer.cursor_position = len(self._buffer.text)

    def navigate_history_down(self) -> None:
        """Replace current input with the next history entry."""
        if self._history is None:
            return

        result = self._history.navigate_down()
        if result is not None:
            self._buffer.text = result
            self._buffer.cursor_position = len(self._buffer.text)

    def add_to_history(self, text: str) -> None:
        """Add submitted text to command history."""
        if self._history is not None and text.strip():
            self._history.add(text.strip())

    # ---- layout ----

    @property
    def window(self) -> Window:
        return self._window

    def focus(self) -> None:
        """Ensure the input buffer has focus."""
        # Focus is managed by the prompt_toolkit Application layout

    # ---- internals ----

    def _handle_accept(self, buffer: Buffer) -> bool:
        """Called when the user presses Enter to submit.

        Returns:
            True to keep the buffer, False to clear it.
        """
        text = buffer.text.strip()
        if text:
            self.add_to_history(text)
        self._on_submit(buffer.text)
        return False  # Clear buffer after submit


def create_input_window(
    on_submit: callable,
    history: object = None,
    placeholder: str = "Type a message or /command...",
) -> Window:
    """Create the input bar Window for use in the TUI layout.

    Args:
        on_submit: Callback receiving submitted text.
        history: CommandHistory instance for Up/Down navigation.
        placeholder: Placeholder text when input is empty.

    Returns:
        A Window configured for the fixed-bottom input area.
    """
    buffer = Buffer(
        multiline=True,
        accept_handler=lambda buf: _handle_input_accept(buf, on_submit, history),
        name="input",
    )

    control = BufferControl(
        buffer=buffer,
        input_processors=[
            BeforeInput("> "),
        ],
    )

    return Window(
        content=control,
        height=3,
        wrap_lines=True,
        cursorline=True,
    )


def _handle_input_accept(buffer: Buffer, on_submit: callable, history) -> bool:
    """Internal accept handler — adds to history and calls on_submit."""
    text = buffer.text.strip()
    if text and history:
        history.add(text)
    on_submit(buffer.text)
    return False  # Clear buffer
