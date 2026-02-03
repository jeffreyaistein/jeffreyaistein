"""
Jeffrey AIstein - OpenRouter Provider

Implementation of LLM provider using OpenRouter's OpenAI-compatible API.
Supports models like Rocinante-12B for unfiltered responses.
"""

import json
from typing import AsyncIterator, Optional

import httpx
import structlog

from config import settings
from services.llm.base import BaseLLMProvider, LLMMessage, LLMResponse, StreamChunk


logger = structlog.get_logger()

# OpenRouter API endpoint (OpenAI-compatible)
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


class OpenRouterProvider(BaseLLMProvider):
    """
    OpenRouter LLM provider.

    Uses OpenRouter's OpenAI-compatible API to access various models
    including unfiltered models like Rocinante-12B.
    """

    # Default model - Mistral Nemo for quality unfiltered responses
    DEFAULT_MODEL = "mistralai/mistral-nemo"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        site_url: Optional[str] = None,
        site_name: Optional[str] = None,
    ):
        """
        Initialize the OpenRouter provider.

        Args:
            api_key: OpenRouter API key (defaults to settings)
            model: Model to use (defaults to Rocinante-12B)
            site_url: Your site URL for OpenRouter rankings (optional)
            site_name: Your site name for OpenRouter rankings (optional)
        """
        self._api_key = api_key or settings.openrouter_api_key
        self._model = model or getattr(settings, 'openrouter_model', self.DEFAULT_MODEL)
        self._site_url = site_url or "https://jeffreyaistein.fun"
        self._site_name = site_name or "Jeffrey AIstein"

    @property
    def is_available(self) -> bool:
        """Check if API key is configured."""
        return bool(self._api_key)

    def get_model_name(self) -> str:
        """Return the model identifier."""
        return self._model

    def _get_headers(self) -> dict:
        """Get headers for OpenRouter API requests."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._site_url,
            "X-Title": self._site_name,
        }
        return headers

    def _convert_messages(
        self, messages: list[LLMMessage], system_prompt: Optional[str]
    ) -> list[dict]:
        """
        Convert LLMMessage list to OpenAI chat format.

        OpenAI format includes system messages in the messages array.
        """
        openai_messages = []

        # Add system prompt first if provided
        if system_prompt:
            openai_messages.append({
                "role": "system",
                "content": system_prompt,
            })

        # Add all messages
        for msg in messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        return openai_messages

    async def generate(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a complete response."""
        openai_messages = self._convert_messages(messages, system_prompt)

        payload = {
            "model": self._model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{OPENROUTER_API_BASE}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )

                if response.status_code != 200:
                    error_body = response.text[:500]
                    logger.error(
                        "openrouter_api_error",
                        status=response.status_code,
                        body=error_body,
                    )
                    raise RuntimeError(f"OpenRouter API error: {response.status_code} - {error_body}")

                data = response.json()

                # Extract content from OpenAI format
                content = data["choices"][0]["message"]["content"]
                finish_reason = data["choices"][0].get("finish_reason", "stop")

                # Get usage info
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

                logger.info(
                    "openrouter_response",
                    model=self._model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

                return LLMResponse(
                    content=content,
                    model=data.get("model", self._model),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    finish_reason=finish_reason,
                    metadata={
                        "provider": "openrouter",
                        "id": data.get("id"),
                    },
                )

            except httpx.TimeoutException:
                raise RuntimeError("OpenRouter API timeout")
            except httpx.RequestError as e:
                raise RuntimeError(f"OpenRouter request error: {e}")

    async def stream(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming response."""
        openai_messages = self._convert_messages(messages, system_prompt)

        payload = {
            "model": self._model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{OPENROUTER_API_BASE}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        content = await response.aread()
                        raise RuntimeError(
                            f"OpenRouter API error: {response.status_code} - {content.decode()[:500]}"
                        )

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        # SSE format: data: {...}
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix

                            # Handle stream end
                            if data_str.strip() == "[DONE]":
                                yield StreamChunk(delta="", finish_reason="stop")
                                break

                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])

                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    finish_reason = choices[0].get("finish_reason")

                                    if content:
                                        yield StreamChunk(delta=content)

                                    if finish_reason:
                                        yield StreamChunk(
                                            delta="",
                                            finish_reason=finish_reason,
                                        )
                            except json.JSONDecodeError:
                                # Skip malformed lines
                                continue

            except httpx.TimeoutException:
                yield StreamChunk(delta="", finish_reason="error")
                raise RuntimeError("OpenRouter API timeout")
            except httpx.RequestError as e:
                yield StreamChunk(delta="", finish_reason="error")
                raise RuntimeError(f"OpenRouter request error: {e}")
