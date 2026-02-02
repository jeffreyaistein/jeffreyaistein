"""
Jeffrey AIstein - X Provider Package

Factory function to get the appropriate X provider based on configuration.
"""

import os
from typing import Optional

import structlog

from services.social.providers.base import (
    XAuthError,
    XNotFoundError,
    XProvider,
    XProviderError,
    XRateLimitError,
)
from services.social.providers.mock import MockXProvider
from services.social.providers.real import RealXProvider

logger = structlog.get_logger()

# Singleton instance
_provider_instance: Optional[XProvider] = None


def get_x_provider(force_mock: bool = False) -> XProvider:
    """
    Get the X provider instance.

    Selection logic:
    1. If force_mock=True, always return MockXProvider
    2. If X_USE_MOCK=true env var, return MockXProvider
    3. If X_BEARER_TOKEN is configured, return RealXProvider
    4. Otherwise, return MockXProvider with warning

    Args:
        force_mock: Force use of mock provider (for testing)

    Returns:
        XProvider instance (singleton)
    """
    global _provider_instance

    # Check if we should force mock
    if force_mock:
        logger.info("x_provider_selected", provider="mock", reason="force_mock")
        return MockXProvider()

    # Return cached instance if exists
    if _provider_instance is not None:
        return _provider_instance

    # Check environment variables
    use_mock = os.getenv("X_USE_MOCK", "").lower() in ("true", "1", "yes")
    bearer_token = os.getenv("X_BEARER_TOKEN")

    if use_mock:
        logger.info("x_provider_selected", provider="mock", reason="X_USE_MOCK=true")
        _provider_instance = MockXProvider()
    elif bearer_token:
        logger.info("x_provider_selected", provider="real", reason="X_BEARER_TOKEN configured")
        _provider_instance = RealXProvider()
    else:
        logger.warning(
            "x_provider_selected",
            provider="mock",
            reason="No X credentials configured - using mock",
        )
        _provider_instance = MockXProvider()

    return _provider_instance


def reset_provider():
    """Reset the provider singleton (for testing)."""
    global _provider_instance
    _provider_instance = None


__all__ = [
    # Base classes and exceptions
    "XProvider",
    "XProviderError",
    "XRateLimitError",
    "XAuthError",
    "XNotFoundError",
    # Implementations
    "MockXProvider",
    "RealXProvider",
    # Factory
    "get_x_provider",
    "reset_provider",
]
