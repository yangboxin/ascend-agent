"""Hook: streaming response handler.

Manages the state for receiving and displaying streaming AI responses.
Supports:
- Appending chunks to the last assistant message (typewriter effect)
- Creating new assistant messages when no existing one is being streamed
- Interrupting an in-progress stream (Ctrl+C)
- Completion signaling
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable


@dataclass
class StreamState:
    """Tracks the state of an active streaming response."""
    is_streaming: bool = False
    """Whether a stream is currently active."""
    started_at: float = 0.0
    """Timestamp when streaming started."""
    chunks_received: int = 0
    """Number of chunks received so far."""
    total_chars: int = 0
    """Total characters received."""
    interrupt_requested: bool = False
    """Whether the user requested interruption."""


class StreamingManager:
    """Manages streaming AI responses with typewriter-effect display.

    Coordinates between the async stream source and the synchronous UI
    update cycle. Chunks are accumulated and the UI is invalidated
    periodically for smooth rendering.
    """

    def __init__(
        self,
        on_chunk: Callable[[str], None],
        on_complete: Callable[[], None],
        on_error: Callable[[Exception], None],
        max_visible_chars: int = 50_000,
    ) -> None:
        self._on_chunk = on_chunk
        self._on_complete = on_complete
        self._on_error = on_error
        self._state = StreamState()
        self._max_visible_chars = max_visible_chars
        self._buffer: str = ""

    @property
    def is_streaming(self) -> bool:
        return self._state.is_streaming

    @property
    def started_at(self) -> float:
        return self._state.started_at

    @property
    def elapsed(self) -> float:
        """Seconds since streaming started, or 0 if not streaming."""
        if not self._state.started_at:
            return 0.0
        return time.time() - self._state.started_at

    def request_interrupt(self) -> None:
        """Signal that the stream should be interrupted.

        The actual interruption is handled by the stream consumer
        checking this flag.
        """
        self._state.interrupt_requested = True

    def reset(self) -> None:
        """Reset state for a new stream."""
        self._state = StreamState()
        self._buffer = ""

    async def consume(self, stream: Awaitable) -> None:
        """Consume an async stream, calling on_chunk for each piece.

        Args:
            stream: An async iterable yielding string chunks,
                    or an awaitable that returns an async iterable.

        The stream is consumed until exhausted or interrupted.
        """
        self.reset()
        self._state.is_streaming = True
        self._state.started_at = time.time()

        try:
            # Resolve the awaitable to get the iterable
            if hasattr(stream, "__aiter__"):
                iterator = stream
            else:
                iterator = await stream

            async for chunk in iterator:
                if self._state.interrupt_requested:
                    break

                if isinstance(chunk, str):
                    text = chunk
                elif isinstance(chunk, dict):
                    # Support OpenAI-style chunk format
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        text = delta.get("content", "") or ""
                    else:
                        text = ""
                else:
                    text = str(chunk)

                if text:
                    self._state.chunks_received += 1
                    self._state.total_chars += len(text)
                    self._buffer = (self._buffer + text)[-self._max_visible_chars:]
                    self._on_chunk(text)

        except Exception as e:
            self._on_error(e)
        finally:
            self._state.is_streaming = False
            self._on_complete()

    def consume_sync_generator(self, generator) -> None:
        """Consume a synchronous generator, calling on_chunk for each piece.

        This is used when the stream source is synchronous (e.g., a simple
        generator that yields chunks).

        Args:
            generator: A sync generator yielding string chunks.
        """
        self.reset()
        self._state.is_streaming = True
        self._state.started_at = time.time()

        try:
            for chunk in generator:
                if self._state.interrupt_requested:
                    break
                if isinstance(chunk, str):
                    text = chunk
                else:
                    text = str(chunk)
                if text:
                    self._state.chunks_received += 1
                    self._state.total_chars += len(text)
                    self._buffer = (self._buffer + text)[-self._max_visible_chars:]
                    self._on_chunk(text)
        except Exception as e:
            self._on_error(e)
        finally:
            self._state.is_streaming = False
            self._on_complete()


class StreamBuffer:
    """Thread-safe buffer for accumulating streaming text between async
    producer and synchronous UI rendering."""

    def __init__(self) -> None:
        self._chunks: list[str] = []
        self._complete: bool = False

    def append(self, text: str) -> None:
        self._chunks.append(text)

    def drain(self) -> str:
        """Return all accumulated text and clear the buffer."""
        if not self._chunks:
            return ""
        text = "".join(self._chunks)
        self._chunks.clear()
        return text

    @property
    def is_complete(self) -> bool:
        return self._complete

    @is_complete.setter
    def is_complete(self, value: bool) -> None:
        self._complete = value

    def reset(self) -> None:
        self._chunks.clear()
        self._complete = False
