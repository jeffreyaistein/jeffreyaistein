"""
Jeffrey AIstein - Brand Rules Enforcement Tests

Tests that HARD BRAND RULES are enforced:
- NO emojis in any output (X, web, drafts, previews)
- NO hashtags in any output (X, web, drafts, previews)

These tests should FAIL if any emoji or hashtag survives post-processing.
"""

import pytest


class TestEmojiStripping:
    """Tests for emoji removal."""

    def test_strips_common_emojis(self):
        """Common emoticons are stripped."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        inputs = [
            ("Hello 😀 world", "Hello world"),
            ("gm ☀️", "gm"),
            ("🚀🚀🚀 to the moon", "to the moon"),
            ("testing 👍 thumbs up", "testing thumbs up"),
            ("fire 🔥 content", "fire content"),
        ]

        for input_text, expected in inputs:
            result = rewriter.strip_emojis(input_text)
            assert "😀" not in result
            assert "☀" not in result
            assert "🚀" not in result
            assert "👍" not in result
            assert "🔥" not in result

    def test_strips_flag_emojis(self):
        """Flag emojis are stripped."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        result = rewriter.strip_emojis("USA 🇺🇸 flag")
        assert "🇺🇸" not in result
        assert "flag" in result

    def test_strips_symbol_emojis(self):
        """Symbol emojis are stripped."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        inputs = [
            "check ✓ mark",
            "arrow → here",
            "star ★ rating",
        ]
        for text in inputs:
            result = rewriter.strip_emojis(text)
            assert not rewriter.contains_emoji(result)

    def test_preserves_text_without_emojis(self):
        """Text without emojis is preserved."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        text = "Just plain text with no emojis"
        result = rewriter.strip_emojis(text)
        assert result == text

    def test_contains_emoji_detection(self):
        """Emoji detection works correctly."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        assert rewriter.contains_emoji("Hello 😀") is True
        assert rewriter.contains_emoji("Hello world") is False
        assert rewriter.contains_emoji("🚀") is True
        assert rewriter.contains_emoji("") is False


class TestHashtagStripping:
    """Tests for hashtag removal."""

    def test_strips_single_hashtag(self):
        """Single hashtag is stripped."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        result = rewriter.strip_hashtags("Check out #crypto today")
        assert "#crypto" not in result
        assert "#" not in result
        assert "Check out" in result

    def test_strips_multiple_hashtags(self):
        """Multiple hashtags are stripped."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        result = rewriter.strip_hashtags("#Bitcoin #Ethereum #Solana are pumping")
        assert "#" not in result
        assert "are pumping" in result

    def test_strips_trailing_hashtags(self):
        """Trailing hashtags are stripped."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        result = rewriter.strip_hashtags("Great content #nfa #dyor")
        assert "#" not in result
        assert "Great content" in result

    def test_preserves_text_without_hashtags(self):
        """Text without hashtags is preserved."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        text = "Just plain text with no hashtags"
        result = rewriter.strip_hashtags(text)
        assert result == text

    def test_contains_hashtag_detection(self):
        """Hashtag detection works correctly."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        assert rewriter.contains_hashtag("Hello #world") is True
        assert rewriter.contains_hashtag("Hello world") is False
        assert rewriter.contains_hashtag("#") is False  # Lone # is not a hashtag
        assert rewriter.contains_hashtag("#a") is True


class TestBrandRulesEnforcement:
    """Tests for combined brand rule enforcement."""

    def test_enforce_strips_both(self):
        """Enforcement strips both emojis and hashtags."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        input_text = "gm 🚀 #crypto gang 💪 #wagmi"
        result = rewriter.enforce_brand_rules(input_text)

        assert "🚀" not in result
        assert "💪" not in result
        assert "#" not in result
        assert "gm" in result
        assert "gang" in result

    def test_validate_catches_violations(self):
        """Validation catches emoji and hashtag violations."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()

        is_valid, violations = rewriter.validate_brand_rules("Hello 😀 #world")
        assert is_valid is False
        assert len(violations) == 2

        is_valid, violations = rewriter.validate_brand_rules("Clean text")
        assert is_valid is True
        assert len(violations) == 0

    def test_rewrite_for_x_enforces_rules(self):
        """X rewriting enforces brand rules."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        input_text = "Check this out 🔥🔥 #alpha #nfa"
        result = rewriter.rewrite_for_x(input_text)

        assert "🔥" not in result
        assert "#" not in result
        is_valid, _ = rewriter.validate_brand_rules(result)
        assert is_valid is True

    def test_rewrite_for_web_enforces_rules(self):
        """Web rewriting enforces brand rules."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        input_text = "Web content 😊 with #hashtags"
        result = rewriter.rewrite_for_web(input_text)

        assert "😊" not in result
        assert "#" not in result
        is_valid, _ = rewriter.validate_brand_rules(result)
        assert is_valid is True


class TestLengthAfterStripping:
    """Tests that length constraints work after stripping."""

    def test_x_length_after_strip(self):
        """X output respects 280 char limit after stripping."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        # Create a long text with emojis
        long_text = "A" * 300 + " 🚀🚀🚀 #crypto"
        result = rewriter.rewrite_for_x(long_text)

        assert len(result) <= 280
        assert "🚀" not in result
        assert "#" not in result

    def test_text_remains_readable_after_strip(self):
        """Text remains coherent after stripping."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()
        input_text = "The 🚀 market is looking 📈 bullish today #crypto #bull"
        result = rewriter.enforce_brand_rules(input_text)

        # Should still be readable
        assert "market" in result
        assert "looking" in result
        assert "bullish" in result
        assert "today" in result


class TestContentGeneratorIntegration:
    """Tests for ContentGenerator brand rule integration."""

    def test_timeline_post_no_emoji_no_hashtag(self):
        """Timeline posts have no emojis or hashtags after processing."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()

        # Simulate what ContentGenerator does with output
        mock_llm_output = "This is fire 🔥🔥 content #alpha #nfa"
        processed = rewriter.rewrite_for_x(mock_llm_output)

        assert "🔥" not in processed
        assert "#" not in processed
        is_valid, _ = rewriter.validate_brand_rules(processed)
        assert is_valid

    def test_reply_no_emoji_no_hashtag(self):
        """Replies have no emojis or hashtags after processing."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()

        mock_reply = "@user Great take 👍 #agree"
        processed = rewriter.rewrite_for_x(mock_reply)

        assert "👍" not in processed
        assert "#" not in processed
        is_valid, _ = rewriter.validate_brand_rules(processed)
        assert is_valid

    def test_web_chat_no_emoji_no_hashtag(self):
        """Web chat has no emojis or hashtags after processing."""
        from services.persona.style_rewriter import StyleRewriter

        rewriter = StyleRewriter()

        mock_web_output = "Here's my analysis 📊\n\n#summary: the data shows..."
        processed = rewriter.rewrite_for_web(mock_web_output)

        assert "📊" not in processed
        assert "#summary" not in processed
        is_valid, _ = rewriter.validate_brand_rules(processed)
        assert is_valid
