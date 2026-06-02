"""Markdown-to-terminal renderer.

Converts Markdown text into prompt_toolkit FormattedText for display
in the terminal. Handles code blocks, bold, italic, lists, etc.
"""

from __future__ import annotations

import re
from typing import List

from prompt_toolkit.formatted_text import FormattedText


# Rudimentary Markdown parsing — handles the most common cases for AI output.
# A full CommonMark parser would be more correct but heavier; this is
# sufficient for typical LLM responses (headings, bold, code, lists, paragraphs).

_BLOCK_FENCE = re.compile(r"^```(\w*)$")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"\*(.+?)\*")
_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
_UNORDERED_LIST = re.compile(r"^(\s*)[-*+]\s+(.+)$")
_ORDERED_LIST = re.compile(r"^(\s*)\d+\.\s+(.+)$")
_BLOCKQUOTE = re.compile(r"^>\s?(.*)$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def render_markdown(text: str, width: int = 80) -> FormattedText:
    """Convert a Markdown string into prompt_toolkit FormattedText.

    Args:
        text: Raw Markdown text (may contain multiple paragraphs).
        width: Terminal width for wrapping (placeholder; prompt_toolkit handles wrapping).

    Returns:
        FormattedText suitable for display in a prompt_toolkit Window.
    """
    result: list[tuple[str, str]] = []
    in_fence = False
    fence_lang = ""

    for raw_line in text.split("\n"):
        line: str = raw_line

        # Handle fenced code blocks
        m = _BLOCK_FENCE.match(line)
        if m:
            if not in_fence:
                in_fence = True
                fence_lang = m.group(1) or ""
                continue
            else:
                in_fence = False
                fence_lang = ""
                continue

        if in_fence:
            style = "fg:#839496"  # Solarized base0 — subtle code color
            result.append((style, line))
            result.append(("", "\n"))
            continue

        # Blockquote
        bq = _BLOCKQUOTE.match(line)
        if bq:
            result.append(("fg:#586e75", "│ " + bq.group(1)))
            result.append(("", "\n"))
            continue

        # Heading
        h = _HEADING.match(line)
        if h:
            level = len(h.group(1))
            if level == 1:
                result.append(("bold fg:#268bd2", h.group(2)))
            elif level == 2:
                result.append(("bold fg:#2aa198", h.group(2)))
            else:
                result.append(("bold fg:#859900", h.group(2)))
            result.append(("", "\n"))
            continue

        # Unordered list
        ul = _UNORDERED_LIST.match(line)
        if ul:
            indent = ul.group(1)
            result.append(("", indent + "  • "))
            _append_inline_styled(result, ul.group(2))
            result.append(("", "\n"))
            continue

        # Ordered list
        ol = _ORDERED_LIST.match(line)
        if ol:
            indent = ol.group(1)
            result.append(("", indent + "  "))
            _append_inline_styled(result, ol.group(2))
            result.append(("", "\n"))
            continue

        # Regular paragraph line — apply inline styles
        if line.strip():
            _append_inline_styled(result, line)
        result.append(("", "\n"))

    return FormattedText(result)


def _append_inline_styled(result: list[tuple[str, str]], text: str) -> None:
    """Parse inline formatting (bold, italic, code, links) and append styled fragments."""
    # This is a simple regex-based parser — works for typical LLM output.
    remaining = text
    while remaining:
        # Try each inline pattern
        bold_match = _BOLD.search(remaining)
        italic_match = _ITALIC.search(remaining)
        code_match = _INLINE_CODE.search(remaining)
        link_match = _LINK.search(remaining)

        # Find the earliest match
        matches: list[tuple[int, int, str, str]] = []
        if bold_match:
            matches.append((bold_match.start(), bold_match.end(), "bold", bold_match.group(1)))
        if italic_match:
            matches.append((italic_match.start(), italic_match.end(), "italic", italic_match.group(1)))
        if code_match:
            matches.append((code_match.start(), code_match.end(), "fg:#b58900 bg:#002b36", code_match.group(1)))
        if link_match:
            matches.append((link_match.start(), link_match.end(), "fg:#268bd2 underline", link_match.group(1)))

        if not matches:
            result.append(("", remaining))
            break

        # Sort by start position
        matches.sort(key=lambda m: m[0])
        start, end, style, content = matches[0]

        # Append text before the match
        if start > 0:
            result.append(("", remaining[:start]))

        result.append((style, content))
        remaining = remaining[end:]
