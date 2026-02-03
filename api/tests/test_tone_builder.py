"""
Tests for Epstein Tone Builder safety validation.

Verifies that generated tone JSON:
1. Contains required hard constraints
2. Has no blocked content (names, victims, PII, explicit)
3. Passes all safety validations
"""

import json
import pytest
from services.corpus.epstein.tone_builder import (
    ToneProfile,
    CASEFILE_CADENCE_PATTERNS,
    TRANSITIONAL_PHRASES,
    HEDGING_PHRASES,
    REDACTION_PHRASES,
    generate_tone_json,
    validate_tone_safety,
)


class TestHardConstraints:
    """Test that hard constraints are always present and correct."""

    def test_tone_json_has_hard_constraints(self):
        """Verify hard_constraints section exists."""
        profile = ToneProfile()
        tone_json = generate_tone_json(profile, doc_count=100)

        assert "hard_constraints" in tone_json
        hc = tone_json["hard_constraints"]

        assert hc["emojis_allowed"] == 0
        assert hc["hashtags_allowed"] == 0
        assert hc["names_allowed"] is False
        assert hc["victims_allowed"] is False
        assert hc["explicit_content_allowed"] is False
        assert hc["pii_allowed"] is False

    def test_hard_constraints_cannot_be_overridden(self):
        """Verify note about constraints being absolute."""
        profile = ToneProfile()
        tone_json = generate_tone_json(profile, doc_count=100)

        assert "ABSOLUTE" in tone_json["hard_constraints"]["note"]
        assert "CANNOT be overridden" in tone_json["hard_constraints"]["note"]


class TestSafetyValidation:
    """Test the validate_tone_safety function."""

    def test_valid_tone_passes(self):
        """A properly generated tone should pass validation."""
        profile = ToneProfile()
        tone_json = generate_tone_json(profile, doc_count=100)

        is_safe, violations = validate_tone_safety(tone_json)

        assert is_safe is True
        assert len(violations) == 0

    def test_missing_hard_constraints_fails(self):
        """Missing hard_constraints should fail."""
        tone_json = {"cadence": {"patterns": []}}

        is_safe, violations = validate_tone_safety(tone_json)

        assert is_safe is False
        assert "Missing hard_constraints section" in violations

    def test_emojis_allowed_fails(self):
        """Allowing emojis should fail."""
        profile = ToneProfile()
        tone_json = generate_tone_json(profile, doc_count=100)
        tone_json["hard_constraints"]["emojis_allowed"] = 1

        is_safe, violations = validate_tone_safety(tone_json)

        assert is_safe is False
        assert "Emojis must be disallowed" in violations

    def test_hashtags_allowed_fails(self):
        """Allowing hashtags should fail."""
        profile = ToneProfile()
        tone_json = generate_tone_json(profile, doc_count=100)
        tone_json["hard_constraints"]["hashtags_allowed"] = 1

        is_safe, violations = validate_tone_safety(tone_json)

        assert is_safe is False
        assert "Hashtags must be disallowed" in violations

    def test_names_allowed_fails(self):
        """Allowing names should fail."""
        profile = ToneProfile()
        tone_json = generate_tone_json(profile, doc_count=100)
        tone_json["hard_constraints"]["names_allowed"] = True

        is_safe, violations = validate_tone_safety(tone_json)

        assert is_safe is False
        assert "Names must be disallowed" in violations


class TestCadencePatterns:
    """Test that cadence patterns are safe and appropriate."""

    def test_patterns_are_generic(self):
        """Patterns should be generic legal speak, no specific names."""
        for pattern in CASEFILE_CADENCE_PATTERNS:
            # No proper nouns (capitalized words that aren't at start)
            words = pattern.split()
            for i, word in enumerate(words[1:], 1):  # Skip first word
                # Skip "The" and common transitional words
                if word in ["The", "Upon", "For", "In", "As", "Of", "It"]:
                    continue
                # Check it's not a potential name (capitalized mid-sentence)
                assert not (word[0].isupper() and word.lower() not in ["i"]), \
                    f"Potential name found in pattern: {word}"

    def test_no_victim_related_words(self):
        """Patterns should not contain victim-related terminology."""
        blocked_words = ["victim", "survivor", "minor", "child", "abuse", "assault"]
        all_patterns = CASEFILE_CADENCE_PATTERNS + TRANSITIONAL_PHRASES + HEDGING_PHRASES

        for pattern in all_patterns:
            pattern_lower = pattern.lower()
            for blocked in blocked_words:
                assert blocked not in pattern_lower, \
                    f"Blocked word '{blocked}' found in: {pattern}"

    def test_no_explicit_content_words(self):
        """Patterns should not contain explicit content."""
        blocked_words = ["sexual", "explicit", "nude", "graphic"]
        all_patterns = CASEFILE_CADENCE_PATTERNS + TRANSITIONAL_PHRASES + HEDGING_PHRASES

        for pattern in all_patterns:
            pattern_lower = pattern.lower()
            for blocked in blocked_words:
                assert blocked not in pattern_lower, \
                    f"Blocked word '{blocked}' found in: {pattern}"


class TestRedactionPhrases:
    """Test redaction phrases for safety."""

    def test_redaction_phrases_are_generic(self):
        """Redaction phrases should be generic placeholders."""
        for phrase in REDACTION_PHRASES:
            # Should contain generic terms, not specific references
            assert any(generic in phrase.lower() for generic in [
                "redacted", "withheld", "sealed", "classified",
                "certain", "unnamed", "relevant", "associated", "subject"
            ]), f"Phrase doesn't look like generic redaction: {phrase}"


class TestToneJsonStructure:
    """Test overall tone JSON structure."""

    def test_required_sections_present(self):
        """All required sections should be present."""
        profile = ToneProfile()
        tone_json = generate_tone_json(profile, doc_count=100)

        required_sections = [
            "generated_at",
            "source",
            "version",
            "description",
            "hard_constraints",
            "cadence",
            "transitions",
            "hedging",
            "redaction_humor",
            "blend_settings",
            "examples",
            "metadata",
        ]

        for section in required_sections:
            assert section in tone_json, f"Missing required section: {section}"

    def test_content_derived_is_false(self):
        """Content should NOT be derived from actual documents."""
        profile = ToneProfile()
        tone_json = generate_tone_json(profile, doc_count=100)

        assert tone_json["metadata"]["content_derived"] is False
        assert tone_json["metadata"]["extraction_method"] == "pre_defined_patterns"

    def test_blend_weight_is_reasonable(self):
        """Blend weight should be low (subtle influence)."""
        profile = ToneProfile()
        tone_json = generate_tone_json(profile, doc_count=100)

        weight = tone_json["blend_settings"]["weight"]
        assert 0 < weight <= 0.25, "Blend weight should be subtle (0-0.25)"


class TestExamples:
    """Test that examples comply with brand rules."""

    def test_examples_have_no_emojis(self):
        """Example outputs should have no emojis."""
        profile = ToneProfile()
        tone_json = generate_tone_json(profile, doc_count=100)

        examples = tone_json.get("examples", {})
        for key, example in examples.items():
            # Check for common emoji unicode ranges
            for char in example:
                code = ord(char)
                # Emoji ranges
                is_emoji = (
                    0x1F600 <= code <= 0x1F64F or  # Emoticons
                    0x1F300 <= code <= 0x1F5FF or  # Symbols
                    0x1F680 <= code <= 0x1F6FF or  # Transport
                    0x2600 <= code <= 0x26FF or    # Misc
                    0x2700 <= code <= 0x27BF       # Dingbats
                )
                assert not is_emoji, f"Emoji found in example '{key}': {char}"

    def test_examples_have_no_hashtags(self):
        """Example outputs should have no hashtags."""
        profile = ToneProfile()
        tone_json = generate_tone_json(profile, doc_count=100)

        examples = tone_json.get("examples", {})
        for key, example in examples.items():
            assert "#" not in example or example.count("#") == 0, \
                f"Hashtag found in example '{key}'"
