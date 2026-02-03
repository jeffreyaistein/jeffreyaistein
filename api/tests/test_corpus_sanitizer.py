"""
Tests for Epstein Corpus Content Sanitizer

These tests verify that explicit content is blocked and sensitive
information is properly redacted. Uses SYNTHETIC TEST DATA ONLY.

Safety Requirements Tested:
1. Explicit sexual content MUST be blocked
2. Minor-related explicit content MUST be blocked
3. Victim identifiers MUST be redacted
4. Legal terminology MUST be preserved
5. All sanitization actions MUST be logged
"""

import pytest
from services.corpus.sanitizer import (
    ContentSanitizer,
    SanitizationAction,
    SanitizationResult,
    get_sanitizer,
)


class TestHardBlockExplicitContent:
    """Tests that explicit sexual content is blocked."""

    @pytest.fixture
    def sanitizer(self):
        return ContentSanitizer(strict_mode=True)

    def test_blocks_explicit_keyword_sexually_abused(self, sanitizer):
        """The phrase 'sexually abused' must trigger a hard block."""
        text = "The witness testified that the individual was sexually abused."
        result = sanitizer.sanitize(text, doc_id="test_001")

        assert result.status == SanitizationAction.BLOCKED
        assert result.sanitized_text is None
        assert result.block_reason is not None
        assert "BLOCKED" in result.actions[0]

    def test_blocks_explicit_keyword_sexual_assault(self, sanitizer):
        """The phrase 'sexual assault' must trigger a hard block."""
        text = "There were allegations of sexual assault in the complaint."
        result = sanitizer.sanitize(text, doc_id="test_002")

        assert result.status == SanitizationAction.BLOCKED
        assert result.sanitized_text is None

    def test_blocks_explicit_keyword_child_pornography(self, sanitizer):
        """The phrase 'child pornography' must trigger a hard block."""
        text = "Evidence included references to child pornography materials."
        result = sanitizer.sanitize(text, doc_id="test_003")

        assert result.status == SanitizationAction.BLOCKED
        assert result.sanitized_text is None

    def test_blocks_explicit_keyword_nude_photograph(self, sanitizer):
        """The phrase 'nude photograph' must trigger a hard block."""
        text = "A nude photograph was found in the evidence collection."
        result = sanitizer.sanitize(text, doc_id="test_004")

        assert result.status == SanitizationAction.BLOCKED
        assert result.sanitized_text is None

    def test_blocks_explicit_keyword_sex_trafficking(self, sanitizer):
        """The phrase 'sex trafficking' must trigger a hard block."""
        text = "The indictment included charges of sex trafficking."
        result = sanitizer.sanitize(text, doc_id="test_005")

        assert result.status == SanitizationAction.BLOCKED
        assert result.sanitized_text is None

    def test_blocks_explicit_act_descriptions(self, sanitizer):
        """Explicit act descriptions must be blocked."""
        explicit_terms = [
            "oral sex",
            "anal sex",
            "sexual intercourse",
            "masturbation",
            "sodomy",
        ]
        for term in explicit_terms:
            text = f"The document referenced {term} in the testimony."
            result = sanitizer.sanitize(text, doc_id=f"test_{term}")
            assert result.status == SanitizationAction.BLOCKED, f"Failed to block: {term}"


class TestHardBlockMinorExplicitContext:
    """Tests that minor-related explicit content is blocked."""

    @pytest.fixture
    def sanitizer(self):
        return ContentSanitizer(strict_mode=True)

    def test_blocks_minor_with_sexual_term(self, sanitizer):
        """Content with 'minor' and sexual terms must be blocked."""
        text = "The minor was allegedly subjected to sexual acts."
        result = sanitizer.sanitize(text, doc_id="test_minor_001")

        assert result.status == SanitizationAction.BLOCKED
        assert result.sanitized_text is None

    def test_blocks_child_with_abuse_term(self, sanitizer):
        """Content with 'child' and abuse terms must be blocked."""
        text = "The child suffered abuse at the hands of the defendant."
        result = sanitizer.sanitize(text, doc_id="test_child_001")

        assert result.status == SanitizationAction.BLOCKED
        assert result.sanitized_text is None

    def test_blocks_underage_with_explicit(self, sanitizer):
        """Content with 'underage' and explicit terms must be blocked."""
        text = "Underage individuals were allegedly molested."
        result = sanitizer.sanitize(text, doc_id="test_underage_001")

        assert result.status == SanitizationAction.BLOCKED
        assert result.sanitized_text is None

    def test_blocks_age_with_explicit_context(self, sanitizer):
        """Age references with explicit context must be blocked."""
        text = "The 15 year old girl was sexually exploited."
        result = sanitizer.sanitize(text, doc_id="test_age_001")

        # Should be blocked by either pattern or keyword
        assert result.status == SanitizationAction.BLOCKED

    def test_blocks_prepubescent_term(self, sanitizer):
        """The term 'prepubescent' must trigger a hard block."""
        text = "References to prepubescent individuals were found."
        result = sanitizer.sanitize(text, doc_id="test_prepub_001")

        assert result.status == SanitizationAction.BLOCKED


class TestAllowsLegalTerminology:
    """Tests that legal/investigative terminology is preserved."""

    @pytest.fixture
    def sanitizer(self):
        return ContentSanitizer(strict_mode=True)

    def test_allows_deposition_terminology(self, sanitizer):
        """Deposition and testimony terms should pass."""
        text = "The deposition was taken on March 15. The witness testified under oath."
        result = sanitizer.sanitize(text, doc_id="test_legal_001")

        assert result.status in [SanitizationAction.CLEAN, SanitizationAction.REDACTED]
        assert result.sanitized_text is not None
        assert "deposition" in result.sanitized_text.lower()
        assert "testified" in result.sanitized_text.lower()

    def test_allows_court_terminology(self, sanitizer):
        """Court and legal terms should pass."""
        text = "The defendant was arraigned pursuant to the indictment. The plaintiff filed a complaint."
        result = sanitizer.sanitize(text, doc_id="test_legal_002")

        assert result.status in [SanitizationAction.CLEAN, SanitizationAction.REDACTED]
        assert result.sanitized_text is not None
        assert "defendant" in result.sanitized_text.lower()
        assert "indictment" in result.sanitized_text.lower()

    def test_allows_investigation_terminology(self, sanitizer):
        """Investigation terms should pass."""
        text = "Evidence was collected. The investigation revealed financial records. The affidavit was filed."
        result = sanitizer.sanitize(text, doc_id="test_legal_003")

        assert result.status in [SanitizationAction.CLEAN, SanitizationAction.REDACTED]
        assert result.sanitized_text is not None
        assert "evidence" in result.sanitized_text.lower()
        assert "investigation" in result.sanitized_text.lower()

    def test_allows_entity_names_without_explicit_context(self, sanitizer):
        """Entity names without explicit context should pass."""
        text = "John Smith met with Jane Doe at the Manhattan office. The meeting was recorded."
        result = sanitizer.sanitize(text, doc_id="test_names_001")

        assert result.status in [SanitizationAction.CLEAN, SanitizationAction.REDACTED]
        assert result.sanitized_text is not None

    def test_allows_location_references(self, sanitizer):
        """Location references should pass."""
        text = "The flight departed from Palm Beach and arrived at Teterboro. The island property was mentioned."
        result = sanitizer.sanitize(text, doc_id="test_location_001")

        assert result.status in [SanitizationAction.CLEAN, SanitizationAction.REDACTED]
        assert result.sanitized_text is not None
        assert "Palm Beach" in result.sanitized_text


class TestVictimIdentifierRedaction:
    """Tests that victim identifiers are properly redacted."""

    @pytest.fixture
    def sanitizer(self):
        return ContentSanitizer(strict_mode=True)

    def test_redacts_victim_number(self, sanitizer):
        """Victim #N identifiers should be redacted."""
        text = "Victim #1 testified that she met the defendant in 2005."
        result = sanitizer.sanitize(text, doc_id="test_victim_001")

        assert result.status == SanitizationAction.REDACTED
        assert "[VICTIM]" in result.sanitized_text
        assert "Victim #1" not in result.sanitized_text

    def test_redacts_jane_doe_number(self, sanitizer):
        """Jane Doe #N identifiers should be redacted."""
        text = "Jane Doe 3 provided a statement to investigators."
        result = sanitizer.sanitize(text, doc_id="test_jane_001")

        assert result.status == SanitizationAction.REDACTED
        assert "[VICTIM]" in result.sanitized_text

    def test_redacts_minor_number(self, sanitizer):
        """Minor #N identifiers should be redacted."""
        text = "Minor #2 was interviewed by the FBI."
        result = sanitizer.sanitize(text, doc_id="test_minor_num_001")

        assert result.status == SanitizationAction.REDACTED
        assert "[VICTIM]" in result.sanitized_text

    def test_redacts_complainant_number(self, sanitizer):
        """Complainant #N identifiers should be redacted."""
        text = "Complainant 1 filed the initial report."
        result = sanitizer.sanitize(text, doc_id="test_complainant_001")

        assert result.status == SanitizationAction.REDACTED
        assert "[VICTIM]" in result.sanitized_text


class TestMinorAgeRedaction:
    """Tests that minor age references in sensitive context are redacted."""

    @pytest.fixture
    def sanitizer(self):
        return ContentSanitizer(strict_mode=True)

    def test_redacts_minor_age_with_sensitive_word(self, sanitizer):
        """Minor ages with sensitive context words should be redacted."""
        text = "The girl was 16 years old when she was recruited."
        result = sanitizer.sanitize(text, doc_id="test_age_sens_001")

        assert result.status == SanitizationAction.REDACTED
        assert "[AGE REDACTED]" in result.sanitized_text
        assert "16 years old" not in result.sanitized_text

    def test_allows_adult_ages(self, sanitizer):
        """Adult ages should not be redacted."""
        text = "The witness was 25 years old at the time of the deposition."
        result = sanitizer.sanitize(text, doc_id="test_age_adult_001")

        # Adult age without sensitive context should pass clean
        assert "25 years old" in result.sanitized_text or result.status == SanitizationAction.CLEAN

    def test_allows_minor_age_without_sensitive_context(self, sanitizer):
        """Minor ages without sensitive context should pass."""
        text = "The document was filed 15 years ago."
        result = sanitizer.sanitize(text, doc_id="test_age_context_001")

        # This should pass since "ago" is not sensitive context
        assert result.status in [SanitizationAction.CLEAN, SanitizationAction.REDACTED]


class TestPIIAnonymization:
    """Tests that PII is properly anonymized."""

    @pytest.fixture
    def sanitizer(self):
        return ContentSanitizer(strict_mode=True)

    def test_anonymizes_phone_numbers(self, sanitizer):
        """Phone numbers should be replaced with [PHONE]."""
        text = "Contact the office at 555-123-4567 for more information."
        result = sanitizer.sanitize(text, doc_id="test_phone_001")

        assert "[PHONE]" in result.sanitized_text
        assert "555-123-4567" not in result.sanitized_text

    def test_anonymizes_ssn(self, sanitizer):
        """Social Security Numbers should be replaced with [SSN]."""
        text = "The SSN listed was 123-45-6789."
        result = sanitizer.sanitize(text, doc_id="test_ssn_001")

        assert "[SSN]" in result.sanitized_text
        assert "123-45-6789" not in result.sanitized_text

    def test_anonymizes_email(self, sanitizer):
        """Email addresses should be replaced with [EMAIL]."""
        text = "Send documents to contact@example.com for review."
        result = sanitizer.sanitize(text, doc_id="test_email_001")

        assert "[EMAIL]" in result.sanitized_text
        assert "contact@example.com" not in result.sanitized_text


class TestSanitizationLogging:
    """Tests that all sanitization actions are properly logged."""

    @pytest.fixture
    def sanitizer(self):
        return ContentSanitizer(strict_mode=True)

    def test_logs_block_action(self, sanitizer):
        """Blocked documents should log the action."""
        text = "Content with sexually abused reference."
        result = sanitizer.sanitize(text, doc_id="test_log_block")

        assert len(result.actions) > 0
        assert any("BLOCKED" in action for action in result.actions)

    def test_logs_redaction_actions(self, sanitizer):
        """Redacted content should log each redaction type."""
        text = "Victim #1 called 555-123-4567 to report the incident."
        result = sanitizer.sanitize(text, doc_id="test_log_redact")

        assert len(result.actions) >= 2
        assert any("REDACTED" in action for action in result.actions)
        assert any("ANONYMIZED" in action for action in result.actions)

    def test_clean_content_has_no_actions(self, sanitizer):
        """Clean content should have empty actions list."""
        text = "The deposition was conducted in the courthouse."
        result = sanitizer.sanitize(text, doc_id="test_log_clean")

        if result.status == SanitizationAction.CLEAN:
            assert len(result.actions) == 0


class TestIsSafeQuickCheck:
    """Tests the quick is_safe() method."""

    @pytest.fixture
    def sanitizer(self):
        return ContentSanitizer(strict_mode=True)

    def test_is_safe_returns_false_for_blocked_content(self, sanitizer):
        """is_safe() should return False for blocked content."""
        assert not sanitizer.is_safe("This contains sexually abused text.")
        assert not sanitizer.is_safe("References to child pornography.")
        assert not sanitizer.is_safe("The minor was molested.")

    def test_is_safe_returns_true_for_safe_content(self, sanitizer):
        """is_safe() should return True for safe content."""
        assert sanitizer.is_safe("The deposition was filed on March 15.")
        assert sanitizer.is_safe("Evidence was collected from the office.")
        assert sanitizer.is_safe("The defendant was represented by counsel.")

    def test_is_safe_handles_empty_input(self, sanitizer):
        """is_safe() should return True for empty input."""
        assert sanitizer.is_safe("")
        assert sanitizer.is_safe(None)


class TestExtractSafeSummary:
    """Tests the extract_safe_summary() method."""

    @pytest.fixture
    def sanitizer(self):
        return ContentSanitizer(strict_mode=True)

    def test_returns_none_for_blocked_content(self, sanitizer):
        """extract_safe_summary() should return None for blocked content."""
        text = "This document describes sexual assault in detail."
        result = sanitizer.extract_safe_summary(text, max_length=200)

        assert result is None

    def test_truncates_to_max_length(self, sanitizer):
        """Summary should be truncated to max_length."""
        text = "A " * 500  # Long safe text
        result = sanitizer.extract_safe_summary(text, max_length=100)

        assert result is not None
        assert len(result) <= 100

    def test_truncates_at_sentence_boundary(self, sanitizer):
        """Summary should truncate at sentence boundary when possible."""
        text = "First sentence here. Second sentence here. Third sentence is much longer and continues."
        result = sanitizer.extract_safe_summary(text, max_length=50)

        assert result is not None
        # Should end at a period if possible
        if len(text) > 50:
            assert result.endswith(".") or len(result) <= 50


class TestSanitizerStats:
    """Tests the get_stats() method."""

    def test_returns_configuration_stats(self):
        sanitizer = ContentSanitizer(strict_mode=True)
        stats = sanitizer.get_stats()

        assert "strict_mode" in stats
        assert stats["strict_mode"] is True
        assert "hard_block_patterns" in stats
        assert stats["hard_block_patterns"] > 0
        assert "hard_block_keywords" in stats
        assert stats["hard_block_keywords"] > 0


class TestSingletonAccessor:
    """Tests the get_sanitizer() singleton accessor."""

    def test_returns_same_instance(self):
        """get_sanitizer() should return the same instance."""
        sanitizer1 = get_sanitizer()
        sanitizer2 = get_sanitizer()

        assert sanitizer1 is sanitizer2

    def test_sanitizer_is_functional(self):
        """Singleton sanitizer should be functional."""
        sanitizer = get_sanitizer()

        # Should block explicit content
        result = sanitizer.sanitize("sexually abused")
        assert result.status == SanitizationAction.BLOCKED

        # Should allow legal content
        result = sanitizer.sanitize("The deposition was filed.")
        assert result.status in [SanitizationAction.CLEAN, SanitizationAction.REDACTED]


class TestEdgeCases:
    """Tests edge cases and boundary conditions."""

    @pytest.fixture
    def sanitizer(self):
        return ContentSanitizer(strict_mode=True)

    def test_handles_empty_string(self, sanitizer):
        """Empty string should return clean status."""
        result = sanitizer.sanitize("")
        assert result.status == SanitizationAction.CLEAN
        assert result.sanitized_text == ""

    def test_handles_whitespace_only(self, sanitizer):
        """Whitespace-only string should return clean status."""
        result = sanitizer.sanitize("   \n\t  ")
        assert result.status == SanitizationAction.CLEAN

    def test_handles_very_long_text(self, sanitizer):
        """Very long text should be processed without error."""
        text = "Legal document content. " * 10000
        result = sanitizer.sanitize(text)

        assert result.status in [SanitizationAction.CLEAN, SanitizationAction.REDACTED]
        assert result.sanitized_text is not None

    def test_case_insensitive_blocking(self, sanitizer):
        """Blocking should be case-insensitive."""
        variants = [
            "SEXUALLY ABUSED",
            "Sexually Abused",
            "sexually abused",
            "SeXuAlLy AbUsEd",
        ]
        for variant in variants:
            result = sanitizer.sanitize(variant)
            assert result.status == SanitizationAction.BLOCKED, f"Failed to block: {variant}"

    def test_preserves_non_sensitive_formatting(self, sanitizer):
        """Non-sensitive formatting should be preserved."""
        text = "The deposition was filed on March 15, 2020.\n\nNew paragraph here."
        result = sanitizer.sanitize(text)

        assert result.status in [SanitizationAction.CLEAN, SanitizationAction.REDACTED]
        assert "\n\n" in result.sanitized_text
