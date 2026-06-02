"""Terminal control utilities — alternate screen buffer, cursor, raw mode.

Handles full-screen mode entry/exit (alternate screen buffer) and terminal
capabilities detection, analogous to the terminal control used by vim/less/htop.
"""

from __future__ import annotations

import sys
import os
import shutil
import logging

logger = logging.getLogger(__name__)

# ANSI escape sequences for alternate screen buffer
ALT_SCREEN_ENTER = "\x1b[?1049h"  # Save cursor + switch to alternate screen
ALT_SCREEN_EXIT = "\x1b[?1049l"   # Restore cursor + switch back to main screen
CURSOR_HIDE = "\x1b[?25l"
CURSOR_SHOW = "\x1b[?25h"
CLEAR_SCREEN = "\x1b[2J"
CURSOR_HOME = "\x1b[H"


def enter_alternate_screen() -> None:
    """Switch to the alternate screen buffer (full-screen mode).

    Saves the current terminal state and switches to a clean buffer.
    Called when the TUI starts — equivalent to vim/less entering full-screen.
    """
    sys.stdout.write(ALT_SCREEN_ENTER)
    sys.stdout.write(CURSOR_HIDE)
    sys.stdout.flush()


def exit_alternate_screen() -> None:
    """Restore the main screen buffer and cursor visibility.

    Called when the TUI exits to ensure the terminal is left clean.
    """
    sys.stdout.write(CURSOR_SHOW)
    sys.stdout.write(ALT_SCREEN_EXIT)
    sys.stdout.flush()


def get_terminal_size() -> tuple[int, int]:
    """Return current terminal size as (columns, rows)."""
    size = shutil.get_terminal_size(fallback=(80, 24))
    return size.columns, size.lines


def is_terminal() -> bool:
    """Check if stdout is a TTY (interactive terminal)."""
    return sys.stdout.isatty()


def supports_unicode() -> bool:
    """Check if the terminal likely supports Unicode box-drawing characters."""
    encoding = sys.stdout.encoding or ""
    return "utf" in encoding.lower()


def supports_truecolor() -> bool:
    """Check if the terminal supports 24-bit truecolor."""
    colorterm = os.environ.get("COLORTERM", "")
    if colorterm in ("truecolor", "24bit"):
        return True
    # Many modern terminals support it even without COLORTERM
    term = os.environ.get("TERM", "")
    if "256color" in term or "truecolor" in term:
        return True
    return False
