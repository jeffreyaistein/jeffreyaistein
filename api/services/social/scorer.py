"""
Jeffrey AIstein - High Quality Account Scorer

Deterministic scoring function to filter out spam/bot accounts.
Only uses public X API metadata - no external lookups.
"""

import os
from datetime import datetime, timezone

import structlog

from services.social.types import QualityScoreResult, XUser

logger = structlog.get_logger()

# Default threshold (configurable via env)
DEFAULT_QUALITY_THRESHOLD = 30


def get_quality_threshold() -> int:
    """Get quality threshold from environment."""
    return int(os.getenv("X_HIGH_QUALITY_SCORE_THRESHOLD", DEFAULT_QUALITY_THRESHOLD))


def compute_quality_score(user: XUser) -> QualityScoreResult:
    """
    Compute quality score (0-100) for an X account.

    Higher score = more likely a real, engaged human.
    Uses ONLY public X API metadata - no external lookups.

    Scoring Components:
    - Account age: 0-20 points
    - Followers count: 0-25 points
    - Follower/Following ratio: 0-15 points
    - Tweet count: 0-15 points
    - Verified status: 0-10 points
    - Profile completeness: 0-15 points

    Args:
        user: XUser object with public metrics

    Returns:
        QualityScoreResult with score, pass/fail, and breakdown
    """
    now = datetime.now(timezone.utc)
    breakdown = {}
    score = 0

    # =========================================
    # Account Age (max 20 points)
    # Older accounts are less likely to be bots
    # =========================================
    account_age_days = (now - user.created_at.replace(tzinfo=timezone.utc)).days

    if account_age_days >= 365:
        age_score = 20
    elif account_age_days >= 180:
        age_score = 15
    elif account_age_days >= 90:
        age_score = 10
    elif account_age_days >= 30:
        age_score = 5
    else:
        age_score = 0

    breakdown["account_age"] = {
        "days": account_age_days,
        "score": age_score,
        "max": 20,
    }
    score += age_score

    # =========================================
    # Followers Count (max 25 points)
    # More followers = more established
    # =========================================
    followers = user.followers_count

    if followers >= 1000:
        follower_score = 25
    elif followers >= 500:
        follower_score = 20
    elif followers >= 100:
        follower_score = 15
    elif followers >= 50:
        follower_score = 10
    elif followers >= 10:
        follower_score = 5
    else:
        follower_score = 0

    breakdown["followers"] = {
        "count": followers,
        "score": follower_score,
        "max": 25,
    }
    score += follower_score

    # =========================================
    # Follower/Following Ratio (max 15 points)
    # High ratio = influential, not follow-bot
    # =========================================
    following = user.following_count

    if following > 0:
        ratio = followers / following
    else:
        ratio = followers if followers > 0 else 0

    if ratio >= 2.0:
        ratio_score = 15
    elif ratio >= 1.0:
        ratio_score = 10
    elif ratio >= 0.5:
        ratio_score = 5
    else:
        ratio_score = 0

    breakdown["follower_ratio"] = {
        "ratio": round(ratio, 2),
        "score": ratio_score,
        "max": 15,
    }
    score += ratio_score

    # =========================================
    # Tweet Count (max 15 points)
    # More tweets = more engaged user
    # =========================================
    tweets = user.tweet_count

    if tweets >= 1000:
        tweet_score = 15
    elif tweets >= 500:
        tweet_score = 10
    elif tweets >= 100:
        tweet_score = 5
    else:
        tweet_score = 0

    breakdown["tweet_count"] = {
        "count": tweets,
        "score": tweet_score,
        "max": 15,
    }
    score += tweet_score

    # =========================================
    # Verified Status (10 points)
    # Verified = human reviewed
    # =========================================
    verified_score = 10 if user.verified else 0

    breakdown["verified"] = {
        "is_verified": user.verified,
        "score": verified_score,
        "max": 10,
    }
    score += verified_score

    # =========================================
    # Profile Completeness (max 15 points)
    # Complete profile = more likely real
    # =========================================
    profile_score = 0

    # Has custom profile image (5 points)
    if not user.default_profile_image:
        profile_score += 5

    # Has bio description of reasonable length (5 points)
    if user.description and len(user.description) >= 20:
        profile_score += 5

    # Has location set (5 points)
    if user.location:
        profile_score += 5

    breakdown["profile"] = {
        "has_custom_image": not user.default_profile_image,
        "has_bio": bool(user.description and len(user.description) >= 20),
        "has_location": bool(user.location),
        "score": profile_score,
        "max": 15,
    }
    score += profile_score

    # Cap at 100
    score = min(score, 100)

    # Check threshold
    threshold = get_quality_threshold()
    passed = score >= threshold

    logger.info(
        "quality_score_computed",
        user_id=user.id,
        username=user.username,
        score=score,
        threshold=threshold,
        passed=passed,
    )

    return QualityScoreResult(
        score=score,
        passed=passed,
        breakdown=breakdown,
    )


def is_high_quality_account(user: XUser) -> bool:
    """
    Quick check if account passes quality threshold.

    Args:
        user: XUser object

    Returns:
        True if account passes threshold
    """
    result = compute_quality_score(user)
    return result.passed
