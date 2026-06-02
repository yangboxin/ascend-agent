"""Status line component — displays session info at the top or bottom.

Shows contextual information like:
- Current provider and model
- Token usage / cost
- Streaming status
- Elapsed time
- Keyboard shortcut hints
"""

from __future__ import annotations

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import Window
from prompt_toolkit.layout.controls import FormattedTextControl


class StatusLine:
    """A single-line status bar showing session context.

    Designed to be used either at the top or just above the input bar.
    """

    def __init__(self) -> None:
        self._provider: str = ""
        self._model: str = ""
        self._mode: str = "chat"
        self._is_streaming: bool = False
        self._token_count: int = 0
        self._elapsed: float = 0.0
        self._width: int = 80

    # ---- setters ----

    def set_provider(self, provider: str) -> None:
        self._provider = provider

    def set_model(self, model: str) -> None:
        self._model = model

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def set_streaming(self, is_streaming: bool) -> None:
        self._is_streaming = is_streaming

    def set_token_count(self, count: int) -> None:
        self._token_count = count

    def set_elapsed(self, seconds: float) -> None:
        self._elapsed = seconds

    def set_width(self, width: int) -> None:
        self._width = width

    # ---- rendering ----

    def render(self) -> FormattedText:
        """Build the status line as FormattedText.

        Layout (adapts to width):
        ┌──────────────────────────────────────────────────────────────┐
        │ ascend  provider:openai  model:claude-sonnet-4-6  streaming ⣾  1.2s │
        └──────────────────────────────────────────────────────────────┘
        """
        segments: list[tuple[str, str]] = []

        # Background bar
        segments.append(("bg:#073642 fg:#839496", " "))

        # Left section: brand + provider + model
        segments.append(("bg:#073642 fg:#b58900 bold", "ascend"))
        segments.append(("bg:#073642 fg:#657b83", " │ "))

        if self._provider:
            segments.append(("bg:#073642 fg:#2aa198", f"provider:{self._provider}"))
            segments.append(("bg:#073642 fg:#657b83", "  "))

        if self._model:
            segments.append(("bg:#073642 fg:#268bd2", f"model:{self._model}"))
            segments.append(("bg:#073642 fg:#657b83", "  "))

        # Streaming indicator
        if self._is_streaming:
            segments.append(("bg:#073642 fg:#859900", "streaming ⣾"))
            segments.append(("bg:#073642 fg:#657b83", "  "))

        if self._elapsed > 0:
            segments.append(("bg:#073642 fg:#6c71c4", f"{self._elapsed:.1f}s"))
            segments.append(("bg:#073642 fg:#657b83", "  "))

        # Right section: token count and keyboard hints (pushed right)
        right_items: list[str] = []
        if self._token_count > 0:
            right_items.append(f"tokens:{self._token_count:,}")
        right_items.append("Ctrl+C:interrupt  Ctrl+D:quit  /help")

        right_text = "  ".join(right_items)
        # Calculate padding
        left_len = self._calculate_visible_length(segments)
        padding = max(1, self._width - left_len - len(right_text) - 1)
        segments.append(("bg:#073642", " " * padding))
        segments.append(("bg:#073642 fg:#586e75", right_text))

        segments.append(("bg:#073642 fg:#839496", " "))

        return FormattedText(segments)

    def _calculate_visible_length(self, segments: list[tuple[str, str]]) -> int:
        """Approximate the visible width of rendered segments."""
        total = 0
        for _, text in segments:
            # Strip ANSI escapes if any
            total += len(text.replace("\x1b", "").split("m")[-1] if "\x1b" in text else text)
        return total

    # ---- layout ----

    def create_window(self) -> Window:
        """Create a prompt_toolkit Window for this status line."""
        control = FormattedTextControl(
            text=lambda: self.render(),
            focusable=False,
        )
        return Window(
            content=control,
            height=1,
            style="bg:#073642",
        )


def create_status_window(status_line: StatusLine) -> Window:
    """Factory: create the status line window.

    Args:
        status_line: The StatusLine instance.

    Returns:
        A Window configured for single-line display.
    """
    return status_line.create_window()
