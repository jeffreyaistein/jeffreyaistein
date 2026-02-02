"""
Jeffrey AIstein - Anthropic Claude Provider

Implementation of LLM provider using Anthropic's Claude API.
"""

import asyncio
from typing import AsyncIterator, Optional

from anthropic import AsyncAnthropic, APIError

from config import settings
from services.llm.base import BaseLLMProvider, LLMMessage, LLMResponse, StreamChunk


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude LLM provider.

    Supports Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku.
    """

    # Default model - Claude 3.5 Sonnet for best quality/speed balance
    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the Anthropic provider.

        Args:
            api_key: Anthropic API key (defaults to settings)
            model: Model to use (defaults to Claude 3.5 Sonnet)
        """
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or self.DEFAULT_MODEL
        self._client: Optional[AsyncAnthropic] = None

    @property
    def client(self) -> AsyncAnthropic:
        """Lazy-initialize the Anthropic client."""
        if self._client is None:
            if not self._api_key:
                raise ValueError("Anthropic API key not configured")
            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    @property
    def is_available(self) -> bool:
        """Check if API key is configured."""
        return bool(self._api_key)

    def get_model_name(self) -> str:
        """Return the model identifier."""
        return self._model

    def _convert_messages(
        self, messages: list[LLMMessage], system_prompt: Optional[str]
    ) -> tuple[str, list[dict]]:
        """
        Convert LLMMessage list to Anthropic format.

        Anthropic expects system prompt separate from messages,
        and messages should alternate user/assistant.
        """
        system = system_prompt or ""

        # Extract any system messages and append to system prompt
        anthropic_messages = []
        for msg in messages:
            if msg.role == "system":
                system = f"{system}\n\n{msg.content}".strip()
            else:
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        return system, anthropic_messages

    async def generate(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a complete response."""
        system, anthropic_messages = self._convert_messages(messages, system_prompt)

        try:
            response = await self.client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system if system else None,
                messages=anthropic_messages,
            )

            # Extract content (handle text blocks)
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            return LLMResponse(
                content=content,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                finish_reason=response.stop_reason or "stop",
                metadata={
                    "provider": "anthropic",
                    "id": response.id,
                },
            )

        except APIError as e:
            raise RuntimeError(f"Anthropic API error: {e}") from e

    async def stream(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming response."""
        system, anthropic_messages = self._convert_messages(messages, system_prompt)

        try:
            async with self.client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system if system else None,
                messages=anthropic_messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield StreamChunk(delta=text)

                # Final chunk with finish reason
                final_message = await stream.get_final_message()
                yield StreamChunk(
                    delta="",
                    finish_reason=final_message.stop_reason or "stop",
                )

        except APIError as e:
            yield StreamChunk(delta="", finish_reason="error")
            raise RuntimeError(f"Anthropic API error: {e}") from e
