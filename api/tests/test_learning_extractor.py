"""
Jeffrey AIstein - Learning Extractor Tests

Unit tests for learning memory extraction from X interactions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSlangExtraction:
    """Test CT slang term extraction."""

    def test_extracts_common_slang_terms(self):
        """Test extraction of common CT slang."""
        from services.learning.extractor import extract_slang

        text = "gm everyone! wagmi today, lfg to the moon 🚀"
        memories = extract_slang(text, "12345")

        # Should find: gm, wagmi, lfg
        terms_found = [m["content"] for m in memories]
        assert "gm" in terms_found
        assert "wagmi" in terms_found
        assert "lfg" in terms_found

    def test_extracts_case_insensitive(self):
        """Test that slang extraction is case insensitive."""
        from services.learning.extractor import extract_slang

        text = "GM CT! WAGMI frens"
        memories = extract_slang(text, "12345")

        terms_found = [m["content"] for m in memories]
        # Should find gm, ct, wagmi, frens (all lowercased)
        assert "gm" in terms_found
        assert "ct" in terms_found
        assert "wagmi" in terms_found
        assert "frens" in terms_found

    def test_no_duplicates_in_same_text(self):
        """Test that duplicate terms in same text don't create duplicate memories."""
        from services.learning.extractor import extract_slang

        text = "gm gm gm! did i say gm?"
        memories = extract_slang(text, "12345")

        # Should only have one "gm" memory
        gm_memories = [m for m in memories if m["content"] == "gm"]
        assert len(gm_memories) == 1

    def test_includes_tweet_id_in_source(self):
        """Test that extracted slang includes source tweet ID."""
        from services.learning.extractor import extract_slang

        text = "gm frens"
        memories = extract_slang(text, "tweet123")

        for memory in memories:
            assert memory["source_tweet_ids"] == ["tweet123"]

    def test_empty_text_returns_empty(self):
        """Test that empty text returns no memories."""
        from services.learning.extractor import extract_slang

        memories = extract_slang("", "12345")
        assert memories == []

    def test_no_slang_returns_empty(self):
        """Test that text without slang returns no memories."""
        from services.learning.extractor import extract_slang

        text = "Hello everyone, how are you today?"
        memories = extract_slang(text, "12345")
        assert memories == []


class TestNarrativeExtraction:
    """Test narrative tag extraction."""

    def test_extracts_token_talk(self):
        """Test extraction of token/price discussion tags."""
        from services.learning.extractor import extract_narrative_tags

        text = "Just bought some $SOL, price looking good"
        memories = extract_narrative_tags(text, "12345")

        tags_found = [m["content"] for m in memories]
        assert "token_talk" in tags_found

    def test_extracts_pump_signals(self):
        """Test extraction of pump-related tags."""
        from services.learning.extractor import extract_narrative_tags

        text = "This is pumping hard! Moon incoming!"
        memories = extract_narrative_tags(text, "12345")

        tags_found = [m["content"] for m in memories]
        assert "pump" in tags_found

    def test_extracts_rug_warnings(self):
        """Test extraction of rug/scam warnings."""
        from services.learning.extractor import extract_narrative_tags

        text = "Be careful, this looks like a rug pull"
        memories = extract_narrative_tags(text, "12345")

        tags_found = [m["content"] for m in memories]
        assert "rug" in tags_found

    def test_extracts_multiple_narratives(self):
        """Test extraction of multiple narrative tags from same text."""
        from services.learning.extractor import extract_narrative_tags

        text = "Dev just dumped after the pump, classic rug"
        memories = extract_narrative_tags(text, "12345")

        tags_found = [m["content"] for m in memories]
        assert "dump" in tags_found
        assert "pump" in tags_found
        assert "rug" in tags_found


class TestRiskExtraction:
    """Test risk flag extraction."""

    def test_extracts_phishing_links(self):
        """Test detection of phishing-style links."""
        from services.learning.extractor import extract_risk_flags

        text = "Check out this airdrop at soIana.com/claim"
        memories = extract_risk_flags(text, "12345")

        # Should find phishing link pattern
        flags_found = [m["content"] for m in memories]
        assert any("phishing" in f for f in flags_found)

    def test_extracts_scam_keywords(self):
        """Test detection of scam keywords."""
        from services.learning.extractor import extract_risk_flags

        text = "GUARANTEED 100x returns! FREE MONEY!"
        memories = extract_risk_flags(text, "12345")

        flags_found = [m["content"] for m in memories]
        assert any("scam" in f for f in flags_found)

    def test_extracts_wallet_solicitation(self):
        """Test detection of wallet address requests."""
        from services.learning.extractor import extract_risk_flags

        text = "Send your wallet address for the airdrop"
        memories = extract_risk_flags(text, "12345")

        flags_found = [m["content"] for m in memories]
        assert any("wallet" in f for f in flags_found)


class TestEngagementOutcome:
    """Test engagement outcome extraction."""

    def test_extracts_reply_outcome(self):
        """Test extraction of reply engagement."""
        from services.learning.extractor import extract_engagement_outcome

        memory = extract_engagement_outcome(
            tweet_id="reply123",
            post_type="reply",
            status="posted",
            reply_to_id="original456",
        )

        assert memory is not None
        assert memory["content"] == "replied:original456"
        assert memory["type"] == "x_engagement"

    def test_extracts_timeline_post(self):
        """Test extraction of timeline post engagement."""
        from services.learning.extractor import extract_engagement_outcome

        memory = extract_engagement_outcome(
            tweet_id="post123",
            post_type="timeline",
            status="posted",
            reply_to_id=None,
        )

        assert memory is not None
        assert memory["content"] == "posted:timeline"

    def test_skips_non_posted(self):
        """Test that non-posted items don't create engagement memory."""
        from services.learning.extractor import extract_engagement_outcome

        memory = extract_engagement_outcome(
            tweet_id="draft123",
            post_type="reply",
            status="draft",
            reply_to_id="original456",
        )

        assert memory is None


class TestCleanText:
    """Test text cleaning (emoji/hashtag removal)."""

    def test_removes_emojis(self):
        """Test that emojis are removed from text."""
        from services.learning.extractor import clean_text

        text = "gm frens 🚀🌙💎"
        cleaned = clean_text(text)
        assert "🚀" not in cleaned
        assert "🌙" not in cleaned
        assert "💎" not in cleaned
        assert "gm frens" in cleaned

    def test_removes_hashtags(self):
        """Test that hashtags are removed from text."""
        from services.learning.extractor import clean_text

        text = "gm #crypto #solana #wagmi"
        cleaned = clean_text(text)
        assert "#crypto" not in cleaned
        assert "#solana" not in cleaned
        assert "#wagmi" not in cleaned
        assert "gm" in cleaned

    def test_removes_both(self):
        """Test that both emojis and hashtags are removed."""
        from services.learning.extractor import clean_text

        text = "gm CT! 🔥 #wagmi to the moon 🚀"
        cleaned = clean_text(text)
        assert "🔥" not in cleaned
        assert "🚀" not in cleaned
        assert "#wagmi" not in cleaned
        assert "gm CT" in cleaned


class TestExtractorIdempotency:
    """Test idempotency of extraction."""

    @pytest.mark.asyncio
    async def test_skips_already_processed_inbox(self):
        """Test that already processed inbox items are skipped."""
        from services.learning.extractor import LearningExtractor

        extractor = LearningExtractor()

        # Create a mock row that's already processed
        mock_row = MagicMock()
        mock_row.id = "12345"
        mock_row.learning_processed = True
        mock_row.tweet_data = {"text": "gm frens"}

        result = await extractor.process_inbox_item(mock_row, AsyncMock())
        assert result["skipped"] is True
        assert result["reason"] == "already_processed"

    @pytest.mark.asyncio
    async def test_skips_already_processed_post(self):
        """Test that already processed posts are skipped."""
        from services.learning.extractor import LearningExtractor

        extractor = LearningExtractor()

        # Create a mock row that's already processed
        mock_row = MagicMock()
        mock_row.id = "12345"
        mock_row.tweet_id = "67890"
        mock_row.learning_processed = True
        mock_row.text = "gm frens"

        result = await extractor.process_outbound_post(mock_row, AsyncMock())
        assert result["skipped"] is True
        assert result["reason"] == "already_processed"


class TestCTSlangVocabulary:
    """Test that CT slang vocabulary is comprehensive."""

    def test_contains_core_terms(self):
        """Test that core CT terms are in vocabulary."""
        from services.learning.extractor import CT_SLANG_TERMS

        core_terms = [
            "gm", "gn", "wagmi", "ngmi", "lfg",
            "degen", "fren", "frens", "anon", "ser",
            "alpha", "chad", "ape", "moon", "diamond hands",
        ]

        for term in core_terms:
            assert term in CT_SLANG_TERMS, f"Missing core term: {term}"

    def test_vocabulary_size(self):
        """Test that vocabulary has reasonable size."""
        from services.learning.extractor import CT_SLANG_TERMS

        # Should have at least 50 terms
        assert len(CT_SLANG_TERMS) >= 50


class TestNarrativePatterns:
    """Test narrative pattern coverage."""

    def test_contains_core_patterns(self):
        """Test that core narrative patterns exist."""
        from services.learning.extractor import NARRATIVE_PATTERNS

        expected_tags = [
            "token_talk", "pump", "dump", "rug", "dev",
            "airdrop", "fud", "whales",
        ]

        for tag in expected_tags:
            assert tag in NARRATIVE_PATTERNS, f"Missing pattern: {tag}"


class TestRiskPatterns:
    """Test risk pattern coverage."""

    def test_contains_core_patterns(self):
        """Test that core risk patterns exist."""
        from services.learning.extractor import RISK_PATTERNS

        expected_patterns = [
            "phishing_link", "scam_keyword", "spam_pattern", "wallet_solicitation",
        ]

        for pattern in expected_patterns:
            assert pattern in RISK_PATTERNS, f"Missing pattern: {pattern}"
