from __future__ import annotations

import json
import logging
import os
import re

from openai import APIStatusError, BadRequestError, OpenAI
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


def _json_fallback_instruction(response_model: type[BaseModel]) -> str:
    schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
    return (
        "Return only one valid JSON object that conforms to this JSON schema. "
        "Do not include markdown fences, prose, or a bare word response.\n"
        f"JSON schema: {schema}"
    )


def _extract_json_object(content: str) -> str | None:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)

    decoder = json.JSONDecoder()
    for idx, char in enumerate(stripped):
        if char not in "[{":
            continue
        try:
            _, end = decoder.raw_decode(stripped[idx:])
        except json.JSONDecodeError:
            continue
        return stripped[idx : idx + end]
    return None


def _coerce_plain_text_response(
    response_model: type[BaseModel], content: str
) -> BaseModel | None:
    """Handle common non-JSON fallback responses for simple router decisions."""
    if response_model.__name__ != "SearchDecision":
        if response_model.__name__ == "DiagnosisResult":
            stripped = content.strip()
            if stripped.lower().startswith("search"):
                return response_model.model_validate(
                    {
                        "hypotheses": [],
                        "errors": [
                            {
                                "stage": "hypothesis_generation",
                                "reason": (
                                    "Provider returned a search request instead "
                                    "of a diagnosis result."
                                ),
                                "details": stripped,
                            }
                        ],
                        "iterations_used": 0,
                    }
                )
        return None

    stripped = content.strip()
    lowered = stripped.lower()
    if not lowered.startswith(("search", "hypothesize")):
        return None

    action = "hypothesize" if lowered.startswith("hypothesize") else "search"
    data: dict[str, object] = {
        "action": action,
        "searches": [],
        "reasoning": "Provider returned a plain-text decision.",
    }

    if action == "search":
        pattern_match = re.search(
            r"(?:pattern|query)\s*:\s*[\"']?([^\"'\n]+)",
            stripped,
            flags=re.IGNORECASE,
        )
        if pattern_match:
            data["searches"] = [
                {
                    "pattern": pattern_match.group(1).strip(),
                    "rationale": "Provider returned a plain-text search pattern.",
                }
            ]

    return response_model.model_validate(data)


def _parse_fallback_response(
    response_model: type[BaseModel], content: str
) -> BaseModel:
    json_content = _extract_json_object(content)
    if json_content is not None:
        return response_model.model_validate_json(json_content)

    coerced = _coerce_plain_text_response(response_model, content)
    if coerced is not None:
        return coerced

    return response_model.model_validate_json(content)


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider (OpenAI-compatible API)."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(description="Base URL for the OpenAI-compatible API endpoint")
    api_key: str = Field(description="API key for this provider")
    default_model: str = Field(description="Default model name for this provider")


PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {"base_url": "https://api.openai.com/v1", "default_model": "gpt-4o"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "default_model": "deepseek-v4-flash"},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "default_model": "qwen-turbo"},
}


def _resolve_provider_config(provider: str) -> tuple[str, str, str]:
    """Resolve base_url, api_key, default_model for a provider.
    
    Priority: env vars > config file > built-in defaults.
    Returns (base_url, api_key, default_model).
    """
    prefix = f"ASCEND_{provider.upper()}"

    api_key = os.environ.get(f"{prefix}_API_KEY")
    base_url = os.environ.get(f"{prefix}_BASE_URL")
    default_model = os.environ.get(f"{prefix}_DEFAULT_MODEL")

    # Fill gaps from config file
    if not api_key or not base_url or not default_model:
        try:
            from ascend_agent.cli.config_manager import ConfigManager
            pc = ConfigManager().get_provider(provider)
            if pc:
                api_key = api_key or pc.api_key or None
                base_url = base_url or pc.base_url
                default_model = default_model or pc.default_model
        except Exception:
            pass

    # Fall back to built-in defaults
    builtin = PROVIDER_DEFAULTS.get(provider, {})
    base_url = base_url or builtin.get("base_url", "https://api.openai.com/v1")
    default_model = default_model or builtin.get("default_model", "gpt-4o")

    return base_url, api_key or None, default_model


def create_router(provider: str = "openai") -> ModelRouter:
    """Create a configured ModelRouter for the given provider.

    Resolves provider config from (in priority order):
      1. Environment variables (ASCEND_{PROVIDER}_*)
      2. Config file (~/.config/ascend-agent/providers.json)
      3. Built-in defaults

    Default provider "openai" falls back to OPENAI_API_KEY for
    backward compatibility (PROV-04).

    Args:
        provider: Provider name, e.g. "openai" or "deepseek".

    Returns:
        A configured ModelRouter instance.

    Raises:
        ValueError: If required API key is missing.
    """
    base_url, api_key, default_model = _resolve_provider_config(provider)

    if provider == "openai":
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "ASCEND_OPENAI_API_KEY or OPENAI_API_KEY is required. "
                "Set one of these environment variables."
            )
    else:
        if not api_key:
            raise ValueError(
                f"ASCEND_{provider.upper()}_API_KEY is required for provider '{provider}'. "
                f"Set the ASCEND_{provider.upper()}_API_KEY environment variable "
                "or configure the provider via /models add."
            )

    config = ProviderConfig(
        base_url=base_url,
        api_key=api_key,
        default_model=default_model,
    )
    return ModelRouter(config=config)


class ModelRouter:
    """Thin wrapper around the LLM client for diagnosis calls.

    Validates API key on construction, uses OpenAI structured outputs
    via .parse() with Pydantic response_format.
    """

    _DEFAULT_MODEL = "gpt-4o"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        config: ProviderConfig | None = None,
    ):
        if config is not None:
            # New code path: use ProviderConfig
            self._client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
            )
            self._model = config.default_model
        else:
            # Backward-compatible code path (deprecated)
            api_key = api_key or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required for diagnosis. "
                    "Set the OPENAI_API_KEY environment variable."
                )
            self._client = OpenAI(api_key=api_key)
            self._model = model or os.environ.get(
                "ASCEND_DIAGNOSIS_MODEL", self._DEFAULT_MODEL
            )
        logger.info("ModelRouter initialized (model: %s)", self._model)

    def completion(
        self,
        messages: list[dict],
        response_model: type[BaseModel],
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> BaseModel:
        """Send messages and return structured response.

        Args:
            messages: Chat messages in OpenAI format.
            response_model: Pydantic model class for structured output.
            max_tokens: Maximum tokens in the response (default 4096).
            temperature: Sampling temperature (default 0.1).

        Returns:
            Parsed Pydantic model instance of the response_model type.
        """
        try:
            completion = self._client.chat.completions.parse(
                model=self._model,
                messages=messages,
                response_format=response_model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return completion.choices[0].message.parsed
        except (APIStatusError, BadRequestError) as e:
            if e.status_code != 400:
                raise
            logger.warning(
                "Structured output not supported by provider (model=%s, status=%d). "
                "Falling back to manual JSON parsing.",
                self._model,
                e.status_code,
            )
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=messages
                + [
                    {
                        "role": "user",
                        "content": _json_fallback_instruction(response_model),
                    }
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = completion.choices[0].message.content
            if not content:
                raise ValueError(
                    f"Empty response from provider (model={self._model}). "
                    "Cannot parse structured output."
                )
            return _parse_fallback_response(response_model, content)

    def chat(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
        """Send an unstructured chat request to the active provider."""
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = completion.choices[0].message.content
        if content is None:
            return ""
        return content

    def __repr__(self) -> str:
        return f"ModelRouter(model={self._model!r})"
