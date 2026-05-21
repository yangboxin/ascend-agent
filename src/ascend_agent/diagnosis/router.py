import logging
import os

from openai import OpenAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ModelRouter:
    """Thin wrapper around the LLM client for diagnosis calls.

    Validates API key on construction, uses OpenAI structured outputs
    via .parse() with Pydantic response_format.
    """

    _DEFAULT_MODEL = "gpt-4o"

    def __init__(self, model: str | None = None, api_key: str | None = None):
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
        completion = self._client.chat.completions.parse(
            model=self._model,
            messages=messages,
            response_format=response_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return completion.choices[0].message.parsed

    def __repr__(self) -> str:
        return f"ModelRouter(model={self._model!r})"
