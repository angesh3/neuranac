"""Initial schema — ORM-managed tables from admin.py and network.py.

Revision ID: 001_initial
Revises: (none)
Create Date: 2026-02-28

This migration covers the SQLAlchemy ORM models only.
The full database schema (including raw-SQL tables from V001/V002/V003)
is managed by database/migrations/*.sql and scripts/setup.sh.
This Alembic migration exists so that future ORM model changes can be
tracked incrementally without touching the raw-SQL migration files.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── admin models ─────────────────────────────────────────────────────
    op.create_table(
        "admin_users",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("role", sa.String(50), server_default="viewer"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("failed_attempts", sa.Integer, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        if_not_exists=True,
    )

    op.create_table(
        "feature_flags",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("enabled", sa.Boolean, server_default="false"),
        sa.Column("rollout_percentage", sa.Integer, server_default="0"),
        sa.Column("metadata_json", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        if_not_exists=True,
    )

    op.create_table(
        "config_versions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("config_type", sa.String(50), nullable=False),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("config_data", JSONB),
        sa.Column("created_by", sa.String(100)),
        sa.Column("change_notes", sa.Text),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        if_not_exists=True,
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_id", sa.String(255)),
        sa.Column("details", JSONB),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        if_not_exists=True,
    )

    # ── network models (representative subset) ───────────────────────────
    op.create_table(
        "policy_sets",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("match_type", sa.String(20), server_default="all"),
        sa.Column("priority", sa.Integer, server_default="100"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        if_not_exists=True,
    )

    op.create_table(
        "network_devices",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("device_type", sa.String(100)),
        sa.Column("vendor", sa.String(100)),
        sa.Column("model", sa.String(100)),
        sa.Column("shared_secret_hash", sa.String(255)),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        if_not_exists=True,
    )

    # Indexes
    op.create_index("ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"], if_not_exists=True)
    op.create_index("ix_network_devices_ip", "network_devices", ["ip_address"], if_not_exists=True)
    op.create_index("ix_policy_sets_tenant", "policy_sets", ["tenant_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_policy_sets_tenant", table_name="policy_sets", if_exists=True)
    op.drop_index("ix_network_devices_ip", table_name="network_devices", if_exists=True)
    op.drop_index("ix_audit_logs_tenant_created", table_name="audit_logs", if_exists=True)
    op.drop_table("network_devices", if_exists=True)
    op.drop_table("policy_sets", if_exists=True)
    op.drop_table("audit_logs", if_exists=True)
    op.drop_table("config_versions", if_exists=True)
    op.drop_table("feature_flags", if_exists=True)
    op.drop_table("admin_users", if_exists=True)
