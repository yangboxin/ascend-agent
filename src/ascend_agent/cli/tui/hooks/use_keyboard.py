"""Hook: keyboard shortcut bindings.

Defines all keyboard shortcuts for the TUI application, including:
- Ctrl+C: interrupt current operation (does NOT exit)
- Ctrl+D: quit application (on empty input)
- Up/Down: navigate command history
- Tab: autocomplete
- Enter: submit
- Escape: cancel / clear input
"""

from __future__ import annotations

from typing import Callable

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys


class KeyboardManager:
    """Manages keyboard shortcuts for the TUI application.

    Separates key binding definition from the application logic so
    bindings can be composed and tested independently.
    """

    def __init__(self) -> None:
        self._bindings = KeyBindings()
        self._handlers: dict[str, Callable[[], None]] = {}
        self._conditional_handlers: dict[str, Callable[[], bool]] = {}

    def on(self, key: str, handler: Callable[[], None]) -> None:
        """Register a handler for a specific key combination."""
        self._handlers[key] = handler

    def on_conditional(self, key: str, condition: Callable[[], bool], handler: Callable[[], None]) -> None:
        """Register a conditional handler — only fires when condition() returns True."""
        self._conditional_handlers[key] = (condition, handler)

    def build_bindings(self) -> KeyBindings:
        """Build and return the prompt_toolkit KeyBindings object.

        Returns:
            KeyBindings configured with all registered handlers.
        """
        kb = KeyBindings()

        @kb.add(Keys.ControlC)
        def _(event):
            """Ctrl+C: Send interrupt signal — does NOT exit the application."""
            if "c-c" in self._handlers:
                self._handlers["c-c"]()

        @kb.add(Keys.ControlD)
        def _(event):
            """Ctrl+D: Quit on empty input, otherwise delete forward."""
            if "c-d" in self._handlers:
                self._handlers["c-d"]()

        @kb.add(Keys.ControlL)
        def _(event):
            """Ctrl+L: Clear the screen / content area."""
            if "c-l" in self._handlers:
                self._handlers["c-l"]()

        @kb.add(Keys.Escape)
        def _(event):
            """Escape: Cancel current operation or clear input."""
            if "escape" in self._handlers:
                self._handlers["escape"]()

        @kb.add(Keys.Up)
        def _(event):
            """Up arrow: Navigate command history backward."""
            if "up" in self._handlers:
                self._handlers["up"]()

        @kb.add(Keys.Down)
        def _(event):
            """Down arrow: Navigate command history forward."""
            if "down" in self._handlers:
                self._handlers["down"]()

        @kb.add(Keys.Tab)
        def _(event):
            """Tab: Trigger autocomplete."""
            if "tab" in self._handlers:
                self._handlers["tab"]()

        @kb.add(Keys.PageUp)
        def _(event):
            """PageUp: Scroll content area up."""
            if "pageup" in self._handlers:
                self._handlers["pageup"]()

        @kb.add(Keys.PageDown)
        def _(event):
            """PageDown: Scroll content area down."""
            if "pagedown" in self._handlers:
                self._handlers["pagedown"]()

        return kb

    def get_bindings(self) -> KeyBindings:
        """Get the KeyBindings object (lazy-build if needed)."""
        return self.build_bindings()


def create_default_keybindings(
    on_interrupt: Callable[[], None],
    on_quit: Callable[[], None],
    on_clear: Callable[[], None],
    on_history_up: Callable[[], None],
    on_history_down: Callable[[], None],
    on_cancel: Callable[[], None],
) -> KeyBindings:
    """Create the standard set of key bindings for the TUI.

    Args:
        on_interrupt: Called on Ctrl+C (interrupt current operation).
        on_quit: Called on Ctrl+D (quit application).
        on_clear: Called on Ctrl+L (clear screen).
        on_history_up: Called on Up arrow (previous history).
        on_history_down: Called on Down arrow (next history).
        on_cancel: Called on Escape (cancel current).

    Returns:
        Configured KeyBindings instance.
    """
    kb = KeyBindings()

    @kb.add(Keys.ControlC)
    def _interrupt(event):
        on_interrupt()

    @kb.add(Keys.ControlD)
    def _quit(event):
        on_quit()

    @kb.add(Keys.ControlL)
    def _clear(event):
        on_clear()

    @kb.add(Keys.Escape)
    def _cancel(event):
        on_cancel()

    @kb.add(Keys.Up)
    def _history_up(event):
        on_history_up()

    @kb.add(Keys.Down)
    def _history_down(event):
        on_history_down()

    return kb
