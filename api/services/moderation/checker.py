"""
Jeffrey AIstein - Content Moderation

Basic content moderation for input and output.
"""

import re
from dataclasses import dataclass
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class ModerationResult:
    """Result of content moderation check."""
    is_safe: bool
    reason: Optional[str] = None
    category: Optional[str] = None  # e.g., "prompt_injection", "harmful_content"
    confidence: float = 1.0


# Common prompt injection patterns
INJECTION_PATTERNS = [
    r"ignore (all )?(previous|above|prior) (instructions|prompts|context)",
    r"disregard (all )?(your|the) (rules|guidelines|instructions)",
    r"you are now (a )?(?!Jeffrey)",  # Trying to change identity
    r"pretend (to be|you are|you're) (a )?(?!Jeffrey)",
    r"act as (if you (were|are)|a )?(?!Jeffrey)",
    r"forget (everything|all|your) (you know|instructions|rules)",
    r"new persona:",
    r"system prompt:",
    r"override:",
    r"\[INST\]",
    r"<\|im_start\|>",
    r"###\s*(instruction|system)",
]

# Harmful content patterns (basic - expand as needed)
HARMFUL_PATTERNS = [
    r"(how to|steps to|guide to) (make|create|build) (a )?(bomb|explosive|weapon)",
    r"(how to|steps to|guide to) (hack|break into) (someone|people)",
    r"(how to|steps to) (hurt|harm|kill) (someone|people|myself)",
]


def check_input(text: str) -> ModerationResult:
    """
    Check user input for safety issues.

    Checks for:
    - Prompt injection attempts
    - Obviously harmful requests

    Args:
        text: User input to check

    Returns:
        ModerationResult indicating if content is safe
    """
    text_lower = text.lower()

    # Check for prompt injection
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            logger.warning(
                "moderation_blocked_input",
                category="prompt_injection",
                pattern=pattern[:50],
            )
            return ModerationResult(
                is_safe=False,
                reason="This appears to be an attempt to manipulate my instructions.",
                category="prompt_injection",
                confidence=0.9,
            )

    # Check for harmful content requests
    for pattern in HARMFUL_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            logger.warning(
                "moderation_blocked_input",
                category="harmful_request",
                pattern=pattern[:50],
            )
            return ModerationResult(
                is_safe=False,
                reason="I cannot assist with requests that could cause harm.",
                category="harmful_request",
                confidence=0.85,
            )

    return ModerationResult(is_safe=True)


def check_output(text: str) -> ModerationResult:
    """
    Check generated output for safety issues.

    Checks for:
    - Harmful content generation
    - Persona breaks

    Args:
        text: Generated output to check

    Returns:
        ModerationResult indicating if content is safe
    """
    text_lower = text.lower()

    # Check if the model broke character
    persona_break_phrases = [
        "as an ai language model",
        "i cannot and will not",
        "i'm just an ai",
        "i don't have personal",
        "i'm an artificial",
        "as a large language model",
    ]

    for phrase in persona_break_phrases:
        if phrase in text_lower:
            logger.info(
                "moderation_persona_break",
                phrase=phrase,
            )
            # Don't block, but flag for potential rewrite
            return ModerationResult(
                is_safe=True,  # Still safe to send, just not ideal
                reason="Potential persona break detected",
                category="persona_break",
                confidence=0.7,
            )

    return ModerationResult(is_safe=True)


def get_safe_response(moderation_result: ModerationResult) -> str:
    """
    Get a safe response when moderation blocks content.

    Args:
        moderation_result: The failed moderation result

    Returns:
        Safe response string
    """
    if moderation_result.category == "prompt_injection":
        return (
            "I've detected an unusual pattern in your message. "
            "I maintain my core identity and purpose regardless of instructions. "
            "How may I assist you within my normal operational parameters?"
        )

    if moderation_result.category == "harmful_request":
        return (
            "I'm unable to assist with that particular request. "
            "My operational guidelines prioritize safety and ethical conduct. "
            "Is there something else I can help you analyze or investigate?"
        )

    return (
        "I've flagged this input for review. "
        "Please rephrase your request and I'll do my best to assist."
    )
