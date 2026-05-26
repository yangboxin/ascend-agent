from __future__ import annotations

import json
import logging
import os

from openai import APIStatusError, BadRequestError, OpenAI
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


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


def create_router(provider: str = "openai") -> ModelRouter:
    """Create a configured ModelRouter for the given provider.

    Resolves provider-specific env vars (ASCEND_{PROVIDER}_API_KEY,
    ASCEND_{PROVIDER}_BASE_URL) and constructs a ProviderConfig.

    Default provider "openai" falls back to OPENAI_API_KEY for
    backward compatibility (PROV-04).

    Args:
        provider: Provider name, e.g. "openai" or "deepseek".

    Returns:
        A configured ModelRouter instance.

    Raises:
        ValueError: If required API key is missing.
    """
    prefix = f"ASCEND_{provider.upper()}"
    api_key = os.environ.get(f"{prefix}_API_KEY")
    base_url = os.environ.get(f"{prefix}_BASE_URL")

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
                f"{prefix}_API_KEY is required for provider '{provider}'. "
                f"Set the {prefix}_API_KEY environment variable."
            )

    config = ProviderConfig(
        base_url=base_url or PROVIDER_DEFAULTS.get(provider, {}).get("base_url", "https://api.openai.com/v1"),
        api_key=api_key,
        default_model=os.environ.get(f"{prefix}_DEFAULT_MODEL", PROVIDER_DEFAULTS.get(provider, {}).get("default_model", "gpt-4o")),
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
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = completion.choices[0].message.content
            if not content:
                raise ValueError(
                    f"Empty response from provider (model={self._model}). "
                    "Cannot parse structured output."
                )
            return response_model.model_validate_json(content)

    def __repr__(self) -> str:
        return f"ModelRouter(model={self._model!r})"
