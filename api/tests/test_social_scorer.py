"""
Tests for the High Quality Account Scorer.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest

from services.social.scorer import (
    compute_quality_score,
    get_quality_threshold,
    is_high_quality_account,
)
from services.social.types import XUser


def make_user(
    id: str = "123456789",
    username: str = "testuser",
    name: str = "Test User",
    days_old: int = 365,
    followers: int = 100,
    following: int = 100,
    tweets: int = 500,
    verified: bool = False,
    has_bio: bool = True,
    has_location: bool = True,
    default_image: bool = False,
) -> XUser:
    """Create a test user with configurable attributes."""
    return XUser(
        id=id,
        username=username,
        name=name,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_old),
        followers_count=followers,
        following_count=following,
        tweet_count=tweets,
        verified=verified,
        description="This is a test bio with more than 20 characters" if has_bio else None,
        location="New York, NY" if has_location else None,
        default_profile_image=default_image,
    )


class TestQualityScorer:
    """Tests for compute_quality_score function."""

    def test_new_account_low_score(self):
        """New accounts with few followers should score low."""
        user = make_user(
            days_old=7,
            followers=5,
            following=100,
            tweets=10,
            has_bio=False,
            has_location=False,
            default_image=True,
        )
        result = compute_quality_score(user)

        assert result.score < 30
        assert result.passed is False
        assert "account_age" in result.breakdown
        assert result.breakdown["account_age"]["score"] == 0  # < 30 days

    def test_established_account_high_score(self):
        """Established accounts with good metrics should score high."""
        user = make_user(
            days_old=400,
            followers=1000,
            following=500,
            tweets=2000,
            verified=True,
            has_bio=True,
            has_location=True,
            default_image=False,
        )
        result = compute_quality_score(user)

        assert result.score >= 70
        assert result.passed is True
        assert result.breakdown["account_age"]["score"] == 20
        assert result.breakdown["followers"]["score"] == 25
        assert result.breakdown["verified"]["score"] == 10

    def test_age_scoring_tiers(self):
        """Test account age scoring at different tiers."""
        # < 30 days = 0 points
        user = make_user(days_old=15)
        result = compute_quality_score(user)
        assert result.breakdown["account_age"]["score"] == 0

        # 30-89 days = 5 points
        user = make_user(days_old=45)
        result = compute_quality_score(user)
        assert result.breakdown["account_age"]["score"] == 5

        # 90-179 days = 10 points
        user = make_user(days_old=120)
        result = compute_quality_score(user)
        assert result.breakdown["account_age"]["score"] == 10

        # 180-364 days = 15 points
        user = make_user(days_old=200)
        result = compute_quality_score(user)
        assert result.breakdown["account_age"]["score"] == 15

        # >= 365 days = 20 points
        user = make_user(days_old=400)
        result = compute_quality_score(user)
        assert result.breakdown["account_age"]["score"] == 20

    def test_follower_scoring_tiers(self):
        """Test follower count scoring at different tiers."""
        # < 10 = 0 points
        user = make_user(followers=5)
        result = compute_quality_score(user)
        assert result.breakdown["followers"]["score"] == 0

        # 10-49 = 5 points
        user = make_user(followers=25)
        result = compute_quality_score(user)
        assert result.breakdown["followers"]["score"] == 5

        # 50-99 = 10 points
        user = make_user(followers=75)
        result = compute_quality_score(user)
        assert result.breakdown["followers"]["score"] == 10

        # 100-499 = 15 points
        user = make_user(followers=250)
        result = compute_quality_score(user)
        assert result.breakdown["followers"]["score"] == 15

        # 500-999 = 20 points
        user = make_user(followers=750)
        result = compute_quality_score(user)
        assert result.breakdown["followers"]["score"] == 20

        # >= 1000 = 25 points
        user = make_user(followers=5000)
        result = compute_quality_score(user)
        assert result.breakdown["followers"]["score"] == 25

    def test_follower_ratio_scoring(self):
        """Test follower/following ratio scoring."""
        # Ratio < 0.5 = 0 points
        user = make_user(followers=100, following=500)
        result = compute_quality_score(user)
        assert result.breakdown["follower_ratio"]["score"] == 0

        # Ratio 0.5-0.99 = 5 points
        user = make_user(followers=100, following=150)
        result = compute_quality_score(user)
        assert result.breakdown["follower_ratio"]["score"] == 5

        # Ratio 1.0-1.99 = 10 points
        user = make_user(followers=150, following=100)
        result = compute_quality_score(user)
        assert result.breakdown["follower_ratio"]["score"] == 10

        # Ratio >= 2.0 = 15 points
        user = make_user(followers=1000, following=100)
        result = compute_quality_score(user)
        assert result.breakdown["follower_ratio"]["score"] == 15

    def test_zero_following_handled(self):
        """Test that zero following doesn't cause division by zero."""
        user = make_user(followers=100, following=0)
        result = compute_quality_score(user)
        # Should use followers as ratio when following=0
        assert result.breakdown["follower_ratio"]["score"] == 15  # ratio = 100

    def test_verified_bonus(self):
        """Verified accounts should get 10 bonus points."""
        user_unverified = make_user(verified=False)
        user_verified = make_user(verified=True)

        result_unverified = compute_quality_score(user_unverified)
        result_verified = compute_quality_score(user_verified)

        assert result_verified.score == result_unverified.score + 10
        assert result_verified.breakdown["verified"]["score"] == 10
        assert result_unverified.breakdown["verified"]["score"] == 0

    def test_profile_completeness_scoring(self):
        """Test profile completeness component."""
        # Empty profile = 0 points
        user = make_user(has_bio=False, has_location=False, default_image=True)
        result = compute_quality_score(user)
        assert result.breakdown["profile"]["score"] == 0

        # Custom image only = 5 points
        user = make_user(has_bio=False, has_location=False, default_image=False)
        result = compute_quality_score(user)
        assert result.breakdown["profile"]["score"] == 5

        # Full profile = 15 points
        user = make_user(has_bio=True, has_location=True, default_image=False)
        result = compute_quality_score(user)
        assert result.breakdown["profile"]["score"] == 15

    def test_score_capped_at_100(self):
        """Score should never exceed 100."""
        # Create super user that would exceed 100
        user = make_user(
            days_old=1000,
            followers=100000,
            following=1,
            tweets=50000,
            verified=True,
            has_bio=True,
            has_location=True,
            default_image=False,
        )
        result = compute_quality_score(user)
        assert result.score <= 100

    def test_threshold_from_env(self, monkeypatch):
        """Threshold should be configurable via environment."""
        # Default threshold
        assert get_quality_threshold() == 30

        # Custom threshold
        monkeypatch.setenv("X_HIGH_QUALITY_SCORE_THRESHOLD", "50")
        assert get_quality_threshold() == 50

    def test_is_high_quality_convenience(self):
        """Test the convenience function."""
        # Low quality account
        user = make_user(days_old=7, followers=5)
        assert is_high_quality_account(user) is False

        # High quality account
        user = make_user(days_old=400, followers=500)
        assert is_high_quality_account(user) is True


class TestBotDetection:
    """Tests for detecting likely bot accounts."""

    def test_follow_bot_pattern(self):
        """Accounts following many but with few followers should score lower due to ratio."""
        user = make_user(
            followers=50,
            following=5000,  # Following way more than followers
            tweets=100,
        )
        result = compute_quality_score(user)
        # Bad ratio should contribute 0 points
        assert result.breakdown["follower_ratio"]["score"] == 0
        # But other factors can still push the score up
        # The key assertion is the ratio penalty is applied
        assert result.breakdown["follower_ratio"]["ratio"] < 0.5

    def test_egg_account_pattern(self):
        """New account with default image and no activity should score very low."""
        user = make_user(
            days_old=5,
            followers=0,
            following=50,
            tweets=0,
            has_bio=False,
            has_location=False,
            default_image=True,
        )
        result = compute_quality_score(user)
        assert result.score < 10
        assert result.passed is False

    def test_real_user_pattern(self):
        """Pattern of a typical real user should pass."""
        user = make_user(
            days_old=200,  # 6+ months old
            followers=150,  # Modest following
            following=200,  # Follows similar amount
            tweets=800,  # Active tweeter
            verified=False,
            has_bio=True,
            has_location=True,
            default_image=False,
        )
        result = compute_quality_score(user)
        # Should score around 50-60
        assert result.score >= 40
        assert result.passed is True
