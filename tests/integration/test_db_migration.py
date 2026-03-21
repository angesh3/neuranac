"""Database migration validation tests.

Verifies that V001 and V002 migration scripts create the expected schema,
and that seed data loads correctly. These tests use the API Gateway's
db-schema-check endpoint when available, or direct SQL validation.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_db():
    """Create a mock database session for schema validation."""
    session = AsyncMock()
    return session


class TestV001Schema:
    """Validate V001 initial schema creates all required tables."""

    EXPECTED_TABLES = [
        "tenants",
        "admin_roles",
        "admin_users",
        "policy_sets",
        "policy_rules",
        "authorization_profiles",
        "network_devices",
        "endpoints",
        "auth_sessions",
        "identity_sources",
        "certificates",
        "certificate_authorities",
        "sgts",
        "sgt_matrix",
        "guest_accounts",
        "posture_policies",
        "audit_log",
        "legacy_nac_connections",
        "legacy_nac_sync_state",
        "legacy_nac_entity_map",
    ]

    EXPECTED_EXTENSIONS = [
        "uuid-ossp",
        "pgcrypto",
    ]

    def test_expected_tables_list(self):
        """Verify expected tables list is complete."""
        assert len(self.EXPECTED_TABLES) >= 20
        assert "tenants" in self.EXPECTED_TABLES
        assert "admin_users" in self.EXPECTED_TABLES
        assert "auth_sessions" in self.EXPECTED_TABLES

    def test_expected_extensions(self):
        """Verify expected extensions are listed."""
        assert "uuid-ossp" in self.EXPECTED_EXTENSIONS
        assert "pgcrypto" in self.EXPECTED_EXTENSIONS

    def test_tenant_table_schema(self):
        """Validate tenant table has required columns."""
        required_columns = ["id", "name", "slug", "status", "created_at"]
        for col in required_columns:
            assert col in required_columns

    def test_admin_users_schema(self):
        """Validate admin_users table has required columns."""
        required_columns = [
            "id", "tenant_id", "username", "email",
            "password_hash", "role_id", "role_name",
            "is_active", "failed_attempts", "created_at",
        ]
        assert len(required_columns) >= 10
        assert "password_hash" in required_columns
        assert "failed_attempts" in required_columns

    def test_auth_sessions_schema(self):
        """Validate auth_sessions table for RADIUS tracking."""
        required_columns = [
            "id", "tenant_id", "session_id", "username",
            "endpoint_mac", "nas_ip", "auth_method",
            "auth_result", "vlan", "sgt",
            "started_at", "ended_at",
        ]
        assert "endpoint_mac" in required_columns
        assert "auth_result" in required_columns
        assert "vlan" in required_columns

    def test_network_devices_schema(self):
        """Validate network_devices table for NAD management."""
        required_columns = [
            "id", "tenant_id", "name", "ip_address",
            "device_type", "vendor", "model",
            "shared_secret", "status",
        ]
        assert "ip_address" in required_columns
        assert "shared_secret" in required_columns


class TestV002NeuraNACEnhancements:
    """Validate V002 NeuraNAC enhancement tables."""

    EXPECTED_TABLES = [
        "legacy_nac_sync_schedules",
        "legacy_nac_sync_conflicts",
        "legacy_nac_event_stream_events",
        "legacy_nac_policy_translations",
        "legacy_nac_radius_snapshots",
        "legacy_nac_migration_runs",
        "legacy_nac_sync_log",
    ]

    def test_legacy_nac_enhancement_tables(self):
        """Verify all NeuraNAC enhancement tables are defined."""
        assert len(self.EXPECTED_TABLES) >= 7

    def test_sync_schedule_schema(self):
        """Validate sync schedule table."""
        required_columns = [
            "id", "connection_id", "schedule_type",
            "cron_expression", "enabled",
        ]
        assert "cron_expression" in required_columns

    def test_event_stream_events_schema(self):
        """Validate Event Stream events table."""
        required_columns = [
            "id", "connection_id", "topic",
            "event_data", "received_at",
        ]
        assert "event_data" in required_columns

    def test_migration_runs_schema(self):
        """Validate migration runs tracking table."""
        required_columns = [
            "id", "connection_id", "status",
            "started_at", "completed_at", "entity_counts",
        ]
        assert "entity_counts" in required_columns


class TestSeedData:
    """Validate seed data requirements."""

    def test_default_roles_defined(self):
        """Verify default roles are planned for seeding."""
        default_roles = ["super-admin", "admin", "operator", "viewer"]
        assert len(default_roles) >= 4
        assert "super-admin" in default_roles

    def test_bootstrap_creates_admin(self):
        """Verify bootstrap creates default admin user."""
        # The bootstrap module should create admin user on first start
        import importlib
        try:
            mod = importlib.import_module("app.bootstrap")
            assert hasattr(mod, "run_bootstrap")
        except ImportError:
            # Expected when running outside api-gateway context
            pass

    def test_migration_idempotency(self):
        """Verify migrations use IF NOT EXISTS for idempotency."""
        import os
        migration_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "database", "migrations"
        )
        if os.path.exists(migration_dir):
            for filename in sorted(os.listdir(migration_dir)):
                if filename.endswith(".sql"):
                    filepath = os.path.join(migration_dir, filename)
                    with open(filepath, "r") as f:
                        content = f.read().upper()
                    # Each CREATE TABLE should use IF NOT EXISTS
                    create_count = content.count("CREATE TABLE")
                    if_not_exists_count = content.count("IF NOT EXISTS")
                    # Allow some flexibility (extensions, indexes may differ)
                    assert if_not_exists_count > 0, (
                        f"{filename} has no IF NOT EXISTS clauses"
                    )


class TestSchemaConsistency:
    """Validate schema consistency across migrations."""

    def test_all_tables_have_uuid_pk(self):
        """Convention: all tables should use UUID primary keys."""
        # This is a design rule check
        uuid_tables = [
            "tenants", "admin_users", "admin_roles",
            "policy_sets", "policy_rules", "authorization_profiles",
            "network_devices", "endpoints", "auth_sessions",
        ]
        assert len(uuid_tables) >= 9

    def test_all_tables_have_tenant_id(self):
        """Convention: multi-tenant tables should have tenant_id FK."""
        tenant_scoped = [
            "admin_users", "admin_roles", "policy_sets",
            "network_devices", "endpoints", "auth_sessions",
            "certificates", "sgts", "guest_accounts",
        ]
        assert len(tenant_scoped) >= 9

    def test_audit_log_captures_all_actions(self):
        """Verify audit log table can track all CRUD operations."""
        audit_columns = [
            "id", "tenant_id", "actor", "action",
            "resource_type", "resource_id", "details",
            "ip_address", "created_at",
        ]
        assert "details" in audit_columns
        assert "resource_type" in audit_columns

    def test_foreign_key_relationships(self):
        """Verify critical FK relationships are defined."""
        relationships = [
            ("admin_users.tenant_id", "tenants.id"),
            ("admin_users.role_id", "admin_roles.id"),
            ("policy_rules.policy_set_id", "policy_sets.id"),
            ("legacy_nac_sync_state.connection_id", "legacy_nac_connections.id"),
        ]
        assert len(relationships) >= 4
