"""
Jeffrey AIstein - Style Version Admin Endpoint Tests

Tests for the style guide version management endpoints:
- GET /api/admin/persona/style/versions
- POST /api/admin/persona/style/activate
- POST /api/admin/persona/style/rollback
- GET /api/admin/persona/style/status

Note: These tests focus on auth validation and request validation.
Full integration tests require a database fixture.
"""

import json
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


# Test admin key - set in environment
TEST_ADMIN_KEY = "test-admin-key-12345"


@pytest.fixture(autouse=True)
def set_test_env():
    """Set test environment variables."""
    original = os.environ.get("ADMIN_API_KEY")
    os.environ["ADMIN_API_KEY"] = TEST_ADMIN_KEY
    yield
    if original:
        os.environ["ADMIN_API_KEY"] = original
    else:
        os.environ.pop("ADMIN_API_KEY", None)


@pytest.fixture
def client():
    """Create test client."""
    # Need to reload settings with new env var
    with patch("config.settings.admin_api_key", TEST_ADMIN_KEY):
        with patch("auth.session.settings.admin_api_key", TEST_ADMIN_KEY):
            from main import app
            yield TestClient(app)


@pytest.fixture
def admin_headers():
    """Headers with admin key."""
    return {"X-Admin-Key": TEST_ADMIN_KEY}


class TestListVersionsAuth:
    """Auth tests for GET /api/admin/persona/style/versions."""

    def test_requires_admin_key(self, client):
        """Endpoint requires admin authentication."""
        response = client.get("/api/admin/persona/style/versions")
        assert response.status_code == 401
        assert "Admin API key required" in response.json()["detail"]

    def test_invalid_admin_key(self, client):
        """Invalid admin key is rejected."""
        response = client.get(
            "/api/admin/persona/style/versions",
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert response.status_code == 403
        assert "Invalid admin API key" in response.json()["detail"]

    def test_bearer_auth_supported(self, client):
        """Authorization: Bearer header is also accepted."""
        response = client.get(
            "/api/admin/persona/style/versions",
            headers={"Authorization": f"Bearer wrong-key"},
        )
        # Wrong key, but recognized as auth attempt
        assert response.status_code == 403


class TestActivateVersionAuth:
    """Auth tests for POST /api/admin/persona/style/activate."""

    def test_requires_admin_key(self, client):
        """Endpoint requires admin authentication."""
        response = client.post(
            "/api/admin/persona/style/activate",
            json={"version_id": "test"},
        )
        assert response.status_code == 401

    def test_requires_version_id(self, client, admin_headers):
        """Request body must include version_id."""
        response = client.post(
            "/api/admin/persona/style/activate",
            json={},
            headers=admin_headers,
        )
        # Pydantic validation error
        assert response.status_code == 422


class TestRollbackVersionAuth:
    """Auth tests for POST /api/admin/persona/style/rollback."""

    def test_requires_admin_key(self, client):
        """Endpoint requires admin authentication."""
        response = client.post(
            "/api/admin/persona/style/rollback",
            json={"previous": True},
        )
        assert response.status_code == 401


class TestStyleStatusAuth:
    """Auth tests for GET /api/admin/persona/style/status."""

    def test_requires_admin_key(self, client):
        """Endpoint requires admin authentication."""
        response = client.get("/api/admin/persona/style/status")
        assert response.status_code == 401


class TestHardConstraintValidation:
    """Tests for hard constraint validation in activation."""

    def test_validate_hard_constraints_accepts_valid(self):
        """Valid guide with correct constraints passes."""
        from services.persona.style_rewriter import _validate_hard_constraints

        valid_guide = {
            "hard_constraints": {
                "emojis_allowed": 0,
                "hashtags_allowed": 0,
            }
        }
        is_valid, error = _validate_hard_constraints(valid_guide)
        assert is_valid is True
        assert error == ""

    def test_validate_hard_constraints_rejects_emojis(self):
        """Guide with emojis_allowed != 0 fails."""
        from services.persona.style_rewriter import _validate_hard_constraints

        invalid_guide = {
            "hard_constraints": {
                "emojis_allowed": 1,
                "hashtags_allowed": 0,
            }
        }
        is_valid, error = _validate_hard_constraints(invalid_guide)
        assert is_valid is False
        assert "emojis_allowed" in error

    def test_validate_hard_constraints_rejects_hashtags(self):
        """Guide with hashtags_allowed != 0 fails."""
        from services.persona.style_rewriter import _validate_hard_constraints

        invalid_guide = {
            "hard_constraints": {
                "emojis_allowed": 0,
                "hashtags_allowed": 3,
            }
        }
        is_valid, error = _validate_hard_constraints(invalid_guide)
        assert is_valid is False
        assert "hashtags_allowed" in error

    def test_validate_hard_constraints_rejects_missing(self):
        """Guide without hard_constraints section fails."""
        from services.persona.style_rewriter import _validate_hard_constraints

        invalid_guide = {"rules": ["test"]}
        is_valid, error = _validate_hard_constraints(invalid_guide)
        assert is_valid is False


class TestRequestModels:
    """Tests for Pydantic request models."""

    def test_activate_request_model(self):
        """ActivateStyleVersionRequest validates correctly."""
        from main import ActivateStyleVersionRequest

        # Valid request
        req = ActivateStyleVersionRequest(version_id="20260203_120000")
        assert req.version_id == "20260203_120000"

    def test_rollback_request_model(self):
        """RollbackStyleVersionRequest validates correctly."""
        from main import RollbackStyleVersionRequest

        # With version_id
        req1 = RollbackStyleVersionRequest(version_id="20260203_120000")
        assert req1.version_id == "20260203_120000"
        assert req1.previous is False

        # With previous=True
        req2 = RollbackStyleVersionRequest(previous=True)
        assert req2.previous is True
        assert req2.version_id is None

        # Empty (defaults)
        req3 = RollbackStyleVersionRequest()
        assert req3.version_id is None
        assert req3.previous is False


class TestStyleRewriterIntegration:
    """Tests for StyleRewriter methods used by endpoints."""

    def test_get_status_returns_expected_fields(self):
        """get_status returns expected structure."""
        from services.persona.style_rewriter import StyleRewriter, reset_style_rewriter

        reset_style_rewriter()

        # Create rewriter with no DB
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            baseline = {
                "hard_constraints": {
                    "emojis_allowed": 0,
                    "hashtags_allowed": 0,
                },
                "rewriting": {"target_length": 150, "max_length": 280},
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
        finally:
            baseline_path.unlink()
            reset_style_rewriter()

    def test_reload_functions_exist(self):
        """Module-level reload functions are importable."""
        from services.persona.style_rewriter import (
            reload_style_rewriter,
            reload_style_rewriter_async,
        )

        # Just verify they're callable
        assert callable(reload_style_rewriter)
        assert callable(reload_style_rewriter_async)
