"""ANSI escape sequence utilities.

Low-level helpers for ANSI escape sequence generation and parsing,
used for terminal color, cursor movement, and screen control.
"""

from __future__ import annotations

import re
from enum import IntEnum


class ANSIColor(IntEnum):
    """Standard 16 ANSI colors (0–15)."""
    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7
    BRIGHT_BLACK = 8
    BRIGHT_RED = 9
    BRIGHT_GREEN = 10
    BRIGHT_YELLOW = 11
    BRIGHT_BLUE = 12
    BRIGHT_MAGENTA = 13
    BRIGHT_CYAN = 14
    BRIGHT_WHITE = 15


# Escape the bell character (used in some terminals)
ESC = "\x1b"
BEL = "\x07"


def sgr(*codes: int) -> str:
    """Build a Select Graphic Rendition (SGR) escape sequence.

    Args:
        codes: SGR codes (e.g., 1=bold, 31=red fg, 42=green bg).

    Returns:
        Full SGR escape string like ``\\x1b[1;31;42m``.
    """
    if not codes:
        codes = (0,)
    return f"{ESC}[{';'.join(map(str, codes))}m"


def reset() -> str:
    """SGR reset — clears all attributes."""
    return sgr(0)


def cursor_up(n: int = 1) -> str:
    """Move cursor up n rows."""
    return f"{ESC}[{n}A" if n > 1 else f"{ESC}[A"


def cursor_down(n: int = 1) -> str:
    """Move cursor down n rows."""
    return f"{ESC}[{n}B" if n > 1 else f"{ESC}[B"


def cursor_forward(n: int = 1) -> str:
    """Move cursor forward n columns."""
    return f"{ESC}[{n}C" if n > 1 else f"{ESC}[C"


def cursor_back(n: int = 1) -> str:
    """Move cursor back n columns."""
    return f"{ESC}[{n}D" if n > 1 else f"{ESC}[D"


def cursor_position(row: int, col: int) -> str:
    """Move cursor to absolute (row, col) position (1-indexed)."""
    return f"{ESC}[{row};{col}H"


def erase_line(mode: int = 2) -> str:
    """Erase current line. Mode: 0=cursor→end, 1=start→cursor, 2=entire line."""
    return f"{ESC}[{mode}K"


def erase_display(mode: int = 2) -> str:
    """Erase display. Mode: 0=cursor→end, 1=start→cursor, 2=entire screen."""
    return f"{ESC}[{mode}J"


def show_cursor() -> str:
    """Make cursor visible."""
    return f"{ESC}[?25h"


def hide_cursor() -> str:
    """Hide cursor."""
    return f"{ESC}[?25l"


_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences from text.

    Useful for measuring visible text width.
    """
    return _ANSI_RE.sub("", text)


def visible_width(text: str) -> int:
    """Return the visible column width of text (stripping ANSI escapes)."""
    return len(strip_ansi(text))
