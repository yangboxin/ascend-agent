"""Hook: command history management.

Provides Up/Down arrow navigation through previously entered commands,
with persistent storage and duplicate suppression.
"""

from __future__ import annotations

import os
import json
from pathlib import Path


class CommandHistory:
    """Manages a ring buffer of previously entered commands.

    Supports:
    - Adding commands to history
    - Navigating backward (Up) and forward (Down)
    - Persisting history to disk
    - Loading history on startup
    """

    def __init__(self, max_size: int = 500, history_file: str | None = None) -> None:
        self._max_size = max_size
        self._history: list[str] = []
        self._index: int = -1  # -1 means "not navigating"
        self._current_input_before_navigate: str = ""
        self._history_file = history_file or self._default_history_path()
        self._load()

    # ---- read/write ----

    def _default_history_path(self) -> Path:
        """Return default history file path: ~/.ascend_agent_history."""
        base = os.environ.get("ASCEND_HISTORY", os.path.expanduser("~"))
        return Path(base) / ".ascend_agent_history"

    def _load(self) -> None:
        try:
            path = Path(self._history_file)
            if path.exists():
                data = json.loads(path.read_text())
                if isinstance(data, list):
                    self._history = [str(item) for item in data[-self._max_size:]]
        except Exception:
            pass

    def save(self) -> None:
        """Persist history to disk."""
        try:
            path = Path(self._history_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._history, ensure_ascii=False))
        except Exception:
            pass

    # ---- mutations ----

    def add(self, command: str) -> None:
        """Add a command to history, suppressing consecutive duplicates.

        Args:
            command: The command string to add.
        """
        stripped = command.strip()
        if not stripped:
            return
        # Suppress consecutive duplicates
        if self._history and self._history[-1] == stripped:
            return
        self._history.append(stripped)
        if len(self._history) > self._max_size:
            self._history = self._history[-self._max_size:]
        self._index = -1
        self._current_input_before_navigate = ""

    def clear(self) -> None:
        """Clear all history (in-memory; does not delete file)."""
        self._history.clear()
        self._index = -1

    # ---- navigation ----

    def navigate_up(self, current_input: str) -> str | None:
        """Navigate to the previous (older) command in history.

        On first call (index == -1), saves current input so Down can restore it.

        Args:
            current_input: The text currently in the input field.

        Returns:
            The historical command string, or None if at the beginning.
        """
        if not self._history:
            return None
        if self._index == -1:
            self._current_input_before_navigate = current_input
            self._index = len(self._history) - 1
        elif self._index > 0:
            self._index -= 1
        else:
            return None  # Already at oldest
        return self._history[self._index]

    def navigate_down(self) -> str | None:
        """Navigate to the next (newer) command in history.

        Returns:
            The historical command string, or the pre-navigation input
            when returning to the "present", or None if at newest.
        """
        if self._index == -1:
            return None
        if self._index < len(self._history) - 1:
            self._index += 1
            return self._history[self._index]
        else:
            # Return to the input the user had before navigating
            self._index = -1
            saved = self._current_input_before_navigate
            self._current_input_before_navigate = ""
            return saved

    # ---- queries ----

    def get_all(self) -> list[str]:
        """Return all history entries (most recent last)."""
        return list(self._history)

    def get_recent(self, n: int = 10) -> list[str]:
        """Return the n most recent commands."""
        return self._history[-n:]

    def search(self, prefix: str) -> list[str]:
        """Return history entries that start with the given prefix."""
        prefix_lower = prefix.lower()
        return [cmd for cmd in self._history if cmd.lower().startswith(prefix_lower)]

    def __len__(self) -> int:
        return len(self._history)

    def __bool__(self) -> bool:
        return bool(self._history)
