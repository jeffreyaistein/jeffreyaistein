"""
Jeffrey AIstein - StyleRewriter Loader Tests

Tests for the DB-backed style guide loading:
- Loads baseline when no active version
- Loads proposal when active version exists
- Refuses to load proposal missing hard constraints
- Reload switches guide without restart
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from services.persona.style_rewriter import (
    StyleRewriter,
    _validate_hard_constraints,
    get_style_rewriter,
    reset_style_rewriter,
    reload_style_rewriter,
)


class TestHardConstraintValidation:
    """Tests for hard constraint validation."""

    def test_valid_constraints(self):
        """Guide with correct hard constraints passes validation."""
        guide = {
            "hard_constraints": {
                "emojis_allowed": 0,
                "hashtags_allowed": 0,
            }
        }
        is_valid, error = _validate_hard_constraints(guide)
        assert is_valid is True
        assert error == ""

    def test_missing_hard_constraints_section(self):
        """Guide without hard_constraints section fails."""
        guide = {"rules": ["some rule"]}
        is_valid, error = _validate_hard_constraints(guide)
        assert is_valid is False
        assert "emojis_allowed" in error

    def test_emojis_allowed_not_zero(self):
        """Guide with emojis_allowed != 0 fails."""
        guide = {
            "hard_constraints": {
                "emojis_allowed": 1,
                "hashtags_allowed": 0,
            }
        }
        is_valid, error = _validate_hard_constraints(guide)
        assert is_valid is False
        assert "emojis_allowed must be 0" in error

    def test_hashtags_allowed_not_zero(self):
        """Guide with hashtags_allowed != 0 fails."""
        guide = {
            "hard_constraints": {
                "emojis_allowed": 0,
                "hashtags_allowed": 2,
            }
        }
        is_valid, error = _validate_hard_constraints(guide)
        assert is_valid is False
        assert "hashtags_allowed must be 0" in error

    def test_emojis_allowed_missing(self):
        """Guide with missing emojis_allowed fails."""
        guide = {
            "hard_constraints": {
                "hashtags_allowed": 0,
            }
        }
        is_valid, error = _validate_hard_constraints(guide)
        assert is_valid is False
        assert "emojis_allowed must be 0" in error

    def test_hashtags_allowed_missing(self):
        """Guide with missing hashtags_allowed fails."""
        guide = {
            "hard_constraints": {
                "emojis_allowed": 0,
            }
        }
        is_valid, error = _validate_hard_constraints(guide)
        assert is_valid is False
        assert "hashtags_allowed must be 0" in error


class TestBaselineLoading:
    """Tests for baseline style guide loading."""

    def test_loads_baseline_when_no_db(self):
        """Loads baseline when database is not available."""
        reset_style_rewriter()

        # Create a temporary baseline file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            baseline = {
                "generated_at": "2026-01-01T00:00:00Z",
                "source": "test_baseline",
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 0,
                },
                "rewriting": {
                    "target_length": 150,
                    "max_length": 280,
                },
            }
            json.dump(baseline, f)
            baseline_path = Path(f.name)

        try:
            # Create rewriter with DB disabled
            rewriter = StyleRewriter(
                style_guide_path=baseline_path,
                use_database=False,
            )

            assert rewriter.is_available() is True
            assert rewriter.get_guide_source() == "baseline"
            assert rewriter.get_active_version_id() is None
            assert rewriter.get_target_length() == 150
        finally:
            baseline_path.unlink()

    def test_loads_baseline_when_no_active_version(self):
        """Loads baseline when no active version in DB."""
        reset_style_rewriter()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            baseline = {
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 0,
                },
                "rewriting": {"target_length": 200},
            }
            json.dump(baseline, f)
            baseline_path = Path(f.name)

        try:
            # Mock DB to return no active version
            with patch("services.persona.style_rewriter.StyleRewriter._load_from_database") as mock_db:
                mock_db.return_value = None

                rewriter = StyleRewriter(
                    style_guide_path=baseline_path,
                    use_database=True,
                )

                assert rewriter.is_available() is True
                assert rewriter.get_guide_source() == "baseline"
                assert rewriter.get_active_version_id() is None
        finally:
            baseline_path.unlink()


class TestProposalLoading:
    """Tests for loading proposals from database."""

    def test_loads_proposal_when_active_version_exists(self):
        """Loads proposal from DB when active version exists."""
        reset_style_rewriter()

        # Create a proposal file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            proposal = {
                "version_id": "20260203_123456",
                "generated_at": "2026-02-03T12:34:56Z",
                "source": "self_style",
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 0,
                },
                "rewriting": {"target_length": 180},
            }
            json.dump(proposal, f)
            proposal_path = Path(f.name)

        # Create a baseline file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            baseline = {
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 0,
                },
                "rewriting": {"target_length": 200},
            }
            json.dump(baseline, f)
            baseline_path = Path(f.name)

        try:
            # Mock DB to return active version
            with patch("services.persona.style_rewriter.StyleRewriter._load_from_database") as mock_db:
                mock_db.return_value = (proposal, "20260203_123456")

                rewriter = StyleRewriter(
                    style_guide_path=baseline_path,
                    use_database=True,
                )

                assert rewriter.is_available() is True
                assert rewriter.get_guide_source() == "database"
                assert rewriter.get_active_version_id() == "20260203_123456"
                assert rewriter.get_target_length() == 180
        finally:
            proposal_path.unlink()
            baseline_path.unlink()


class TestRefuseInvalidProposal:
    """Tests for refusing invalid proposals."""

    def test_refuses_proposal_missing_emojis_allowed(self):
        """Refuses proposal without emojis_allowed=0."""
        reset_style_rewriter()

        # Create baseline
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            baseline = {
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 0,
                },
                "rewriting": {"target_length": 200},
            }
            json.dump(baseline, f)
            baseline_path = Path(f.name)

        try:
            # Invalid proposal - emojis_allowed = 1
            invalid_proposal = {
                "version_id": "20260203_bad",
                "hard_constraints": {
                    "emojis_allowed": 1,  # INVALID
                    "hashtags_allowed": 0,
                },
            }

            with patch("services.persona.style_rewriter.StyleRewriter._load_from_database") as mock_db:
                mock_db.return_value = (invalid_proposal, "20260203_bad")

                rewriter = StyleRewriter(
                    style_guide_path=baseline_path,
                    use_database=True,
                )

                # Should fall back to baseline, not use invalid proposal
                assert rewriter.is_available() is True
                assert rewriter.get_guide_source() == "baseline"
                assert rewriter.get_active_version_id() is None
        finally:
            baseline_path.unlink()

    def test_refuses_proposal_missing_hashtags_allowed(self):
        """Refuses proposal without hashtags_allowed=0."""
        reset_style_rewriter()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            baseline = {
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 0,
                },
            }
            json.dump(baseline, f)
            baseline_path = Path(f.name)

        try:
            invalid_proposal = {
                "version_id": "20260203_bad",
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 5,  # INVALID
                },
            }

            with patch("services.persona.style_rewriter.StyleRewriter._load_from_database") as mock_db:
                mock_db.return_value = (invalid_proposal, "20260203_bad")

                rewriter = StyleRewriter(
                    style_guide_path=baseline_path,
                    use_database=True,
                )

                assert rewriter.get_guide_source() == "baseline"
                assert rewriter.get_active_version_id() is None
        finally:
            baseline_path.unlink()

    def test_refuses_proposal_missing_hard_constraints(self):
        """Refuses proposal without hard_constraints section."""
        reset_style_rewriter()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            baseline = {
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 0,
                },
            }
            json.dump(baseline, f)
            baseline_path = Path(f.name)

        try:
            invalid_proposal = {
                "version_id": "20260203_bad",
                "rules": ["some rule"],
                # No hard_constraints section
            }

            with patch("services.persona.style_rewriter.StyleRewriter._load_from_database") as mock_db:
                mock_db.return_value = (invalid_proposal, "20260203_bad")

                rewriter = StyleRewriter(
                    style_guide_path=baseline_path,
                    use_database=True,
                )

                assert rewriter.get_guide_source() == "baseline"
        finally:
            baseline_path.unlink()


class TestReload:
    """Tests for hot reload functionality."""

    def test_reload_switches_guide(self):
        """Reload switches from baseline to proposal."""
        reset_style_rewriter()

        # Create baseline
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            baseline = {
                "source": "baseline",
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 0,
                },
                "rewriting": {"target_length": 200},
            }
            json.dump(baseline, f)
            baseline_path = Path(f.name)

        try:
            # Initially no active version
            with patch("services.persona.style_rewriter.StyleRewriter._load_from_database") as mock_db:
                mock_db.return_value = None

                rewriter = StyleRewriter(
                    style_guide_path=baseline_path,
                    use_database=True,
                )

                assert rewriter.get_guide_source() == "baseline"
                assert rewriter.get_target_length() == 200

            # Now simulate activating a proposal
            new_proposal = {
                "version_id": "20260203_new",
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 0,
                },
                "rewriting": {"target_length": 150},
            }

            with patch.object(rewriter, "_load_from_database") as mock_db:
                mock_db.return_value = (new_proposal, "20260203_new")

                # Reload
                result = rewriter.reload()

                assert result is True
                assert rewriter.get_guide_source() == "database"
                assert rewriter.get_active_version_id() == "20260203_new"
                assert rewriter.get_target_length() == 150
        finally:
            baseline_path.unlink()

    def test_reload_keeps_previous_on_failure(self):
        """Reload keeps previous guide if loading fails."""
        reset_style_rewriter()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            baseline = {
                "source": "baseline",
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 0,
                },
                "rewriting": {"target_length": 200},
            }
            json.dump(baseline, f)
            baseline_path = Path(f.name)

        try:
            # Load baseline initially
            with patch("services.persona.style_rewriter.StyleRewriter._load_from_database") as mock_db:
                mock_db.return_value = None

                rewriter = StyleRewriter(
                    style_guide_path=baseline_path,
                    use_database=True,
                )

                assert rewriter.get_guide_source() == "baseline"

            # Now try to reload with invalid proposal
            invalid_proposal = {
                "version_id": "20260203_bad",
                "hard_constraints": {
                    "emojis_allowed": 5,  # INVALID
                    "hashtags_allowed": 0,
                },
            }

            with patch.object(rewriter, "_load_from_database") as mock_db:
                mock_db.return_value = (invalid_proposal, "20260203_bad")

                # Also mock _load_from_baseline to return None (simulate missing file)
                with patch.object(rewriter, "_load_from_baseline") as mock_baseline:
                    mock_baseline.return_value = None

                    # Reload should keep previous
                    result = rewriter.reload()

                    # Previous guide should be preserved
                    assert rewriter.is_available() is True
                    assert rewriter.get_guide_source() == "baseline"
        finally:
            baseline_path.unlink()


class TestSingleton:
    """Tests for singleton behavior."""

    def test_singleton_returns_same_instance(self):
        """get_style_rewriter returns same instance."""
        reset_style_rewriter()

        rewriter1 = get_style_rewriter()
        rewriter2 = get_style_rewriter()

        assert rewriter1 is rewriter2

    def test_reset_clears_singleton(self):
        """reset_style_rewriter clears the singleton."""
        reset_style_rewriter()

        rewriter1 = get_style_rewriter()
        reset_style_rewriter()
        rewriter2 = get_style_rewriter()

        assert rewriter1 is not rewriter2


class TestStatusMethod:
    """Tests for get_status method."""

    def test_status_contains_expected_fields(self):
        """Status dict contains all expected fields."""
        reset_style_rewriter()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            baseline = {
                "generated_at": "2026-01-01T00:00:00Z",
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 0,
                },
                "rewriting": {
                    "target_length": 150,
                    "max_length": 280,
                },
            }
            json.dump(baseline, f)
            baseline_path = Path(f.name)

        try:
            rewriter = StyleRewriter(
                style_guide_path=baseline_path,
                use_database=False,
            )

            status = rewriter.get_status()

            assert "available" in status
            assert "source" in status
            assert "active_version_id" in status
            assert "generated_at" in status
            assert "target_length" in status
            assert "max_length" in status

            assert status["available"] is True
            assert status["source"] == "baseline"
            assert status["active_version_id"] is None
            assert status["target_length"] == 150
            assert status["max_length"] == 280
        finally:
            baseline_path.unlink()
