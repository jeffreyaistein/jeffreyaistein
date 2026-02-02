"""
Jeffrey AIstein - LLM Provider Factory

Factory function to get the configured LLM provider.
"""

from typing import Optional
import structlog

from config import settings
from services.llm.base import BaseLLMProvider
from services.llm.anthropic_provider import AnthropicProvider
from services.llm.mock_provider import MockProvider


logger = structlog.get_logger()

# Singleton provider instance
_provider_instance: Optional[BaseLLMProvider] = None


def get_llm_provider(force_mock: bool = False) -> BaseLLMProvider:
    """
    Get the configured LLM provider.

    Provider selection priority:
    1. If force_mock=True, return MockProvider
    2. If ANTHROPIC_API_KEY is set, return AnthropicProvider
    3. Otherwise, return MockProvider (fallback)

    The provider is cached as a singleton for efficiency.

    Args:
        force_mock: Force using the mock provider regardless of config

    Returns:
        Configured LLM provider instance
    """
    global _provider_instance

    # Force mock mode
    if force_mock:
        logger.info("llm_provider_selected", provider="mock", reason="force_mock")
        return MockProvider()

    # Return cached instance if available
    if _provider_instance is not None:
        return _provider_instance

    # Check for Anthropic API key
    if settings.anthropic_api_key:
        _provider_instance = AnthropicProvider()
        logger.info(
            "llm_provider_selected",
            provider="anthropic",
            model=_provider_instance.get_model_name(),
        )
        return _provider_instance

    # Fallback to mock
    logger.warning(
        "llm_provider_fallback",
        provider="mock",
        reason="no_api_key",
        hint="Set ANTHROPIC_API_KEY for real LLM responses",
    )
    _provider_instance = MockProvider()
    return _provider_instance


def reset_provider() -> None:
    """
    Reset the cached provider instance.

    Useful for testing or when configuration changes.
    """
    global _provider_instance
    _provider_instance = None
    logger.info("llm_provider_reset")
