"""SSE chat server for the Node.js TUI frontend.

Provides a lightweight HTTP+SSE endpoint that the Ink+React TUI
connects to for streaming LLM responses.

Usage:
    python -m ascend_agent.cli.tui_server [--port 9020] [--provider openai]

    # Then launch the TUI in another terminal:
    asd --server http://localhost:9020
"""

from __future__ import annotations

import json
import logging
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from typing import Optional

logger = logging.getLogger(__name__)


class SSEChatHandler(BaseHTTPRequestHandler):
    """HTTP handler providing SSE streaming chat endpoints.

    Endpoints:
      POST /chat/stream  — Streaming chat (SSE)
      POST /chat         — Non-streaming chat (JSON response)
      GET  /health       — Health check
    """

    router: Optional[object] = None  # ModelRouter instance (set by server factory)
    messages: list[dict] = []  # Conversation history

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/chat/stream":
            self._handle_chat_stream()
        elif parsed.path == "/chat":
            self._handle_chat_sync()
        else:
            self.send_error(404, "Not found")

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_error(404, "Not found")

    def do_OPTIONS(self) -> None:
        """CORS preflight."""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    # ---- internals ----

    def _handle_chat_stream(self) -> None:
        """POST /chat/stream — SSE streaming response."""
        try:
            body = self._read_body()
        except Exception:
            self.send_error(400, "Invalid JSON body")
            return

        message = body.get("message", "")
        history = body.get("history", [])
        provider = body.get("provider", "")

        if not message:
            self.send_error(400, "Missing 'message' field")
            return

        # Build messages
        msgs = [{"role": "system", "content": _SYSTEM_PROMPT}]
        msgs.extend(history)
        msgs.append({"role": "user", "content": message})

        # Ensure we have a router
        if self.router is None:
            try:
                from ascend_agent.diagnosis.router import create_router
                self.__class__.router = create_router(provider=provider or "openai")
            except Exception as e:
                self.send_error(500, str(e))
                return

        # Set up SSE response
        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            stream = self.router.chat_stream(msgs)
            for chunk in stream:
                data = json.dumps({"content": chunk}, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception as e:
            error_data = json.dumps({"error": str(e)})
            self.wfile.write(f"data: {error_data}\n\n".encode())
            self.wfile.flush()

    def _handle_chat_sync(self) -> None:
        """POST /chat — non-streaming JSON response."""
        try:
            body = self._read_body()
        except Exception:
            self.send_error(400, "Invalid JSON body")
            return

        message = body.get("message", "")
        history = body.get("history", [])

        if not message:
            self.send_error(400, "Missing 'message' field")
            return

        msgs = [{"role": "system", "content": _SYSTEM_PROMPT}]
        msgs.extend(history)
        msgs.append({"role": "user", "content": message})

        if self.router is None:
            from ascend_agent.diagnosis.router import create_router
            self.__class__.router = create_router(provider=body.get("provider", "openai"))

        try:
            content = self.router.chat(msgs)
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"content": content}).encode())
        except Exception as e:
            self.send_error(500, str(e))

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        """Suppress default stderr logging; use our logger instead."""
        logger.debug("HTTP %s", args[0] if args else "")


_SYSTEM_PROMPT = (
    "You are Ascend Diagnostic Agent. "
    "Answer concisely and help with debugging, diagnosis, reproduction, and fixes. "
    "Format code blocks with triple backticks and language tags."
)


def run_server(port: int = 9020, provider: str = "openai") -> None:
    """Start the SSE chat server.

    Args:
        port: TCP port to listen on.
        provider: LLM provider to use.
    """
    # Pre-warm the router
    try:
        from ascend_agent.diagnosis.router import create_router
        SSEChatHandler.router = create_router(provider=provider)
        logger.info("Router initialized (provider=%s)", provider)
    except Exception as e:
        logger.warning("Router not initialized: %s. Will init on first request.", e)

    server = HTTPServer(("127.0.0.1", port), SSEChatHandler)
    print(f"✨ Ascend TUI chat server listening on http://127.0.0.1:{port}")
    print(f"   Endpoints:")
    print(f"     POST /chat/stream  — SSE streaming chat")
    print(f"     POST /chat         — JSON chat")
    print(f"     GET  /health       — Health check")
    print(f"")
    print(f"   Launch the TUI with:")
    print(f"     asd --server http://127.0.0.1:{port}")
    print(f"")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ascend TUI chat server")
    parser.add_argument("--port", type=int, default=9020)
    parser.add_argument("--provider", default="openai")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    run_server(port=args.port, provider=args.provider)
