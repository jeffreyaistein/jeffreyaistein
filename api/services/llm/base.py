"""
Jeffrey AIstein - LLM Provider Base Interface

Abstract base class for LLM providers with streaming support.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


@dataclass
class LLMMessage:
    """A message in the conversation."""
    role: str  # system, user, assistant
    content: str


@dataclass
class StreamChunk:
    """A chunk of streamed response."""
    delta: str  # The text delta
    finish_reason: Optional[str] = None  # None, "stop", "max_tokens", "error"


@dataclass
class LLMResponse:
    """Complete LLM response (non-streaming)."""
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "stop"
    metadata: dict = field(default_factory=dict)


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers must implement:
    - generate(): Non-streaming generation
    - stream(): Streaming generation
    - get_model_name(): Return the model identifier
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """
        Generate a complete response (non-streaming).

        Args:
            messages: List of conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            system_prompt: Optional system prompt

        Returns:
            LLMResponse with the complete response
        """
        pass

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Generate a streaming response.

        Args:
            messages: List of conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            system_prompt: Optional system prompt

        Yields:
            StreamChunk objects with text deltas
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is configured and available."""
        pass
