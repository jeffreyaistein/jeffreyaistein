"""
Jeffrey AIstein - KOL Pipeline Tests

Tests for:
- Tweet extractor (extract_kol_tweets.py)
- Style analyzer (style_dataset/analyzer.py)
- KOL profile generator (generate_kol_profiles.py)
"""

import json
import tempfile
from pathlib import Path

import pytest


class TestTweetExtractor:
    """Tests for extract_kol_tweets.py functions."""

    def test_hash_text_deterministic(self):
        """Hash function produces consistent output."""
        from scripts.extract_kol_tweets import hash_text

        text = "gm crypto twitter"
        hash1 = hash_text(text)
        hash2 = hash_text(text)
        assert hash1 == hash2
        assert len(hash1) == 16

    def test_hash_text_different_inputs(self):
        """Different inputs produce different hashes."""
        from scripts.extract_kol_tweets import hash_text

        hash1 = hash_text("gm")
        hash2 = hash_text("gn")
        assert hash1 != hash2

    def test_sanitize_cube_references_in_text(self):
        """CUBE references in tweet text are replaced."""
        from scripts.extract_kol_tweets import sanitize_cube_references

        result = sanitize_cube_references("Buy CUBE token now!", "text")
        assert "CUBE" not in result
        assert "AIstein" in result

    def test_sanitize_cube_references_preserves_other_text(self):
        """Non-CUBE text is preserved."""
        from scripts.extract_kol_tweets import sanitize_cube_references

        original = "gm ct, lfg on solana"
        result = sanitize_cube_references(original, "text")
        assert result == original

    def test_deduplicate_tweets_removes_exact_duplicates(self):
        """Deduplication removes tweets with same text hash."""
        from scripts.extract_kol_tweets import deduplicate_tweets

        tweets = [
            {"text": "gm", "handle": "user1", "tweet_id": None},
            {"text": "gm", "handle": "user2", "tweet_id": None},  # duplicate
            {"text": "gn", "handle": "user1", "tweet_id": None},
        ]

        unique, duplicates = deduplicate_tweets(tweets)
        assert len(unique) == 2
        assert duplicates == 1

    def test_deduplicate_tweets_uses_tweet_id_when_available(self):
        """Deduplication prefers tweet_id over text hash."""
        from scripts.extract_kol_tweets import deduplicate_tweets

        tweets = [
            {"text": "different text 1", "handle": "user1", "tweet_id": "123"},
            {"text": "different text 2", "handle": "user2", "tweet_id": "123"},  # same id
        ]

        unique, duplicates = deduplicate_tweets(tweets)
        assert len(unique) == 1
        assert duplicates == 1


class TestStyleAnalyzer:
    """Tests for style_dataset/analyzer.py."""

    @pytest.fixture
    def sample_jsonl(self, tmp_path):
        """Create a sample JSONL file for testing."""
        jsonl_path = tmp_path / "test_tweets.jsonl"
        tweets = [
            {"text": "gm ct! another beautiful day in crypto 🚀", "handle": "user1"},
            {"text": "just aped into this new project, nfa", "handle": "user2"},
            {"text": "thoughts on solana? been watching the charts", "handle": "user3"},
            {"text": "lfg", "handle": "user4"},
            {"text": "the market is looking bullish rn", "handle": "user5"},
        ]
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for t in tweets:
                f.write(json.dumps(t) + "\n")
        return jsonl_path

    def test_analyzer_processes_jsonl(self, sample_jsonl):
        """Analyzer can read and process JSONL file."""
        from services.social.style_dataset.analyzer import StyleAnalyzer

        analyzer = StyleAnalyzer()
        profile = analyzer.analyze_dataset(sample_jsonl)

        assert profile.avg_length > 0
        assert 0 <= profile.emoji_usage_pct <= 100
        assert 0 <= profile.question_pct <= 100

    def test_analyzer_detects_ct_vocab(self, sample_jsonl):
        """Analyzer detects CT vocabulary."""
        from services.social.style_dataset.analyzer import StyleAnalyzer

        analyzer = StyleAnalyzer()
        profile = analyzer.analyze_dataset(sample_jsonl)

        # Should detect gm, lfg, nfa, ape
        assert len(profile.ct_vocab_frequency) > 0
        assert "gm" in profile.ct_vocab_frequency or "lfg" in profile.ct_vocab_frequency

    def test_analyzer_generates_rules(self, sample_jsonl):
        """Analyzer generates style rules."""
        from services.social.style_dataset.analyzer import StyleAnalyzer

        analyzer = StyleAnalyzer()
        profile = analyzer.analyze_dataset(sample_jsonl)

        assert len(profile.rules) > 0

    def test_analyzer_generates_markdown(self, sample_jsonl, tmp_path):
        """Analyzer generates markdown output."""
        from services.social.style_dataset.analyzer import StyleAnalyzer

        md_path = tmp_path / "test_style_guide.md"
        analyzer = StyleAnalyzer()
        profile = analyzer.analyze_dataset(sample_jsonl)
        result_path = analyzer.generate_markdown(profile, md_path)

        assert result_path.exists()
        content = result_path.read_text()
        assert "Tweet Length Patterns" in content
        assert "CT Vocabulary" in content

    def test_analyzer_generates_json(self, sample_jsonl, tmp_path):
        """Analyzer generates JSON output."""
        from services.social.style_dataset.analyzer import StyleAnalyzer

        json_path = tmp_path / "test_style_guide.json"
        analyzer = StyleAnalyzer()
        profile = analyzer.analyze_dataset(sample_jsonl)
        result_path = analyzer.generate_json(profile, json_path)

        assert result_path.exists()
        with open(result_path) as f:
            data = json.load(f)
        assert "patterns" in data
        assert "rules" in data
        assert "rewriting" in data


class TestKOLProfileExtractor:
    """Tests for extract_kol_profiles.py."""

    @pytest.fixture
    def sample_kol_json(self, tmp_path):
        """Create sample KOL data for testing."""
        json_path = tmp_path / "test_kol_data.json"
        data = [
            {
                "handle": "testuser1",
                "category": "alpha_caller|degen_trader",
                "notes": json.dumps({
                    "personality_summary": "A bold trader with aggressive takes",
                    "tone": "aggressive | hype_beast",
                    "credibility_score": 7,
                    "influence_reach": "medium",
                    "engagement_playbook": {
                        "best_approach": "Match their energy with confidence",
                        "topics_they_respond_to": ["market analysis", "alpha"],
                        "avoid_topics": ["politics"],
                        "collab_potential": "high",
                    },
                    "sample_tweets": ["gm ct", "bullish on sol"],
                }),
            },
            {
                "handle": "testuser2",
                "category": "influencer",
                "notes": json.dumps({
                    "personality_summary": "Chill vibes educator",
                    "tone": "chill | educational",
                    "credibility_score": 9,
                    "influence_reach": "high",
                    "engagement_playbook": {
                        "best_approach": "Be respectful and add value",
                    },
                    "sample_tweets": ["learning is key"],
                }),
            },
        ]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return json_path

    def test_extract_key_traits(self):
        """Key traits extracted from tone field."""
        from scripts.extract_kol_profiles import extract_key_traits

        notes = {"tone": "aggressive | hype_beast"}
        traits = extract_key_traits(notes)

        assert len(traits) <= 2
        assert "aggressive" in traits

    def test_extract_risk_flags(self):
        """Risk flags are extracted from profile notes."""
        from scripts.extract_kol_profiles import extract_risk_flags

        notes = {"credibility_score": 3}
        playbook = {"avoid_topics": ["politics", "controversy"]}
        flags = extract_risk_flags(notes, playbook)

        assert "low_credibility" in flags
        assert "avoid_politics" in flags

    def test_extract_risk_flags_high_cred(self):
        """High credibility flag is set for score >= 8."""
        from scripts.extract_kol_profiles import extract_risk_flags

        notes = {"credibility_score": 9}
        playbook = {}
        flags = extract_risk_flags(notes, playbook)

        assert "high_credibility" in flags

    def test_sanitize_cube_refs(self):
        """CUBE references are replaced with AIstein."""
        from scripts.extract_kol_profiles import sanitize_cube_refs

        assert sanitize_cube_refs("Buy CUBE now") == "Buy AIstein now"
        assert sanitize_cube_refs("lowercase cube") == "lowercase AIstein"
        assert sanitize_cube_refs(None) is None
        assert sanitize_cube_refs("") == ""

    def test_process_kol_data(self, sample_kol_json):
        """Profile extraction works with sample data."""
        from scripts.extract_kol_profiles import process_kol_data

        profiles = process_kol_data(sample_kol_json)

        assert len(profiles) == 2
        assert profiles[0]["handle"] == "testuser1"
        assert profiles[0]["credibility_score"] == 7
        assert profiles[1]["credibility_score"] == 9


class TestKOLProfileLoader:
    """Tests for services/persona/kol_profiles.py."""

    @pytest.fixture
    def sample_profiles_json(self, tmp_path):
        """Create sample profiles JSON for testing."""
        json_path = tmp_path / "test_kol_profiles.json"
        data = {
            "generated_at": "2026-02-02T00:00:00Z",
            "profile_count": 3,
            "profiles": {
                "highcred": {
                    "cred": 9,
                    "reach": "high",
                    "traits": ["aggressive", "hype"],
                    "notes": "Match their energy",
                    "flags": ["high_credibility"],
                    "topics": ["alpha", "defi"],
                    "avoid": [],
                },
                "lowcred": {
                    "cred": 3,
                    "reach": "low",
                    "traits": [],
                    "notes": "",
                    "flags": ["low_credibility"],
                    "topics": [],
                    "avoid": ["politics"],
                },
                "midcred": {
                    "cred": 6,
                    "reach": "medium",
                    "traits": ["chill"],
                    "notes": "Standard engagement",
                    "flags": [],
                    "topics": ["nfts"],
                    "avoid": [],
                },
            },
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return json_path

    def test_loader_loads_profiles(self, sample_profiles_json):
        """Loader loads profiles from JSON file."""
        from services.persona.kol_profiles import KOLProfileLoader

        loader = KOLProfileLoader(sample_profiles_json)

        assert loader.is_available()
        assert loader.profile_count == 3

    def test_loader_get_profile(self, sample_profiles_json):
        """Loader retrieves profile by handle."""
        from services.persona.kol_profiles import KOLProfileLoader

        loader = KOLProfileLoader(sample_profiles_json)

        profile = loader.get_profile("highcred")
        assert profile is not None
        assert profile.credibility == 9
        assert profile.is_high_credibility

        profile_low = loader.get_profile("lowcred")
        assert profile_low is not None
        assert profile_low.is_low_credibility

    def test_loader_handles_at_prefix(self, sample_profiles_json):
        """Loader handles @ prefix in handle lookup."""
        from services.persona.kol_profiles import KOLProfileLoader

        loader = KOLProfileLoader(sample_profiles_json)

        profile = loader.get_profile("@highcred")
        assert profile is not None
        assert profile.handle == "highcred"

    def test_loader_unknown_handle(self, sample_profiles_json):
        """Loader returns None for unknown handles."""
        from services.persona.kol_profiles import KOLProfileLoader

        loader = KOLProfileLoader(sample_profiles_json)

        profile = loader.get_profile("nonexistent")
        assert profile is None

    def test_engagement_context_high_cred(self, sample_profiles_json):
        """High-cred profile generates appropriate context."""
        from services.persona.kol_profiles import KOLProfileLoader

        loader = KOLProfileLoader(sample_profiles_json)
        context = loader.get_engagement_context("highcred")

        assert context is not None
        assert "respected voice" in context.lower()
        assert "9/10" in context

    def test_engagement_context_low_cred(self, sample_profiles_json):
        """Low-cred profile generates caution context."""
        from services.persona.kol_profiles import KOLProfileLoader

        loader = KOLProfileLoader(sample_profiles_json)
        context = loader.get_engagement_context("lowcred")

        assert context is not None
        assert "caution" in context.lower()

    def test_is_known_kol(self, sample_profiles_json):
        """is_known_kol returns correct boolean."""
        from services.persona.kol_profiles import KOLProfileLoader

        loader = KOLProfileLoader(sample_profiles_json)

        assert loader.is_known_kol("highcred") is True
        assert loader.is_known_kol("@midcred") is True
        assert loader.is_known_kol("unknown") is False
