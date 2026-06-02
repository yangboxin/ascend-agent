"""Content area component — the scrollable message display region.

This is the main content pane that shows the conversation history.
It scrolls independently from the fixed-bottom input bar.
"""

from __future__ import annotations

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import Window, ScrollOffsets
from prompt_toolkit.layout.controls import FormattedTextControl

from ascend_agent.cli.tui.components.message_bubble import Message, format_messages


class ContentArea:
    """Manages the scrollable content region showing messages.

    Wraps a prompt_toolkit Window with FormattedTextControl for
    efficient rendering. Supports scroll-to-bottom on new messages
    and manual scroll via PageUp/PageDown.
    """

    def __init__(self, max_messages: int = 1000) -> None:
        self._messages: list[Message] = []
        self._max_messages = max_messages
        self._auto_scroll: bool = True
        self._width: int = 80
        self._control = FormattedTextControl(
            text=self._get_formatted_text,
            focusable=False,
        )
        self._window = Window(
            content=self._control,
            wrap_lines=True,
            allow_scroll_beyond_bottom=False,
            cursorline=False,
            dont_extend_height=False,
        )

    # ---- message management ----

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def add_message(self, message: Message) -> None:
        """Append a message to the content area.

        Trims oldest messages if exceeding max_messages.

        Args:
            message: The Message to add.
        """
        self._messages.append(message)
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages:]
        self._invalidate()

    def append_to_last(self, text: str) -> None:
        """Append text to the most recent assistant message.

        Used for streaming: each chunk is appended to the last message.
        If the last message is not an assistant message, creates a new one.

        Args:
            text: Text chunk to append.
        """
        if self._messages and self._messages[-1].is_assistant:
            self._messages[-1].content += text
        else:
            self._messages.append(Message(role="assistant", content=text))
        self._invalidate()

    def update_last_content(self, content: str) -> None:
        """Replace the content of the last assistant message.

        More efficient than append_to_last for rapid updates.

        Args:
            content: Full new content for the last message.
        """
        if self._messages and self._messages[-1].is_assistant:
            self._messages[-1].content = content
        else:
            self._messages.append(Message(role="assistant", content=content))
        self._invalidate()

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()
        self._invalidate()

    # ---- scrolling ----

    @property
    def auto_scroll(self) -> bool:
        return self._auto_scroll

    @auto_scroll.setter
    def auto_scroll(self, value: bool) -> None:
        self._auto_scroll = value

    def scroll_to_bottom(self) -> None:
        """Scroll to show the most recent messages."""
        # prompt_toolkit Window handles this via cursor_position
        self._invalidate()

    def scroll_up(self, lines: int = 5) -> None:
        """Scroll the content area up by N lines."""
        self._auto_scroll = False
        # Scrolling is handled by prompt_toolkit's built-in Window scrolling

    def scroll_down(self, lines: int = 5) -> None:
        """Scroll the content area down by N lines."""
        # Scrolling is handled by prompt_toolkit's built-in Window scrolling

    # ---- size ----

    def set_width(self, width: int) -> None:
        """Update the terminal width for text wrapping context."""
        self._width = width
        self._invalidate()

    # ---- layout ----

    @property
    def window(self) -> Window:
        """The prompt_toolkit Window object for use in Layout."""
        return self._window

    def _get_formatted_text(self) -> FormattedText:
        """Callback for FormattedTextControl — returns the current formatted text."""
        if not self._messages:
            return FormattedText([("fg:#657b83", "Welcome to Ascend Agent TUI.\n"
                                     "Type a message or /help for commands.\n")])
        return format_messages(self._messages, self._width)

    def _invalidate(self) -> None:
        """Mark the content area as needing a redraw."""
        # In prompt_toolkit, we invalidate by triggering a redraw
        # This is done by the application's event loop
        pass


def create_content_window(content_area: ContentArea) -> Window:
    """Create a prompt_toolkit Window for the content area.

    Args:
        content_area: The ContentArea instance managing messages.

    Returns:
        A Window configured for scrollable content display.
    """
    return Window(
        content=FormattedTextControl(
            text=lambda: (
                format_messages(content_area._messages, content_area._width)
                if content_area._messages
                else FormattedText([("#657b83", "Welcome to Ascend Agent TUI.\n"
                                              "Type a message or /help for commands.\n")])
            ),
            focusable=False,
        ),
        wrap_lines=True,
        allow_scroll_beyond_bottom=False,
        cursorline=False,
    )
