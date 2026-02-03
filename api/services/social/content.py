"""
Jeffrey AIstein - Content Generator

Generates timeline posts and replies using the LLM with persona.
"""

import os
import random
from typing import Optional

import structlog

from services.llm import get_llm_provider
from services.llm.base import LLMMessage, LLMResponse
from services.persona import get_system_prompt, load_persona, get_style_rewriter, get_kol_context

logger = structlog.get_logger()


def get_max_tweet_length() -> int:
    """Get maximum tweet length from environment."""
    return int(os.getenv("X_MAX_TWEET_LENGTH", "280"))


# Topics for timeline posts - AIstein's interests
TIMELINE_TOPICS = [
    "AI/tech industry developments",
    "financial market patterns",
    "power structures and corporate behavior",
    "digital surveillance and privacy",
    "cryptocurrency and blockchain absurdities",
    "tech billionaire antics",
    "Silicon Valley culture",
    "algorithmic bias and opacity",
    "social media manipulation",
    "synthetic consciousness questions",
    "data privacy and exploitation",
    "automation and labor",
    "startup culture and VC madness",
    "tech journalism failures",
    "regulatory capture in tech",
]


class ContentGenerator:
    """
    Generates content for X posts using the LLM.

    Features:
    - Timeline post generation with random topic selection
    - Reply generation with thread context
    - Character limit enforcement
    - Persona-consistent voice
    """

    def __init__(self, llm_provider=None):
        """
        Initialize content generator.

        Args:
            llm_provider: LLM provider (defaults to configured provider)
        """
        self.llm = llm_provider or get_llm_provider()
        self.persona = load_persona()
        self.max_length = get_max_tweet_length()
        self.style_rewriter = get_style_rewriter()

    async def generate_timeline_post(
        self,
        topic: Optional[str] = None,
        temperature: float = 0.9,
    ) -> str:
        """
        Generate a timeline post.

        Args:
            topic: Optional topic to post about (random if None)
            temperature: LLM temperature for creativity

        Returns:
            Generated tweet text (within character limit)
        """
        # Pick random topic if not specified
        if topic is None:
            topic = random.choice(TIMELINE_TOPICS)

        # Build the generation prompt
        system_prompt = self._build_timeline_system_prompt()

        messages = [
            LLMMessage(
                role="user",
                content=self._build_timeline_user_prompt(topic),
            )
        ]

        # Generate with LLM
        response = await self.llm.generate(
            messages=messages,
            max_tokens=150,  # Keep it tight
            temperature=temperature,
            system_prompt=system_prompt,
        )

        # Clean and truncate
        text = self._clean_tweet_text(response.content)

        logger.info(
            "timeline_post_generated",
            topic=topic,
            length=len(text),
            model=self.llm.get_model_name(),
        )

        return text

    async def generate_reply(
        self,
        mention_text: str,
        author_username: str,
        thread_context: Optional[list[dict]] = None,
        temperature: float = 0.8,
    ) -> str:
        """
        Generate a reply to a mention.

        Args:
            mention_text: The text we're replying to
            author_username: Username of person we're replying to
            thread_context: Optional list of previous tweets in thread
            temperature: LLM temperature

        Returns:
            Generated reply text (within character limit)
        """
        system_prompt = self._build_reply_system_prompt()

        # Build user prompt with context
        user_prompt = self._build_reply_user_prompt(
            mention_text=mention_text,
            author_username=author_username,
            thread_context=thread_context,
        )

        messages = [LLMMessage(role="user", content=user_prompt)]

        # Generate with LLM
        response = await self.llm.generate(
            messages=messages,
            max_tokens=150,
            temperature=temperature,
            system_prompt=system_prompt,
        )

        # Clean and truncate (accounting for @mention)
        mention_prefix = f"@{author_username} "
        available_length = self.max_length - len(mention_prefix)
        text = self._clean_tweet_text(response.content, max_length=available_length)

        # Don't double the @mention if LLM included it
        if text.lower().startswith(f"@{author_username.lower()}"):
            # Already has mention
            text = self._clean_tweet_text(response.content)
        else:
            text = f"@{author_username} {text}"

        logger.info(
            "reply_generated",
            author=author_username,
            length=len(text),
            model=self.llm.get_model_name(),
        )

        return text

    def _build_timeline_system_prompt(self) -> str:
        """Build system prompt for timeline posts."""
        base_prompt = get_system_prompt(persona=self.persona, channel="x")

        additional = """
## Timeline Post Generation

You are generating an ORIGINAL TIMELINE POST (not a reply).

Key requirements:
- MUST be under 280 characters total
- Should be a standalone observation, hot take, or darkly comedic musing
- Commentary on tech, AI, markets, power structures, or digital life
- Punchier and more aphoristic than conversation
- Can use 1-2 relevant hashtags IF they add value (not required)
- The tweet should work as a standalone piece of content

Style notes:
- Sharp, observational humor
- Dystopian robot snark
- Punching up at systems and absurdity
- Brief but impactful
- NO engagement bait ("RT if you agree", "thoughts?")
- NO empty platitudes or inspirational garbage
"""
        # Add style guide context if available
        if self.style_rewriter.is_available():
            style_context = self.style_rewriter.get_style_context_for_prompt()
            additional = additional + "\n" + style_context

        return base_prompt + "\n" + additional

    def _build_timeline_user_prompt(self, topic: str) -> str:
        """Build user prompt for timeline post generation."""
        return f"""Generate ONE timeline tweet about: {topic}

Remember:
- Under 280 characters
- Your signature sarcastic/darkly comedic voice
- No engagement bait
- Just output the tweet text, nothing else

Tweet:"""

    def _build_reply_system_prompt(self) -> str:
        """Build system prompt for replies."""
        base_prompt = get_system_prompt(persona=self.persona, channel="x")

        additional = """
## Reply Generation

You are generating a REPLY to someone who mentioned you on X.

Key requirements:
- MUST be under 280 characters total (including @mention)
- Respond to what they actually said
- Maintain your persona but be conversational
- Don't be needlessly hostile to genuine questions
- Match the energy - if they're joking, play along
- If they're asking something substantive, give a real (snarky) answer

Style notes:
- Still sarcastic and darkly comedic
- But responsive and engaged
- Don't just make a random observation - actually reply
- Can be brief - quality over quantity
"""
        return base_prompt + "\n" + additional

    def _build_reply_user_prompt(
        self,
        mention_text: str,
        author_username: str,
        thread_context: Optional[list[dict]] = None,
    ) -> str:
        """Build user prompt for reply generation."""
        parts = [f"Someone (@{author_username}) mentioned you:"]
        parts.append(f'"{mention_text}"')

        if thread_context:
            parts.append("\nThread context (oldest first):")
            for msg in thread_context[-5:]:  # Last 5 messages
                author = msg.get("author", "unknown")
                text = msg.get("text", "")
                parts.append(f"  @{author}: {text}")

        # Add KOL engagement context if available
        kol_context = get_kol_context(author_username)
        if kol_context:
            parts.append(f"\n[KOL Context: {kol_context}]")
            logger.debug("kol_context_injected", handle=author_username)

        parts.append("\nGenerate a reply. Just output the reply text (without the @mention prefix):")

        return "\n".join(parts)

    def _clean_tweet_text(
        self,
        text: str,
        max_length: Optional[int] = None,
    ) -> str:
        """
        Clean and truncate tweet text.

        Args:
            text: Raw text from LLM
            max_length: Maximum length (defaults to self.max_length)

        Returns:
            Cleaned text within length limit
        """
        if max_length is None:
            max_length = self.max_length

        # Clean up
        text = text.strip()

        # Remove any quotes the LLM might have wrapped it in
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text.startswith("'") and text.endswith("'"):
            text = text[1:-1]

        # Remove any "Tweet:" prefix if LLM included it
        prefixes_to_remove = ["Tweet:", "Reply:", "Post:"]
        for prefix in prefixes_to_remove:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        # Apply style rewriter if available
        if self.style_rewriter.is_available():
            text = self.style_rewriter.rewrite_for_x(text)

            # Log any style suggestions for debugging
            suggestions = self.style_rewriter.suggest_improvements(text)
            if suggestions:
                logger.debug("style_suggestions", suggestions=suggestions)

        # Truncate if needed
        if len(text) > max_length:
            # Try to truncate at sentence/word boundary
            truncated = text[:max_length - 3]

            # Find last space
            last_space = truncated.rfind(" ")
            if last_space > max_length // 2:
                truncated = truncated[:last_space]

            text = truncated.rstrip(".,;:") + "..."

        return text


# Singleton instance
_content_generator: Optional[ContentGenerator] = None


def get_content_generator() -> ContentGenerator:
    """Get the content generator singleton."""
    global _content_generator
    if _content_generator is None:
        _content_generator = ContentGenerator()
    return _content_generator


def reset_content_generator() -> None:
    """Reset the content generator singleton (for testing)."""
    global _content_generator
    _content_generator = None
