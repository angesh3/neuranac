"""Network, Policy, Segmentation, Session, Identity, Certificate, Guest, Posture, AI models"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Text, Integer, BigInteger, Numeric
from sqlalchemy.dialects.postgresql import UUID
from app.database.session import Base


def _utcnow():
    """Return a naive UTC datetime compatible with TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NetworkDevice(Base):
    __tablename__ = "network_devices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=False)
    device_type = Column(String(100))
    vendor = Column(String(100))
    model = Column(String(100))
    shared_secret_encrypted = Column(Text, nullable=False)
    radsec_enabled = Column(Boolean, default=False)
    coa_port = Column(Integer, default=3799)
    snmp_community = Column(String(255))
    location = Column(String(255))
    site_id = Column(UUID(as_uuid=True))
    status = Column(String(50), default="active")
    last_seen = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)


class IdentitySource(Base):
    __tablename__ = "identity_sources"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)
    config = Column(JSON, default=dict)
    priority = Column(Integer, default=1)
    status = Column(String(50), default="active")
    last_sync = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)


class CertificateAuthority(Base):
    __tablename__ = "certificate_authorities"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    ca_type = Column(String(50), nullable=False)
    subject = Column(Text)
    cert_pem = Column(Text)
    key_encrypted = Column(Text)
    not_before = Column(DateTime)
    not_after = Column(DateTime)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=_utcnow)


class Certificate(Base):
    __tablename__ = "certificates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    ca_id = Column(UUID(as_uuid=True), ForeignKey("certificate_authorities.id"))
    subject = Column(Text, nullable=False)
    serial = Column(String(255))
    cert_pem = Column(Text)
    key_encrypted = Column(Text)
    not_before = Column(DateTime)
    not_after = Column(DateTime)
    revoked = Column(Boolean, default=False)
    usage = Column(String(100))
    san = Column(JSON, default=list)
    created_at = Column(DateTime, default=_utcnow)


class Endpoint(Base):
    __tablename__ = "endpoints"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    mac_address = Column(String(17), nullable=False)
    device_type = Column(String(100))
    vendor = Column(String(100))
    os = Column(String(100))
    hostname = Column(String(255))
    ip_address = Column(String(45))
    status = Column(String(50), default="active")
    attributes = Column(JSON, default=dict)
    first_seen = Column(DateTime, default=_utcnow)
    last_seen = Column(DateTime, default=_utcnow)


class ClientGroup(Base):
    __tablename__ = "client_groups"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    group_type = Column(String(50), default="static")
    rules = Column(JSON, default=list)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("client_groups.id"))
    created_at = Column(DateTime, default=_utcnow)


class PolicySet(Base):
    __tablename__ = "policy_sets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    priority = Column(Integer, default=1)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=_utcnow)


class AuthorizationProfile(Base):
    __tablename__ = "authorization_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    vlan_id = Column(String(50))
    vlan_name = Column(String(100))
    sgt_value = Column(Integer)
    dacl_id = Column(UUID(as_uuid=True))
    ipsk = Column(String(255))
    coa_action = Column(String(50))
    group_policy = Column(String(255))
    voice_domain = Column(Boolean, default=False)
    redirect_url = Column(String(512))
    session_timeout = Column(Integer)
    bandwidth_limit_mbps = Column(Integer)
    destination_whitelist = Column(JSON, default=list)
    vendor_attributes = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)


class PolicyRule(Base):
    __tablename__ = "policy_rules"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_set_id = Column(UUID(as_uuid=True), ForeignKey("policy_sets.id"), nullable=False)
    name = Column(String(255), nullable=False)
    priority = Column(Integer, default=1)
    conditions = Column(JSON, default=list)
    auth_profile_id = Column(UUID(as_uuid=True), ForeignKey("authorization_profiles.id"))
    action = Column(String(50), default="permit")
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=_utcnow)


class SecurityGroup(Base):
    __tablename__ = "security_groups"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(100), nullable=False)
    tag_value = Column(Integer, nullable=False)
    description = Column(Text)
    is_ai_sgt = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)


class Session(Base):
    __tablename__ = "sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    session_id_radius = Column(String(255))
    endpoint_mac = Column(String(17))
    username = Column(String(255))
    nas_ip = Column(String(45))
    eap_type = Column(String(50))
    auth_result = Column(String(50))
    vlan_id = Column(String(50))
    sgt = Column(String(50))
    risk_score = Column(Integer, default=0)
    ai_agent_id = Column(UUID(as_uuid=True))
    accounting = Column(JSON, default=dict)
    started_at = Column(DateTime, default=_utcnow)
    ended_at = Column(DateTime)
    is_active = Column(Boolean, default=True)


class GuestPortal(Base):
    __tablename__ = "guest_portals"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    portal_type = Column(String(50), nullable=False)
    theme = Column(JSON, default=dict)
    settings = Column(JSON, default=dict)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=_utcnow)


class PosturePolicy(Base):
    __tablename__ = "posture_policies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    conditions = Column(JSON, default=list)
    grace_period_hours = Column(Integer, default=0)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=_utcnow)


class AIAgent(Base):
    __tablename__ = "ai_agents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    agent_name = Column(String(255), nullable=False)
    agent_type = Column(String(50), nullable=False)
    delegated_by_user_id = Column(UUID(as_uuid=True))
    delegation_scope = Column(JSON, default=list)
    model_type = Column(String(100))
    runtime = Column(String(50))
    auth_method = Column(String(50))
    status = Column(String(50), default="active")
    max_bandwidth_mbps = Column(Integer)
    data_classification_allowed = Column(JSON, default=list)
    ttl_hours = Column(Integer, default=24)
    created_at = Column(DateTime, default=_utcnow)


class AIService(Base):
    __tablename__ = "ai_services"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)
    dns_patterns = Column(JSON, default=list)
    sni_patterns = Column(JSON, default=list)
    api_patterns = Column(JSON, default=list)
    risk_level = Column(String(50), default="medium")
    is_approved = Column(Boolean, default=False)
    is_builtin = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=_utcnow)


class AIDataFlowPolicy(Base):
    __tablename__ = "ai_data_flow_policies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    priority = Column(Integer, default=1)
    source_conditions = Column(JSON, default=dict)
    dest_conditions = Column(JSON, default=dict)
    data_classification = Column(String(50))
    action = Column(String(50), default="deny")
    max_volume_mb = Column(Integer)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=_utcnow)


class AIShadowDetection(Base):
    __tablename__ = "ai_shadow_detections"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    endpoint_mac = Column(String(17))
    user_id = Column(String(255))
    ai_service_id = Column(UUID(as_uuid=True), ForeignKey("ai_services.id"))
    detection_type = Column(String(50))
    bytes_uploaded = Column(BigInteger, default=0)
    bytes_downloaded = Column(BigInteger, default=0)
    detected_at = Column(DateTime, default=_utcnow)
    action_taken = Column(String(50))


class AIRiskScore(Base):
    __tablename__ = "ai_risk_scores"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True))
    endpoint_mac = Column(String(17))
    behavioral_score = Column(Integer, default=0)
    identity_score = Column(Integer, default=0)
    endpoint_score = Column(Integer, default=0)
    ai_activity_score = Column(Integer, default=0)
    total_score = Column(Integer, default=0)
    factors = Column(JSON, default=list)
    computed_at = Column(DateTime, default=_utcnow)


class DataRetentionPolicy(Base):
    __tablename__ = "data_retention_policies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    data_type = Column(String(100), nullable=False)
    retention_days = Column(Integer, nullable=False, default=90)
    is_active = Column(Boolean, default=True)


class PrivacySubject(Base):
    __tablename__ = "privacy_subjects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    subject_type = Column(String(50), nullable=False)
    subject_identifier = Column(String(255), nullable=False)
    consent_given = Column(Boolean, default=False)
    consent_date = Column(DateTime)
    consent_method = Column(String(100))
    data_categories = Column(JSON, default=list)
    retention_override_days = Column(Integer)
    erasure_requested = Column(Boolean, default=False)
    erasure_requested_at = Column(DateTime)
    erasure_completed_at = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)


class PrivacyDataExport(Base):
    __tablename__ = "privacy_data_exports"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("privacy_subjects.id"), nullable=False)
    requested_by = Column(String(255), nullable=False)
    status = Column(String(50), default="pending")
    export_format = Column(String(50), default="json")
    file_path = Column(String(512))
    expires_at = Column(DateTime)
    requested_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime)


class PrivacyConsentRecord(Base):
    __tablename__ = "privacy_consent_records"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("privacy_subjects.id"), nullable=False)
    purpose = Column(String(255), nullable=False)
    legal_basis = Column(String(100), nullable=False)
    granted = Column(Boolean, nullable=False)
    granted_at = Column(DateTime, default=_utcnow)
    revoked_at = Column(DateTime)
    source = Column(String(100))
    ip_address = Column(String(45))
