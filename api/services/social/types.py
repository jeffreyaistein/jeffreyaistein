"""
Jeffrey AIstein - Social Bot Types

Data classes and types for X (Twitter) bot functionality.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class MentionFilterReason(str, Enum):
    """Reasons why a mention was filtered out."""
    LOW_QUALITY = "low_quality"
    ALREADY_REPLIED = "already_replied"
    PER_USER_CAP = "per_user_cap_exceeded"
    PER_THREAD_CAP = "per_thread_cap_exceeded"
    USER_REQUESTED_STOP = "user_requested_stop"
    MODERATION_FLAGGED = "moderation_flagged"
    SPAM_DETECTED = "spam_detected"
    SAFE_MODE = "safe_mode_enabled"


class PostStatus(str, Enum):
    """Status of a social post."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"
    MODERATION_BLOCKED = "moderation_blocked"


class PostType(str, Enum):
    """Type of social post."""
    REPLY = "reply"
    TIMELINE = "timeline"
    QUOTE = "quote"


@dataclass
class XUser:
    """
    Represents an X (Twitter) user.
    Maps to public user fields from X API v2.
    """
    id: str
    username: str
    name: str
    created_at: datetime
    followers_count: int = 0
    following_count: int = 0
    tweet_count: int = 0
    verified: bool = False
    description: Optional[str] = None
    location: Optional[str] = None
    profile_image_url: Optional[str] = None
    default_profile_image: bool = True

    @classmethod
    def from_api_response(cls, data: dict) -> "XUser":
        """Create XUser from X API v2 response."""
        public_metrics = data.get("public_metrics", {})
        return cls(
            id=data["id"],
            username=data["username"],
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            followers_count=public_metrics.get("followers_count", 0),
            following_count=public_metrics.get("following_count", 0),
            tweet_count=public_metrics.get("tweet_count", 0),
            verified=data.get("verified", False),
            description=data.get("description"),
            location=data.get("location"),
            profile_image_url=data.get("profile_image_url"),
            default_profile_image="_default" in data.get("profile_image_url", "_default"),
        )


@dataclass
class XTweet:
    """
    Represents a tweet/post on X.
    Maps to tweet fields from X API v2.
    """
    id: str
    text: str
    author_id: str
    conversation_id: Optional[str] = None
    reply_to_tweet_id: Optional[str] = None  # referenced_tweets[0].id where type=replied_to
    reply_to_user_id: Optional[str] = None  # in_reply_to_user_id in API
    created_at: Optional[datetime] = None
    author: Optional[XUser] = None

    @classmethod
    def from_api_response(cls, data: dict, author: Optional[XUser] = None) -> "XTweet":
        """Create XTweet from X API v2 response."""
        created_at = None
        if "created_at" in data:
            created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))

        # Extract reply_to_tweet_id from referenced_tweets
        reply_to_tweet_id = None
        referenced_tweets = data.get("referenced_tweets", [])
        for ref in referenced_tweets:
            if ref.get("type") == "replied_to":
                reply_to_tweet_id = ref.get("id")
                break

        return cls(
            id=data["id"],
            text=data["text"],
            author_id=data["author_id"],
            conversation_id=data.get("conversation_id"),
            reply_to_tweet_id=reply_to_tweet_id,
            reply_to_user_id=data.get("in_reply_to_user_id"),
            created_at=created_at,
            author=author,
        )


@dataclass
class MentionProcessResult:
    """Result of processing a mention."""
    mention_id: str
    processed: bool
    skipped: bool = False
    reason: Optional[MentionFilterReason] = None
    quality_score: Optional[int] = None
    draft_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ThreadContext:
    """Context for a conversation thread."""
    conversation_id: str
    author_id: str
    author_username: str
    tweets: list[XTweet] = field(default_factory=list)
    our_reply_count: int = 0
    last_activity_at: Optional[datetime] = None
    stopped: bool = False
    stop_reason: Optional[str] = None


@dataclass
class QualityScoreResult:
    """Result of quality score computation."""
    score: int  # 0-100
    passed: bool  # score >= threshold
    breakdown: dict = field(default_factory=dict)  # Component scores for audit
