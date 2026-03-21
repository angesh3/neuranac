"""Admin user and role models"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from app.database.session import Base


def _utcnow():
    """Return a naive UTC datetime compatible with TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    isolation_mode = Column(String(50), default="row")  # row, schema, database
    status = Column(String(50), default="active")
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    username = Column(String(255), nullable=False)
    email = Column(String(255))
    password_hash = Column(String(255), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("admin_roles.id"))
    role_name = Column(String(100), default="admin")
    mfa_secret = Column(String(255))
    mfa_enabled = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)


class AdminRole(Base):
    __tablename__ = "admin_roles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    permissions = Column(JSON, default=list)
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    actor = Column(String(255), nullable=False)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100))
    entity_id = Column(String(255))
    before_data = Column(JSON)
    after_data = Column(JSON)
    source_ip = Column(String(45))
    timestamp = Column(DateTime, default=_utcnow)
    prev_hash = Column(String(64))
    entry_hash = Column(String(64))


class ConfigVersion(Base):
    __tablename__ = "config_versions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    data = Column(JSON, nullable=False)
    changed_by = Column(String(255))
    changed_at = Column(DateTime, default=_utcnow)


class BootstrapState(Base):
    __tablename__ = "bootstrap_state"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    step = Column(String(100), unique=True, nullable=False)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime)
    data = Column(JSON)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    enabled = Column(Boolean, default=False)
    rollout_percentage = Column(Integer, default=0)
    tenant_filter = Column(JSON, default=list)
    description = Column(Text)
    created_at = Column(DateTime, default=_utcnow)
