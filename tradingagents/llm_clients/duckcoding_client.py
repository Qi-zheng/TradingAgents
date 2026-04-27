import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model

DUCKCODING_BASE_URL = "https://www.duckcoding.ai/v1"


class NormalizedDuckCodingChatOpenAI(ChatOpenAI):
    """DuckCoding ChatOpenAI wrapper with normalized output content."""

    def invoke(self, input, config=None, **kwargs):  # noqa: A002
        return normalize_content(super().invoke(input, config, **kwargs))


class DuckCodingClient(BaseLLMClient):
    """Native DuckCoding client using OpenAI-compatible chat completions."""

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, base_url, **kwargs)
        self.provider = "duckcoding"

    def get_llm(self) -> Any:
        self.warn_if_unknown_model()
        api_key = (
            self.kwargs.get("api_key")
            or os.getenv("DUCKCODING_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )

        llm_kwargs = {
            "model": self.model,
            "base_url": self.base_url or DUCKCODING_BASE_URL,
            "api_key": api_key,
        }

        for key in ("timeout", "max_retries", "callbacks", "http_client", "http_async_client"):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        # Do not enable Responses API for DuckCoding; use chat completions only.
        return NormalizedDuckCodingChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        return validate_model(self.provider, self.model)
