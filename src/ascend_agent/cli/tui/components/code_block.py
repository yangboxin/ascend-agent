"""Code block component — syntax-highlighted code display.

Leverages Pygments for syntax highlighting when available, with a
fallback to plain text display. Supports expand/collapse for long blocks.
"""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.formatted_text import FormattedText


@dataclass
class CodeBlock:
    """A code block with optional language for syntax highlighting.

    Attributes:
        code: The code text.
        language: Programming language identifier (e.g., 'python', 'typescript').
        is_expanded: Whether the block is fully expanded (vs collapsed).
        line_offset: Starting line number for display.
    """
    code: str
    language: str = ""
    is_expanded: bool = True
    line_offset: int = 1

    @property
    def line_count(self) -> int:
        return self.code.count("\n") + 1

    @property
    def collapsed_preview_lines(self) -> int:
        """Number of lines to show when collapsed."""
        return 4


def highlight_code(code: str, language: str = "") -> FormattedText:
    """Apply syntax highlighting to a code block.

    Uses Pygments if installed; otherwise falls back to plain text
    with a subtle color.

    Args:
        code: Raw code text.
        language: Language identifier for Pygments lexer selection.

    Returns:
        FormattedText with syntax highlighting applied.
    """
    segments: list[tuple[str, str]] = []

    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name, guess_lexer
        from pygments.formatters import Terminal256Formatter

        try:
            lexer = get_lexer_by_name(language) if language else guess_lexer(code)
        except Exception:
            lexer = guess_lexer(code)

        style = "monokai"  # Dark-friendly, readable in terminals
        highlighted = highlight(code, lexer, Terminal256Formatter(style=style))

        # Remove trailing newline from pygments output
        if highlighted.endswith("\n"):
            highlighted = highlighted[:-1]

        # Parse into (style, text) segments — for now, return as single styled segment
        # since Pygments output is already ANSI-encoded
        for line in highlighted.split("\n"):
            segments.append(("fg:#839496", line))
            segments.append(("", "\n"))

    except ImportError:
        # Pygments not available — use plain text with subtle coloring
        for line in code.split("\n"):
            segments.append(("fg:#839496", line))
            segments.append(("", "\n"))

    if segments and segments[-1] == ("", "\n"):
        segments.pop()

    return FormattedText(segments)


def format_code_block(
    code: str,
    language: str = "",
    line_numbers: bool = True,
    max_lines: int | None = None,
) -> FormattedText:
    """Format a code block for terminal display.

    Args:
        code: The code text.
        language: Language for syntax highlighting.
        line_numbers: Whether to show line numbers.
        max_lines: Truncate display after this many lines (None = no limit).

    Returns:
        FormattedText with borders, optional line numbers, and highlighting.
    """
    lines = code.split("\n")
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True
    else:
        truncated = False

    segments: list[tuple[str, str]] = []

    # Top border with language label
    lang_label = f" {language} " if language else " code "
    segments.append(("fg:#586e75", f"┌─{lang_label}{'─' * 40}┐\n"))

    # Code lines
    for i, line in enumerate(lines, start=1):
        segments.append(("fg:#586e75", "│ "))

        if line_numbers:
            num = f"{i:3d} "
            segments.append(("fg:#586e75 dim", num))

        highlighted = highlight_code(line, language)
        # Extract the actual styled content from the line
        segments.append(("fg:#839496", line))
        segments.append(("", " " * max(0, 60 - len(line))))
        segments.append(("fg:#586e75", "│\n"))

    if truncated:
        segments.append(("fg:#586e75", f"│ ... ({len(code.split(chr(10))) - max_lines} more lines) ...\n"))

    # Bottom border
    segments.append(("fg:#586e75", "└" + "─" * 48 + "┘\n"))

    return FormattedText(segments)


def detect_language(code: str) -> str:
    """Heuristically detect the language of a code block.

    Args:
        code: The code text.

    Returns:
        Language identifier string, or empty string.
    """
    # Simple heuristics based on common syntax patterns
    first_line = code.strip().split("\n")[0] if code.strip() else ""

    if first_line.startswith("#!/usr/bin/env python") or first_line.startswith("#!/usr/bin/python"):
        return "python"
    if first_line.startswith("#!/usr/bin/env node") or first_line.startswith("//"):
        return "javascript"
    if first_line.startswith("#!/usr/bin/env bash") or first_line.startswith("#!"):
        return "bash"
    if first_line.startswith("def ") or first_line.startswith("class ") or "import " in first_line:
        return "python"
    if first_line.startswith("function ") or first_line.startswith("const ") or first_line.startswith("let "):
        return "javascript"
    if first_line.startswith("package ") or "func " in first_line:
        return "go"
    if first_line.startswith("use ") or first_line.startswith("fn ") or first_line.startswith("impl "):
        return "rust"
    if first_line.startswith("<") and first_line.endswith(">"):
        return "html"

    return ""
