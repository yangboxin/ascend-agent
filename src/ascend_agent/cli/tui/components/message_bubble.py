"""Message bubble component — renders a single chat message.

Handles both user messages and assistant (AI) messages with
Markdown rendering for assistant responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from prompt_toolkit.formatted_text import FormattedText


@dataclass
class Message:
    """A single message in the conversation.

    Attributes:
        role: 'user', 'assistant', or 'system'.
        content: The message text (may contain Markdown for assistant messages).
        timestamp: When the message was created (epoch seconds).
        id: Unique identifier for React-like list rendering.
    """
    role: str
    content: str
    timestamp: float = 0.0
    id: str = ""

    def __post_init__(self):
        import time
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.id:
            import uuid
            self.id = uuid.uuid4().hex[:8]

    @property
    def is_user(self) -> bool:
        return self.role == "user"

    @property
    def is_assistant(self) -> bool:
        return self.role == "assistant"

    @property
    def is_system(self) -> bool:
        return self.role == "system"


def format_message(message: Message, width: int = 80) -> FormattedText:
    """Format a single message into styled prompt_toolkit FormattedText.

    User messages: green prefix, plain text.
    Assistant messages: blue prefix, Markdown-rendered content.
    System messages: dim yellow prefix, italic text.

    Args:
        message: The message to format.
        width: Terminal width for wrapping context.

    Returns:
        FormattedText ready for display in a Window.
    """
    from ascend_agent.cli.tui.utils.markdown import render_markdown

    segments: list[tuple[str, str]] = []

    if message.is_user:
        segments.append(("bold fg:green", "\n> "))
        segments.append(("fg:green", message.content))
        segments.append(("", "\n"))

    elif message.is_assistant:
        # Try to render as Markdown; fall back to plain text
        segments.append(("bold fg:blue", "\n🤖 "))
        try:
            md = render_markdown(message.content, width)
            segments.extend(md)
        except Exception:
            segments.append(("fg:blue", message.content))
        segments.append(("", "\n"))

    elif message.is_system:
        segments.append(("italic fg:yellow dim", f"\n[SYS] {message.content}\n"))

    else:
        segments.append(("", f"\n{message.content}\n"))

    return FormattedText(segments)


def format_messages(messages: list[Message], width: int = 80) -> FormattedText:
    """Format a list of messages into a single FormattedText for the content window.

    Each message is formatted separately and concatenated.

    Args:
        messages: List of messages to display.
        width: Terminal width for formatting context.

    Returns:
        Combined FormattedText.
    """
    segments: list[tuple[str, str]] = []
    for msg in messages:
        formatted = format_message(msg, width)
        segments.extend(formatted)
    return FormattedText(segments)
