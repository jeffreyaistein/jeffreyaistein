"""
Jeffrey AIstein - Self-Style Admin Endpoint Tests

Tests for admin endpoint response shapes including self_style_worker fields.
Verifies fields appear even when worker is disabled.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


class TestStyleStatusEndpointShape:
    """Tests for GET /api/admin/persona/style/status response shape."""

    @pytest.mark.asyncio
    async def test_response_includes_self_style_worker_when_disabled(self):
        """Response includes self_style_worker even when disabled."""
        # Create a mock worker that's disabled
        mock_worker = MagicMock()
        mock_worker.get_stats.return_value = {
            "enabled": False,
            "disabled_reason": "disabled",
            "last_run_status": None,
            "last_run_started_at": None,
            "last_run_finished_at": None,
            "last_error": None,
            "last_proposal_version_id": None,
            "total_proposals_generated": 0,
            "total_proposals_skipped": 0,
            "leader_lock": {
                "lock_key": "self_style:leader",
                "lock_ttl_seconds": 300,
                "currently_acquired": False,
                "instance_id": "test-instance",
                "total_acquisitions": 0,
                "total_failures": 0,
            },
        }

        with patch("main.get_self_style_worker", return_value=mock_worker):
            with patch("main.get_style_rewriter") as mock_rewriter:
                mock_rewriter.return_value.get_status.return_value = {"source": "baseline"}

                # Mock DB queries
                mock_db = AsyncMock()
                mock_result = MagicMock()
                mock_result.mappings.return_value.fetchone.return_value = None
                mock_db.execute.return_value = mock_result

                from main import admin_get_style_status
                from fastapi import Request

                # Create mock request with admin key
                mock_request = MagicMock(spec=Request)

                with patch("main.verify_admin_key", new_callable=AsyncMock):
                    response = await admin_get_style_status(mock_request, mock_db)

        # Verify self_style_worker is present
        assert "self_style_worker" in response
        worker_stats = response["self_style_worker"]

        # Verify all required fields are present
        assert "enabled" in worker_stats
        assert "disabled_reason" in worker_stats
        assert "last_run_status" in worker_stats
        assert "last_run_started_at" in worker_stats
        assert "last_run_finished_at" in worker_stats
        assert "last_error" in worker_stats
        assert "last_proposal_version_id" in worker_stats
        assert "total_proposals_generated" in worker_stats
        assert "total_proposals_skipped" in worker_stats
        assert "leader_lock" in worker_stats

        # Verify disabled state
        assert worker_stats["enabled"] is False
        assert worker_stats["disabled_reason"] == "disabled"

    @pytest.mark.asyncio
    async def test_response_includes_last_proposal_from_db(self):
        """Response includes last_proposal from database."""
        mock_worker = MagicMock()
        mock_worker.get_stats.return_value = {
            "enabled": True,
            "disabled_reason": None,
            "last_run_status": "success",
            "last_error": None,
            "last_proposal_version_id": "20260202_120000",
            "total_proposals_generated": 1,
            "total_proposals_skipped": 0,
            "leader_lock": {},
        }

        with patch("main.get_self_style_worker", return_value=mock_worker):
            with patch("main.get_style_rewriter") as mock_rewriter:
                mock_rewriter.return_value.get_status.return_value = {"source": "baseline"}

                # Mock DB queries - first for active, second for latest
                mock_db = AsyncMock()

                # Create mock for active version (None)
                active_result = MagicMock()
                active_result.mappings.return_value.fetchone.return_value = None

                # Create mock for latest proposal
                latest_result = MagicMock()
                latest_result.mappings.return_value.fetchone.return_value = {
                    "version_id": "20260202_120000",
                    "generated_at": datetime(2026, 2, 2, 12, 0, 0, tzinfo=timezone.utc),
                    "source": "self_style",
                    "tweet_count": 50,
                    "is_active": False,
                }

                mock_db.execute.side_effect = [active_result, latest_result]

                from main import admin_get_style_status
                from fastapi import Request

                mock_request = MagicMock(spec=Request)

                with patch("main.verify_admin_key", new_callable=AsyncMock):
                    response = await admin_get_style_status(mock_request, mock_db)

        # Verify last_proposal is present
        assert "last_proposal" in response
        last_proposal = response["last_proposal"]
        assert last_proposal["version_id"] == "20260202_120000"
        assert last_proposal["source"] == "self_style"
        assert last_proposal["tweet_count"] == 50
        assert last_proposal["is_active"] is False

    @pytest.mark.asyncio
    async def test_response_includes_hard_rules_enforced(self):
        """Response always includes hard_rules_enforced."""
        mock_worker = MagicMock()
        mock_worker.get_stats.return_value = {
            "enabled": False,
            "disabled_reason": "disabled",
            "last_error": None,
            "leader_lock": {},
        }

        with patch("main.get_self_style_worker", return_value=mock_worker):
            with patch("main.get_style_rewriter") as mock_rewriter:
                mock_rewriter.return_value.get_status.return_value = {}

                mock_db = AsyncMock()
                mock_result = MagicMock()
                mock_result.mappings.return_value.fetchone.return_value = None
                mock_db.execute.return_value = mock_result

                from main import admin_get_style_status
                from fastapi import Request

                mock_request = MagicMock(spec=Request)

                with patch("main.verify_admin_key", new_callable=AsyncMock):
                    response = await admin_get_style_status(mock_request, mock_db)

        assert "hard_rules_enforced" in response
        assert response["hard_rules_enforced"]["emojis_allowed"] == 0
        assert response["hard_rules_enforced"]["hashtags_allowed"] == 0


class TestSocialStatusEndpointShape:
    """Tests for GET /api/admin/social/status response shape."""

    @pytest.mark.asyncio
    async def test_response_includes_self_style(self):
        """Response includes self_style field."""
        mock_worker = MagicMock()
        mock_worker.get_stats.return_value = {
            "enabled": True,
            "disabled_reason": None,
            "last_run_status": "success",
        }

        with patch("main.get_self_style_worker", return_value=mock_worker):
            with patch("main.get_ingestion_loop", return_value=None):
                with patch("main.get_timeline_loop", return_value=None):
                    with patch("main.get_learning_worker", return_value=None):
                        with patch("main.is_x_bot_enabled", return_value=False):
                            with patch("main.get_runtime_setting", new_callable=AsyncMock, return_value=False):
                                from main import admin_get_social_status
                                from fastapi import Request

                                mock_request = MagicMock(spec=Request)

                                with patch("main.verify_admin_key", new_callable=AsyncMock):
                                    response = await admin_get_social_status(mock_request)

        assert "self_style" in response
        assert response["self_style"]["enabled"] is True
        assert response["self_style"]["last_run_status"] == "success"

    @pytest.mark.asyncio
    async def test_response_self_style_none_when_no_worker(self):
        """Response has self_style=None when worker not created."""
        with patch("main.get_self_style_worker", return_value=None):
            with patch("main.get_ingestion_loop", return_value=None):
                with patch("main.get_timeline_loop", return_value=None):
                    with patch("main.get_learning_worker", return_value=None):
                        with patch("main.is_x_bot_enabled", return_value=False):
                            with patch("main.get_runtime_setting", new_callable=AsyncMock, return_value=False):
                                from main import admin_get_social_status
                                from fastapi import Request

                                mock_request = MagicMock(spec=Request)

                                with patch("main.verify_admin_key", new_callable=AsyncMock):
                                    response = await admin_get_social_status(mock_request)

        assert "self_style" in response
        assert response["self_style"] is None


class TestLearningStatusEndpointShape:
    """Tests for GET /api/admin/learning/status response shape."""

    @pytest.mark.asyncio
    async def test_response_includes_self_style_fields(self):
        """Response includes last_self_style_job_at and last_self_style_status."""
        mock_worker = MagicMock()
        mock_worker.get_stats.return_value = {
            "enabled": True,
            "disabled_reason": None,
            "last_run_status": "skipped_insufficient_data",
            "last_run_finished_at": "2026-02-02T12:05:00+00:00",
            "last_proposal_version_id": None,
        }

        with patch("main.get_self_style_worker", return_value=mock_worker):
            # Mock all DB queries
            mock_db = AsyncMock()

            # Create sequential mock results
            mock_scalar_result = MagicMock()
            mock_scalar_result.scalar.return_value = 0

            mock_fetchall_result = MagicMock()
            mock_fetchall_result.fetchall.return_value = []

            # Return appropriate mocks for each query type
            mock_db.execute.return_value = mock_scalar_result

            from main import admin_get_learning_status
            from fastapi import Request

            mock_request = MagicMock(spec=Request)

            with patch("main.verify_admin_key", new_callable=AsyncMock):
                response = await admin_get_learning_status(mock_request, mock_db)

        # Verify self-style fields
        assert "last_self_style_job_at" in response
        assert "last_self_style_status" in response
        assert "self_style" in response

        assert response["last_self_style_job_at"] == "2026-02-02T12:05:00+00:00"
        assert response["last_self_style_status"] == "skipped_insufficient_data"

    @pytest.mark.asyncio
    async def test_response_includes_style_guide_versions_in_tables(self):
        """Response includes style_guide_versions in tables_used."""
        mock_worker = MagicMock()
        mock_worker.get_stats.return_value = {
            "enabled": False,
            "disabled_reason": "disabled",
            "last_run_status": None,
            "last_run_finished_at": None,
            "last_proposal_version_id": None,
        }

        with patch("main.get_self_style_worker", return_value=mock_worker):
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 0
            mock_result.fetchall.return_value = []
            mock_db.execute.return_value = mock_result

            from main import admin_get_learning_status
            from fastapi import Request

            mock_request = MagicMock(spec=Request)

            with patch("main.verify_admin_key", new_callable=AsyncMock):
                response = await admin_get_learning_status(mock_request, mock_db)

        assert "tables_used" in response
        assert "style_guide_versions" in response["tables_used"]


class TestEndpointFieldsWhenWorkerDisabled:
    """Tests that fields appear correctly when worker is disabled."""

    @pytest.mark.asyncio
    async def test_style_status_fields_when_disabled(self):
        """All self_style_worker fields present when disabled."""
        mock_worker = MagicMock()
        mock_worker.get_stats.return_value = {
            "enabled": False,
            "disabled_reason": "redis_missing",
            "last_run_status": None,
            "last_run_started_at": None,
            "last_run_finished_at": None,
            "last_error": "REDIS_URL not configured - worker refused to start",
            "last_proposal_version_id": None,
            "total_proposals_generated": 0,
            "total_proposals_skipped": 0,
            "leader_lock": {
                "lock_key": "self_style:leader",
                "lock_ttl_seconds": 300,
                "currently_acquired": False,
                "instance_id": "disabled-instance",
                "total_acquisitions": 0,
                "total_failures": 0,
            },
        }

        with patch("main.get_self_style_worker", return_value=mock_worker):
            with patch("main.get_style_rewriter") as mock_rewriter:
                mock_rewriter.return_value.get_status.return_value = {}

                mock_db = AsyncMock()
                mock_result = MagicMock()
                mock_result.mappings.return_value.fetchone.return_value = None
                mock_db.execute.return_value = mock_result

                from main import admin_get_style_status
                from fastapi import Request

                mock_request = MagicMock(spec=Request)

                with patch("main.verify_admin_key", new_callable=AsyncMock):
                    response = await admin_get_style_status(mock_request, mock_db)

        worker_stats = response["self_style_worker"]

        # All fields present
        assert worker_stats["enabled"] is False
        assert worker_stats["disabled_reason"] == "redis_missing"
        assert worker_stats["last_run_status"] is None
        assert worker_stats["last_run_started_at"] is None
        assert worker_stats["last_run_finished_at"] is None
        assert "REDIS_URL" in worker_stats["last_error"]
        assert worker_stats["last_proposal_version_id"] is None
        assert worker_stats["total_proposals_generated"] == 0
        assert worker_stats["total_proposals_skipped"] == 0

        # Leader lock info present
        lock_info = worker_stats["leader_lock"]
        assert lock_info["lock_key"] == "self_style:leader"
        assert lock_info["currently_acquired"] is False
