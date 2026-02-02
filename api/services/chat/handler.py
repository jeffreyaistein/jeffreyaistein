"""
Jeffrey AIstein - Chat Handler Service

Orchestrates LLM calls with persona, moderation, and context.
"""

from typing import AsyncIterator, Optional
from dataclasses import dataclass

import structlog

from services.llm import get_llm_provider, LLMMessage, StreamChunk
from services.persona import get_system_prompt, load_persona
from services.moderation import check_input, check_output, get_safe_response


logger = structlog.get_logger()


@dataclass
class ChatContext:
    """Context for a chat interaction."""
    user_id: str
    conversation_id: str
    channel: str = "web"  # "web" or "x"


class ChatService:
    """
    Service for handling chat interactions.

    Coordinates:
    - LLM provider calls
    - Persona system prompt
    - Input/output moderation
    - Memory retrieval (future)
    """

    def __init__(self, channel: str = "web"):
        """
        Initialize the chat service.

        Args:
            channel: Platform channel ("web" or "x")
        """
        self.channel = channel
        self.llm = get_llm_provider()
        self.persona = load_persona()
        self.system_prompt = get_system_prompt(
            persona=self.persona,
            channel=channel,
            include_memory_context=True,
        )

    async def generate(
        self,
        messages: list[dict],
        context: Optional[ChatContext] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate a complete response.

        Args:
            messages: Conversation history [{"role": "user/assistant", "content": "..."}]
            context: Optional chat context
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated response string
        """
        # Get the latest user message for moderation
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        # Check input moderation
        mod_result = check_input(user_message)
        if not mod_result.is_safe:
            logger.warning(
                "chat_moderation_blocked",
                category=mod_result.category,
                user_id=context.user_id if context else None,
            )
            return get_safe_response(mod_result)

        # Convert to LLMMessage format
        llm_messages = [
            LLMMessage(role=msg["role"], content=msg["content"])
            for msg in messages
        ]

        # Generate response
        try:
            response = await self.llm.generate(
                messages=llm_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=self.system_prompt,
            )

            # Check output moderation (non-blocking, just logging)
            output_mod = check_output(response.content)
            if output_mod.category == "persona_break":
                logger.info("chat_persona_break_detected")

            logger.info(
                "chat_response_generated",
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                user_id=context.user_id if context else None,
            )

            return response.content

        except Exception as e:
            logger.error("chat_generation_error", error=str(e))
            return (
                "My neural pathways encountered an error during processing. "
                "Please try again, or rephrase your query."
            )

    async def stream(
        self,
        messages: list[dict],
        context: Optional[ChatContext] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """
        Stream a response token by token.

        Args:
            messages: Conversation history
            context: Optional chat context
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Response text chunks
        """
        # Get the latest user message for moderation
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        # Check input moderation
        mod_result = check_input(user_message)
        if not mod_result.is_safe:
            logger.warning(
                "chat_moderation_blocked",
                category=mod_result.category,
                user_id=context.user_id if context else None,
            )
            # Stream the safe response
            safe_response = get_safe_response(mod_result)
            for i in range(0, len(safe_response), 10):
                yield safe_response[i:i + 10]
            return

        # Convert to LLMMessage format
        llm_messages = [
            LLMMessage(role=msg["role"], content=msg["content"])
            for msg in messages
        ]

        # Stream response
        full_response = ""
        try:
            async for chunk in self.llm.stream(
                messages=llm_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=self.system_prompt,
            ):
                if chunk.delta:
                    full_response += chunk.delta
                    yield chunk.delta

                if chunk.finish_reason == "error":
                    logger.error("chat_stream_error")
                    break

            # Check output moderation
            output_mod = check_output(full_response)
            if output_mod.category == "persona_break":
                logger.info("chat_persona_break_detected")

            logger.info(
                "chat_stream_completed",
                model=self.llm.get_model_name(),
                response_length=len(full_response),
                user_id=context.user_id if context else None,
            )

        except Exception as e:
            logger.error("chat_stream_error", error=str(e))
            error_msg = "Processing error. Please try again."
            yield error_msg


# Convenience functions for direct use
async def generate_response(
    messages: list[dict],
    channel: str = "web",
    context: Optional[ChatContext] = None,
) -> str:
    """Generate a complete response."""
    service = ChatService(channel=channel)
    return await service.generate(messages, context=context)


async def stream_response(
    messages: list[dict],
    channel: str = "web",
    context: Optional[ChatContext] = None,
) -> AsyncIterator[str]:
    """Stream a response."""
    service = ChatService(channel=channel)
    async for chunk in service.stream(messages, context=context):
        yield chunk
