"""Hook: monitor terminal resize events.

Provides reactive terminal size tracking so components can adapt
their layout when the user resizes the terminal window.
"""

from __future__ import annotations

import os
import signal
import shutil
from dataclasses import dataclass


@dataclass
class TerminalSize:
    """Current terminal dimensions."""
    columns: int
    rows: int

    @property
    def content_height(self) -> int:
        """Height available for scrollable content (minus input + status bars)."""
        return max(1, self.rows - 5)  # 3 input + 1 status + 1 border

    @property
    def input_height(self) -> int:
        """Height reserved for the input area."""
        return 3


class TerminalSizeWatcher:
    """Watches terminal size changes, calling a callback on resize.

    In prompt_toolkit, terminal resize is handled automatically via
    SIGWINCH. This class provides a programmatic way to react to
    size changes for manual calculation of layout dimensions.
    """

    def __init__(self) -> None:
        size = shutil.get_terminal_size(fallback=(80, 24))
        self._columns = size.columns
        self._rows = size.lines
        self._callbacks: list[callable] = []

    @property
    def size(self) -> TerminalSize:
        return TerminalSize(columns=self._columns, rows=self._rows)

    def refresh(self) -> TerminalSize:
        """Re-read terminal size (call on SIGWINCH or before layout calc)."""
        size = shutil.get_terminal_size(fallback=(80, 24))
        self._columns = size.columns
        self._rows = size.lines
        return self.size

    def on_resize(self, callback) -> None:
        """Register a callback invoked when terminal size changes."""
        self._callbacks.append(callback)

    def notify(self) -> None:
        """Notify all registered callbacks of a resize."""
        self.refresh()
        for cb in self._callbacks:
            try:
                cb(self.size)
            except Exception:
                pass


# Singleton instance for the application
_watcher: TerminalSizeWatcher | None = None


def get_terminal_size_watcher() -> TerminalSizeWatcher:
    """Get or create the singleton terminal size watcher."""
    global _watcher
    if _watcher is None:
        _watcher = TerminalSizeWatcher()
    return _watcher
