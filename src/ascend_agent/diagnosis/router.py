"""Backward-compatible re-export of provider router types.

The ModelRouter and related utilities have moved to
``ascend_agent.providers.router``.  This module is retained so that
existing ``from ascend_agent.diagnosis.router import ...`` call sites
continue to work without changes.

New code should import from ``ascend_agent.providers.router`` directly:
    from ascend_agent.providers.router import ModelRouter, ChatResponse, create_router
"""

import httpx  # noqa: F401  kept for tests that reference diagnosis.router.httpx

from ascend_agent.providers.router import (  # noqa: F401
    PROVIDER_DEFAULTS,
    ChatResponse,
    ModelRouter,
    ProviderConfig,
    _build_http_client,
    _configured_proxy,
    _coerce_plain_text_response,
    _extract_json_object,
    _format_connection_error,
    _json_fallback_instruction,
    _parse_fallback_response,
    _repair_response_data,
    _resolve_provider_config,
    _ssl_verify_config,
    create_router,
)
