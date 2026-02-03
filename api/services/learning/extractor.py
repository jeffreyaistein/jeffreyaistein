"""
Jeffrey AIstein - Learning Memory Extractor

Extracts learning memories from X interactions:
- Slang/phrases (CT vocabulary)
- Narrative tags (topics being discussed)
- Risk flags (spam, scam, harassment signals)
- Engagement outcomes (reply received, approved, posted)

IMPORTANT: Never store emojis or hashtags in memory content.
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import async_session_maker

logger = structlog.get_logger()


# ===========================================
# Data Types
# ===========================================


@dataclass
class MemoryItem:
    """A single extracted memory item."""
    type: str  # x_slang, x_narrative, x_risk_flag, x_engagement
    content: str
    confidence: float
    source_tweet_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ===========================================
# Constants
# ===========================================


# CT (Crypto Twitter) slang terms to recognize
CT_SLANG_TERMS = {
    "gm", "gn", "wagmi", "ngmi", "lfg", "iykyk", "nfa", "dyor",
    "alpha", "based", "rekt", "fud", "fomo", "hodl", "ape", "apeing",
    "degen", "ser", "anon", "fren", "normie", "noob", "whale",
    "pump", "dump", "moon", "rug", "rugged", "jeet", "jeets",
    "ct", "send it", "size", "bags", "exit liquidity",
    "1000x", "100x", "10x", "lambo", "wen", "smol", "thicc",
    "cope", "seethe", "touch grass", "down bad", "up only",
    "floor is lava", "generational wealth", "life changing",
}

# Narrative tag keywords (maps pattern to tag)
NARRATIVE_PATTERNS = {
    "token_talk": [r"\$\w+", r"token", r"coin", r"mint", r"launch"],
    "pump": [r"pump", r"pumping", r"mooning", r"ripping", r"sending"],
    "dump": [r"dump", r"dumping", r"crashed", r"tanking", r"bleeding"],
    "rug": [r"rug", r"rugged", r"rugpull", r"scam", r"honeypot"],
    "dev": [r"\bdev\b", r"developer", r"builder", r"shipped", r"deployed"],
    "cabal": [r"cabal", r"insider", r"coordinated", r"manipulation"],
    "tools": [r"bot", r"sniper", r"scanner", r"tracker", r"alert"],
    "charts": [r"chart", r"ta\b", r"technical", r"support", r"resistance"],
    "airdrop": [r"airdrop", r"drop", r"claim", r"eligib"],
    "fud": [r"\bfud\b", r"fear", r"uncertainty", r"doubt"],
    "whales": [r"whale", r"big wallet", r"large holder"],
    "community": [r"community", r"holders", r"fam", r"gang"],
}

# Risk flag patterns
RISK_PATTERNS = {
    "phishing_link": [
        r"bit\.ly", r"tinyurl", r"goo\.gl", r"t\.co.*claim",
        r"connect.*wallet", r"verify.*wallet", r"sync.*wallet",
    ],
    "scam_keyword": [
        r"guaranteed.*return", r"100%.*profit", r"risk.free",
        r"double.*your", r"send.*receive.*back",
    ],
    "doxx_attempt": [
        r"what.*your.*address", r"where.*you.*live",
        r"what.*your.*name", r"reveal.*identity",
    ],
    "spam_pattern": [
        r"follow.*back", r"f4f", r"dm.*me.*now",
        r"check.*my.*profile", r"link.*in.*bio",
    ],
    "wallet_solicitation": [
        r"dm.*wallet", r"send.*wallet.*address",
        r"wallet.*dm", r"airdrop.*wallet",
    ],
}

# Emoji pattern for stripping
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F1E0-\U0001F1FF"
    "\U00002300-\U000023FF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\U0000FE00-\U0000FE0F"
    "\U0001F000-\U0001F02F"
    "\U0001F0A0-\U0001F0FF"
    "]+",
    flags=re.UNICODE,
)

# Hashtag pattern for stripping
HASHTAG_PATTERN = re.compile(r"#\w+", re.UNICODE)


# ===========================================
# Helper Functions
# ===========================================


def clean_text(text: str) -> str:
    """
    Clean text by removing emojis and hashtags.

    HARD RULE: No emojis or hashtags in memory content.
    """
    result = text
    result = EMOJI_PATTERN.sub("", result)
    result = HASHTAG_PATTERN.sub("", result)
    result = re.sub(r"\s+", " ", result)
    return result.strip()


def extract_urls(text: str) -> list[str]:
    """Extract URLs from text."""
    url_pattern = r"https?://[^\s<>\"{}|\\^`\[\]]+"
    return re.findall(url_pattern, text, re.IGNORECASE)


# ===========================================
# Extraction Functions
# ===========================================


def extract_slang(text: str, tweet_id: str) -> list[MemoryItem]:
    """
    Extract CT slang terms from text.

    Returns MemoryItem for each recognized slang term.
    """
    memories = []
    text_lower = text.lower()
    words = set(re.findall(r"\b\w+\b", text_lower))

    # Find matching slang terms
    found_terms = words.intersection(CT_SLANG_TERMS)

    # Also check multi-word phrases
    for phrase in CT_SLANG_TERMS:
        if " " in phrase and phrase in text_lower:
            found_terms.add(phrase)

    for term in found_terms:
        memories.append(MemoryItem(
            type="x_slang",
            content=clean_text(term),  # Already clean but be safe
            confidence=0.9,
            source_tweet_ids=[tweet_id],
            metadata={"term": term},
        ))

    return memories


def extract_narrative_tags(text: str, tweet_id: str) -> list[MemoryItem]:
    """
    Extract narrative tags from text using keyword patterns.

    Returns MemoryItem for each detected narrative.
    """
    memories = []
    text_lower = text.lower()

    for tag, patterns in NARRATIVE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                # Extract a clean snippet around the match
                match = re.search(pattern, text_lower, re.IGNORECASE)
                if match:
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 20)
                    snippet = clean_text(text[start:end])

                    memories.append(MemoryItem(
                        type="x_narrative",
                        content=f"{tag}: {snippet}",
                        confidence=0.7,
                        source_tweet_ids=[tweet_id],
                        metadata={"tag": tag, "pattern": pattern},
                    ))
                    break  # Only one memory per tag per tweet

    return memories


def extract_risk_flags(text: str, tweet_id: str) -> list[MemoryItem]:
    """
    Extract risk flags from text.

    Returns MemoryItem for each detected risk.
    """
    memories = []
    text_lower = text.lower()
    urls = extract_urls(text)

    for flag_type, patterns in RISK_PATTERNS.items():
        for pattern in patterns:
            # Check in text
            if re.search(pattern, text_lower, re.IGNORECASE):
                snippet = clean_text(text[:100])
                memories.append(MemoryItem(
                    type="x_risk_flag",
                    content=f"{flag_type}: {snippet}",
                    confidence=0.8,
                    source_tweet_ids=[tweet_id],
                    metadata={"flag": flag_type, "pattern": pattern},
                ))
                break

            # Check in URLs
            for url in urls:
                if re.search(pattern, url, re.IGNORECASE):
                    memories.append(MemoryItem(
                        type="x_risk_flag",
                        content=f"{flag_type}: suspicious URL detected",
                        confidence=0.9,
                        source_tweet_ids=[tweet_id],
                        metadata={"flag": flag_type, "url": url[:100]},
                    ))
                    break

    return memories


def extract_engagement_outcome(
    tweet_id: str,
    is_inbound: bool,
    was_replied_to: bool = False,
    reply_approved: bool = False,
    reply_posted: bool = False,
    received_reply_back: bool = False,
) -> list[MemoryItem]:
    """
    Extract engagement outcome as memory.

    Args:
        tweet_id: The tweet ID
        is_inbound: True if this is an inbound mention, False if outbound post
        was_replied_to: True if we replied to this inbound tweet
        reply_approved: True if our reply was approved
        reply_posted: True if our reply was posted
        received_reply_back: True if we got a reply to our post
    """
    memories = []

    if is_inbound:
        if was_replied_to and reply_posted:
            memories.append(MemoryItem(
                type="x_engagement",
                content="Inbound mention received reply that was approved and posted",
                confidence=1.0,
                source_tweet_ids=[tweet_id],
                metadata={
                    "outcome": "replied_and_posted",
                    "direction": "inbound",
                },
            ))
        elif was_replied_to and reply_approved:
            memories.append(MemoryItem(
                type="x_engagement",
                content="Inbound mention received reply that was approved",
                confidence=1.0,
                source_tweet_ids=[tweet_id],
                metadata={
                    "outcome": "replied_approved",
                    "direction": "inbound",
                },
            ))
        elif was_replied_to:
            memories.append(MemoryItem(
                type="x_engagement",
                content="Inbound mention received draft reply",
                confidence=1.0,
                source_tweet_ids=[tweet_id],
                metadata={
                    "outcome": "replied_draft",
                    "direction": "inbound",
                },
            ))
        else:
            memories.append(MemoryItem(
                type="x_engagement",
                content="Inbound mention was processed but not replied to",
                confidence=1.0,
                source_tweet_ids=[tweet_id],
                metadata={
                    "outcome": "no_reply",
                    "direction": "inbound",
                },
            ))
    else:
        # Outbound post
        if received_reply_back:
            memories.append(MemoryItem(
                type="x_engagement",
                content="Outbound post received engagement (reply back)",
                confidence=1.0,
                source_tweet_ids=[tweet_id],
                metadata={
                    "outcome": "received_reply",
                    "direction": "outbound",
                },
            ))
        else:
            memories.append(MemoryItem(
                type="x_engagement",
                content="Outbound post was published",
                confidence=1.0,
                source_tweet_ids=[tweet_id],
                metadata={
                    "outcome": "posted",
                    "direction": "outbound",
                },
            ))

    return memories


# ===========================================
# Main Extractor Class
# ===========================================


class LearningExtractor:
    """
    Extracts learning memories from X interactions.

    Idempotent: Checks learning_processed flag before processing.
    Safe: Catches exceptions per-row; never crashes caller.
    """

    def __init__(self):
        self._last_job_at: Optional[datetime] = None
        self._processed_count = 0
        self._error_count = 0

    async def _get_session(self) -> AsyncSession:
        return async_session_maker()

    async def process_inbox_item(self, inbox_row: dict) -> list[MemoryItem]:
        """
        Process a single x_inbox row and extract memories.

        Args:
            inbox_row: Dict with keys: id, tweet_data, author_id, etc.

        Returns:
            List of extracted MemoryItems (empty if already processed or error)
        """
        tweet_id = inbox_row.get("id")
        correlation_id = str(uuid.uuid4())[:8]

        try:
            # Check if already processed
            if inbox_row.get("learning_processed"):
                logger.debug(
                    "inbox_already_processed",
                    tweet_id=tweet_id,
                    correlation_id=correlation_id,
                )
                return []

            # Get tweet text from tweet_data
            tweet_data = inbox_row.get("tweet_data", {})
            if isinstance(tweet_data, str):
                import json
                tweet_data = json.loads(tweet_data)

            text = tweet_data.get("text", "")
            if not text:
                logger.warning(
                    "inbox_no_text",
                    tweet_id=tweet_id,
                    correlation_id=correlation_id,
                )
                return []

            # Extract memories
            memories = []
            memories.extend(extract_slang(text, tweet_id))
            memories.extend(extract_narrative_tags(text, tweet_id))
            memories.extend(extract_risk_flags(text, tweet_id))

            # Check engagement outcome
            was_processed = inbox_row.get("processed", False)
            # TODO: Look up if we replied and if that reply was posted
            memories.extend(extract_engagement_outcome(
                tweet_id=tweet_id,
                is_inbound=True,
                was_replied_to=was_processed,
            ))

            # Save memories
            if memories:
                await self._save_memories(memories)

            # Mark as processed
            await self._mark_inbox_processed(tweet_id)

            self._last_job_at = datetime.now(timezone.utc)
            self._processed_count += 1

            logger.info(
                "inbox_item_processed",
                tweet_id=tweet_id,
                memories_extracted=len(memories),
                correlation_id=correlation_id,
            )

            return memories

        except Exception as e:
            self._error_count += 1
            logger.error(
                "inbox_processing_failed",
                tweet_id=tweet_id,
                error=str(e),
                correlation_id=correlation_id,
                exc_info=True,
            )
            return []

    async def process_outbound_post(self, post_row: dict) -> list[MemoryItem]:
        """
        Process a single x_posts row and extract memories.

        Args:
            post_row: Dict with keys: id, tweet_id, text, status, etc.

        Returns:
            List of extracted MemoryItems (empty if already processed or error)
        """
        post_id = post_row.get("id")
        tweet_id = post_row.get("tweet_id")
        correlation_id = str(uuid.uuid4())[:8]

        try:
            # Check if already processed
            if post_row.get("learning_processed"):
                logger.debug(
                    "post_already_processed",
                    post_id=post_id,
                    tweet_id=tweet_id,
                    correlation_id=correlation_id,
                )
                return []

            # Only process posted items
            if post_row.get("status") != "posted":
                logger.debug(
                    "post_not_posted_yet",
                    post_id=post_id,
                    status=post_row.get("status"),
                    correlation_id=correlation_id,
                )
                return []

            text = post_row.get("text", "")
            if not text:
                logger.warning(
                    "post_no_text",
                    post_id=post_id,
                    correlation_id=correlation_id,
                )
                return []

            # Use tweet_id if available, otherwise post_id
            source_id = tweet_id or post_id

            # Extract memories
            memories = []
            memories.extend(extract_slang(text, source_id))
            memories.extend(extract_narrative_tags(text, source_id))
            # Risk flags less relevant for our own posts, but check anyway
            memories.extend(extract_risk_flags(text, source_id))

            # Engagement outcome
            memories.extend(extract_engagement_outcome(
                tweet_id=source_id,
                is_inbound=False,
                reply_posted=True,
            ))

            # Save memories
            if memories:
                await self._save_memories(memories)

            # Mark as processed
            await self._mark_post_processed(post_id)

            self._last_job_at = datetime.now(timezone.utc)
            self._processed_count += 1

            logger.info(
                "outbound_post_processed",
                post_id=post_id,
                tweet_id=tweet_id,
                memories_extracted=len(memories),
                correlation_id=correlation_id,
            )

            return memories

        except Exception as e:
            self._error_count += 1
            logger.error(
                "post_processing_failed",
                post_id=post_id,
                tweet_id=tweet_id,
                error=str(e),
                correlation_id=correlation_id,
                exc_info=True,
            )
            return []

    async def process_unprocessed_items(self, limit: int = 100) -> dict:
        """
        Process all unprocessed inbox items and posts.

        Returns:
            Dict with counts of processed items and memories
        """
        results = {
            "inbox_processed": 0,
            "posts_processed": 0,
            "memories_extracted": 0,
            "errors": 0,
        }

        async with await self._get_session() as session:
            # Process unprocessed inbox items
            inbox_result = await session.execute(
                text("""
                    SELECT * FROM x_inbox
                    WHERE learning_processed = false
                    ORDER BY received_at ASC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            inbox_rows = inbox_result.mappings().fetchall()

            for row in inbox_rows:
                memories = await self.process_inbox_item(dict(row))
                if memories:
                    results["inbox_processed"] += 1
                    results["memories_extracted"] += len(memories)

            # Process unprocessed posts
            posts_result = await session.execute(
                text("""
                    SELECT * FROM x_posts
                    WHERE learning_processed = false
                      AND status = 'posted'
                    ORDER BY posted_at ASC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            posts_rows = posts_result.mappings().fetchall()

            for row in posts_rows:
                memories = await self.process_outbound_post(dict(row))
                if memories:
                    results["posts_processed"] += 1
                    results["memories_extracted"] += len(memories)

        results["errors"] = self._error_count

        logger.info(
            "learning_extraction_complete",
            **results,
        )

        return results

    async def _save_memories(self, memories: list[MemoryItem]) -> None:
        """Save extracted memories to database."""
        async with await self._get_session() as session:
            for memory in memories:
                # Ensure content is clean (no emojis/hashtags)
                clean_content = clean_text(memory.content)

                # Serialize metadata to JSON string for JSONB column
                metadata_json = json.dumps(memory.metadata) if memory.metadata else None

                await session.execute(
                    text("""
                        INSERT INTO memories (
                            id, type, content, confidence,
                            source_tweet_ids, metadata, created_at
                        ) VALUES (
                            :id, :type, :content, :confidence,
                            :source_tweet_ids, CAST(:metadata AS jsonb), :created_at
                        )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "type": memory.type,
                        "content": clean_content,
                        "confidence": memory.confidence,
                        "source_tweet_ids": memory.source_tweet_ids,
                        "metadata": metadata_json,
                        "created_at": datetime.now(timezone.utc),
                    }
                )

            await session.commit()

    async def _mark_inbox_processed(self, tweet_id: str) -> None:
        """Mark an inbox item as learning-processed."""
        async with await self._get_session() as session:
            await session.execute(
                text("""
                    UPDATE x_inbox
                    SET learning_processed = true,
                        learning_processed_at = :now
                    WHERE id = :tweet_id
                """),
                {
                    "tweet_id": tweet_id,
                    "now": datetime.now(timezone.utc),
                }
            )
            await session.commit()

    async def _mark_post_processed(self, post_id: str) -> None:
        """Mark a post as learning-processed."""
        async with await self._get_session() as session:
            await session.execute(
                text("""
                    UPDATE x_posts
                    SET learning_processed = true,
                        learning_processed_at = :now
                    WHERE id = :post_id
                """),
                {
                    "post_id": post_id,
                    "now": datetime.now(timezone.utc),
                }
            )
            await session.commit()

    @property
    def last_job_at(self) -> Optional[datetime]:
        """Get timestamp of last extraction job."""
        return self._last_job_at

    @property
    def processed_count(self) -> int:
        """Get count of processed items."""
        return self._processed_count

    @property
    def error_count(self) -> int:
        """Get count of errors."""
        return self._error_count


# ===========================================
# Singleton
# ===========================================


_extractor_instance: Optional[LearningExtractor] = None


def get_learning_extractor() -> LearningExtractor:
    """Get the learning extractor singleton."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = LearningExtractor()
    return _extractor_instance


def reset_learning_extractor() -> None:
    """Reset the learning extractor singleton (for testing)."""
    global _extractor_instance
    _extractor_instance = None
