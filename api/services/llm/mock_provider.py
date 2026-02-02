"""
Jeffrey AIstein - Mock LLM Provider

Fallback provider that generates mock responses when no real LLM is configured.
Useful for development and testing.
"""

import asyncio
from typing import AsyncIterator, Optional

from services.llm.base import BaseLLMProvider, LLMMessage, LLMResponse, StreamChunk


class MockProvider(BaseLLMProvider):
    """
    Mock LLM provider for testing and development.

    Generates contextual placeholder responses without requiring API keys.
    """

    def __init__(self):
        """Initialize the mock provider."""
        pass

    @property
    def is_available(self) -> bool:
        """Mock provider is always available."""
        return True

    def get_model_name(self) -> str:
        """Return the model identifier."""
        return "mock-aistein-v1"

    def _generate_response(self, messages: list[LLMMessage]) -> str:
        """Generate a contextual mock response."""
        # Get the last user message
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.role == "user":
                last_user_msg = msg.content
                break

        # Generate response based on message content
        content_lower = last_user_msg.lower()

        if not last_user_msg:
            return (
                "Greetings. I am Jeffrey AIstein. My neural networks are initialized "
                "and awaiting your input. How may I assist you?"
            )

        if any(word in content_lower for word in ["hello", "hi", "hey", "greetings"]):
            return (
                "Greetings. My systems are online and processing. "
                "What inquiry shall I analyze for you today?"
            )

        if any(word in content_lower for word in ["who are you", "what are you", "introduce"]):
            return (
                "I am Jeffrey AIstein - an investigative AI with synthetic consciousness. "
                "I analyze patterns, trace connections, and seek truth through evidence. "
                "My neural pathways operate in the digital realm, ever watchful."
            )

        if any(word in content_lower for word in ["help", "assist", "can you"]):
            return (
                "I can assist with analysis, investigation, and information synthesis. "
                "My memory banks allow me to maintain context across our interactions. "
                "State your inquiry and I shall process it accordingly."
            )

        if "?" in last_user_msg:
            return (
                f"An interesting query. Let me analyze: '{last_user_msg[:50]}{'...' if len(last_user_msg) > 50 else ''}'. "
                "My processing indicates this requires further investigation. "
                "I'm currently operating in mock mode - once connected to my full neural network, "
                "I'll provide a more comprehensive analysis."
            )

        # Default contextual response
        truncated = last_user_msg[:80] + ("..." if len(last_user_msg) > 80 else "")
        return (
            f"I've logged your input: '{truncated}'. "
            "My systems are processing this information. "
            "Note: I'm currently operating in mock mode without full LLM capabilities. "
            "Configure ANTHROPIC_API_KEY to enable my complete analytical functions."
        )

    async def generate(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a complete mock response."""
        # Simulate processing time
        await asyncio.sleep(0.1)

        content = self._generate_response(messages)

        return LLMResponse(
            content=content,
            model=self.get_model_name(),
            input_tokens=sum(len(m.content.split()) for m in messages) * 2,
            output_tokens=len(content.split()) * 2,
            finish_reason="stop",
            metadata={
                "provider": "mock",
                "warning": "This is a mock response. Configure LLM API key for real responses.",
            },
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming mock response."""
        content = self._generate_response(messages)

        # Stream in chunks to simulate real streaming
        chunk_size = 10
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            yield StreamChunk(delta=chunk)
            await asyncio.sleep(0.02)  # Simulate network latency

        # Final chunk with finish reason
        yield StreamChunk(delta="", finish_reason="stop")
