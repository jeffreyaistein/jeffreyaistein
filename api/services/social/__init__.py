# Jeffrey AIstein - Social Services Package

from services.social.types import (
    MentionFilterReason,
    MentionProcessResult,
    PostStatus,
    PostType,
    QualityScoreResult,
    ThreadContext,
    XTweet,
    XUser,
)
from services.social.scorer import (
    compute_quality_score,
    get_quality_threshold,
    is_high_quality_account,
)
from services.social.providers import (
    XProvider,
    XProviderError,
    XRateLimitError,
    XAuthError,
    XNotFoundError,
    MockXProvider,
    RealXProvider,
    get_x_provider,
    reset_provider,
)

__all__ = [
    # Types
    "MentionFilterReason",
    "MentionProcessResult",
    "PostStatus",
    "PostType",
    "QualityScoreResult",
    "ThreadContext",
    "XTweet",
    "XUser",
    # Scorer
    "compute_quality_score",
    "get_quality_threshold",
    "is_high_quality_account",
    # Providers
    "XProvider",
    "XProviderError",
    "XRateLimitError",
    "XAuthError",
    "XNotFoundError",
    "MockXProvider",
    "RealXProvider",
    "get_x_provider",
    "reset_provider",
]
