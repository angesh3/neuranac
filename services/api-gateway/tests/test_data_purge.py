"""Tests for data retention purge service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.data_purge import (
    DataPurgeService,
    RetentionPolicy,
    PurgeResult,
    DEFAULT_POLICIES,
    get_purge_service,
)


class TestRetentionPolicy:
    def test_defaults(self):
        p = RetentionPolicy(table="test_table")
        assert p.timestamp_column == "created_at"
        assert p.retention_days == 90
        assert p.condition == ""
        assert p.batch_size == 1000

    def test_custom(self):
        p = RetentionPolicy(
            table="audit_logs",
            timestamp_column="logged_at",
            retention_days=365,
            condition="level = 'debug'",
            batch_size=500,
            description="Debug audit logs",
        )
        assert p.retention_days == 365
        assert p.condition == "level = 'debug'"


class TestDefaultPolicies:
    def test_has_policies(self):
        assert len(DEFAULT_POLICIES) > 0

    def test_all_have_tables(self):
        for p in DEFAULT_POLICIES:
            assert p.table, f"Policy missing table name"
            assert p.retention_days > 0, f"Policy {p.table} has invalid retention"

    def test_session_log_policy(self):
        session_policies = [p for p in DEFAULT_POLICIES if p.table == "radius_session_log"]
        assert len(session_policies) == 1
        assert session_policies[0].retention_days == 90

    def test_audit_log_policy(self):
        audit_policies = [p for p in DEFAULT_POLICIES if p.table == "audit_logs"]
        assert len(audit_policies) == 1
        assert audit_policies[0].retention_days == 365

    def test_guest_account_policy(self):
        guest_policies = [p for p in DEFAULT_POLICIES if p.table == "internal_users"]
        assert len(guest_policies) == 1
        assert guest_policies[0].condition == "status = 'guest'"
        assert guest_policies[0].retention_days == 7


class TestPurgeResult:
    def test_success(self):
        r = PurgeResult(table="test", rows_deleted=100, duration_ms=50.5)
        assert r.error is None
        assert r.rows_deleted == 100

    def test_error(self):
        r = PurgeResult(table="test", rows_deleted=0, duration_ms=1.0, error="table not found")
        assert r.error == "table not found"


class TestDataPurgeService:
    def test_init_default_policies(self):
        svc = DataPurgeService()
        assert len(svc.policies) == len(DEFAULT_POLICIES)
        assert svc.last_run is None
        assert svc.last_results == []

    def test_init_custom_policies(self):
        custom = [RetentionPolicy(table="custom_table", retention_days=30)]
        svc = DataPurgeService(policies=custom)
        assert len(svc.policies) == 1
        assert svc.policies[0].table == "custom_table"

    def test_get_status_initial(self):
        svc = DataPurgeService()
        status = svc.get_status()
        assert status["running"] is False
        assert status["last_run"] is None
        assert status["policies_count"] == len(DEFAULT_POLICIES)
        assert status["last_results"] == []

    @pytest.mark.asyncio
    async def test_run_purge_nonexistent_table(self):
        """Purge should handle non-existent tables gracefully."""
        policies = [RetentionPolicy(table="nonexistent_table_xyz", retention_days=1)]
        svc = DataPurgeService(policies=policies)

        # Mock the DB session
        mock_db = AsyncMock()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar.return_value = False
        mock_db.execute.return_value = mock_scalar_result
        mock_db.commit = AsyncMock()

        results = await svc.run_purge(mock_db)
        assert len(results) == 1
        assert results[0].table == "nonexistent_table_xyz"
        assert "does not exist" in (results[0].error or "")

    @pytest.mark.asyncio
    async def test_stop_scheduler_not_running(self):
        svc = DataPurgeService()
        # Should not raise
        await svc.stop_scheduler()
        assert svc._running is False


class TestGetPurgeService:
    def test_singleton(self):
        svc1 = get_purge_service()
        svc2 = get_purge_service()
        assert svc1 is svc2
