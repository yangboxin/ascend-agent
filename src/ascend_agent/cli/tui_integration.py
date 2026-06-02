"""TUI ↔ LLM Integration Layer

Wires the immersive terminal UI to the LLM backend, handling:
- User input → LLM router → streaming response → TUI display
- Slash commands (already handled inside TUI)
- Provider/model resolution
- Error display in the TUI
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ascend_agent.cli.tui.app import AscendTUI
from ascend_agent.cli.tui.components.message_bubble import Message

logger = logging.getLogger(__name__)


def run_tui_with_llm(
    provider: str = "",
    model: str = "",
    history_file: str | None = None,
) -> None:
    """Launch the TUI with LLM backend integration.

    This is the main entry point for the immersive terminal interface.
    It creates the TUI, sets up the streaming callback that sends
    user messages to the LLM and streams responses back.

    Args:
        provider: LLM provider name (e.g., 'openai', 'deepseek').
        model: Model name override (uses config default if empty).
        history_file: Path to command history file.
    """
    # Resolve provider and model
    if not provider:
        provider = _resolve_provider()

    if not model:
        model = _resolve_model(provider)

    # Create the TUI
    tui = AscendTUI(
        provider=provider,
        model=model,
        history_file=history_file,
    )

    # Set up the LLM callback
    tui.set_on_user_input(
        lambda text: _handle_user_input(tui, provider, text)
    )

    # Store reference for Ctrl+C interrupt handling
    _active_tui = tui

    # Launch
    tui.run()


# Module-level reference to the active TUI for interrupt handling
_active_tui: Optional[AscendTUI] = None


def _handle_user_input(tui: AscendTUI, provider: str, text: str) -> None:
    """Handle user text input — send to LLM and stream response.

    Called by the TUI when the user submits non-command text.
    Sends the message to the LLM router and streams the response
    back to the TUI content area.

    Args:
        tui: The active AscendTUI instance.
        provider: LLM provider name.
        text: The user's message text.
    """
    # Build messages from conversation history
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for msg in tui.messages:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})

    # Create router
    try:
        from ascend_agent.diagnosis.router import create_router
        router = create_router(provider=provider)
    except ValueError as e:
        tui.add_message(Message(
            role="system",
            content=f"[red]Error:[/red] {e}\n"
                    f"  Set the required API key or configure via /models add."
        ))
        return

    # Start streaming
    _, stream_buffer = tui.start_stream()
    tui.set_status(streaming=True)

    try:
        # Consume the stream synchronously (the OpenAI SDK stream is sync-iterable)
        stream = router.chat_stream(messages)
        for chunk in stream:
            if tui._interrupted:
                break
            tui.append_to_assistant(chunk)
    except Exception as e:
        logger.exception("LLM stream error")
        tui.add_message(Message(
            role="system",
            content=f"[red]Stream error:[/red] {e}"
        ))
    finally:
        tui.set_status(streaming=False)


_SYSTEM_PROMPT = (
    "You are Ascend Diagnostic Agent, an AI assistant for Ascend NPU development. "
    "Answer concisely and help with debugging, diagnosis, reproduction, and fixes. "
    "Format code blocks with triple backticks and language tags. "
    "Use clear, structured responses."
)


def _resolve_provider() -> str:
    """Resolve the active provider from config."""
    try:
        from ascend_agent.cli.config_manager import ConfigManager
        return ConfigManager().get_active()
    except Exception:
        return "openai"


def _resolve_model(provider: str) -> str:
    """Resolve the active model for a provider."""
    try:
        from ascend_agent.cli.config_manager import ConfigManager
        return ConfigManager().get_active_model()
    except Exception:
        return ""
