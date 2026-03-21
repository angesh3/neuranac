-- NeuraNAC Initial Database Schema
-- All core tables for the NeuraNAC platform

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ═══════════════════════════════════════════════════════════════════
-- CORE: Tenants, Admin, Audit
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    isolation_mode VARCHAR(50) DEFAULT 'row',
    status VARCHAR(50) DEFAULT 'active',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE admin_roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    permissions JSONB DEFAULT '[]',
    is_builtin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    role_id UUID REFERENCES admin_roles(id),
    role_name VARCHAR(100) DEFAULT 'admin',
    mfa_secret VARCHAR(255),
    mfa_enabled BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMPTZ,
    failed_attempts INT DEFAULT 0,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, username)
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id),
    actor VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id VARCHAR(255),
    before_data JSONB,
    after_data JSONB,
    source_ip VARCHAR(45),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    prev_hash VARCHAR(64),
    entry_hash VARCHAR(64)
);
CREATE INDEX idx_audit_tenant_ts ON audit_logs(tenant_id, timestamp DESC);

CREATE TABLE config_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id),
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    version INT NOT NULL DEFAULT 1,
    data JSONB NOT NULL,
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE bootstrap_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    step VARCHAR(100) UNIQUE NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    data JSONB
);

CREATE TABLE feature_flags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT FALSE,
    rollout_percentage INT DEFAULT 0,
    tenant_filter JSONB DEFAULT '[]',
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════
-- LICENSING
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE licenses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    tier VARCHAR(50) NOT NULL DEFAULT 'essentials',
    license_type VARCHAR(50) NOT NULL DEFAULT 'trial',
    max_endpoints INT DEFAULT 100,
    features JSONB DEFAULT '{}',
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_to TIMESTAMPTZ,
    key_hash VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE license_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    endpoint_count INT DEFAULT 0,
    compute_hours DECIMAL(10,2) DEFAULT 0,
    ai_queries INT DEFAULT 0,
    bandwidth_gb DECIMAL(10,2) DEFAULT 0,
    UNIQUE(tenant_id, date)
);

-- ═══════════════════════════════════════════════════════════════════
-- NETWORK DEVICES (NADs)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE network_devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    device_type VARCHAR(100),
    vendor VARCHAR(100),
    model VARCHAR(100),
    shared_secret_encrypted TEXT NOT NULL,
    radsec_enabled BOOLEAN DEFAULT FALSE,
    coa_port INT DEFAULT 3799,
    snmp_community VARCHAR(255),
    location VARCHAR(255),
    site_id UUID,
    status VARCHAR(50) DEFAULT 'active',
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, ip_address)
);
CREATE INDEX idx_nad_ip ON network_devices(ip_address);

CREATE TABLE device_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    members JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE radius_dictionaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    attributes JSONB NOT NULL,
    is_builtin BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════
-- IDENTITY
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE identity_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    priority INT DEFAULT 1,
    status VARCHAR(50) DEFAULT 'active',
    last_sync TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE internal_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    username VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    groups JSONB DEFAULT '[]',
    status VARCHAR(50) DEFAULT 'active',
    password_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, username)
);

-- ═══════════════════════════════════════════════════════════════════
-- CERTIFICATES
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE certificate_authorities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    ca_type VARCHAR(50) NOT NULL,
    subject TEXT,
    cert_pem TEXT,
    key_encrypted TEXT,
    crl_url VARCHAR(512),
    ocsp_url VARCHAR(512),
    not_before TIMESTAMPTZ,
    not_after TIMESTAMPTZ,
    parent_ca_id UUID REFERENCES certificate_authorities(id),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE certificates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    ca_id UUID REFERENCES certificate_authorities(id),
    subject TEXT NOT NULL,
    serial VARCHAR(255),
    cert_pem TEXT,
    key_encrypted TEXT,
    not_before TIMESTAMPTZ,
    not_after TIMESTAMPTZ,
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    usage VARCHAR(100),
    san JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════
-- ENDPOINTS
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE endpoints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    mac_address VARCHAR(17) NOT NULL,
    profile_id UUID,
    device_type VARCHAR(100),
    vendor VARCHAR(100),
    os VARCHAR(100),
    hostname VARCHAR(255),
    ip_address VARCHAR(45),
    identity_group_id UUID,
    status VARCHAR(50) DEFAULT 'active',
    attributes JSONB DEFAULT '{}',
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, mac_address)
);
CREATE INDEX idx_endpoint_mac ON endpoints(mac_address);

CREATE TABLE client_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    group_type VARCHAR(50) DEFAULT 'static',
    rules JSONB DEFAULT '[]',
    parent_id UUID REFERENCES client_groups(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE endpoint_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    match_rules JSONB NOT NULL DEFAULT '[]',
    device_type VARCHAR(100),
    vendor VARCHAR(100),
    os VARCHAR(100),
    is_builtin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════
-- POLICY
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE policy_sets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    priority INT DEFAULT 1,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE authorization_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    vlan_id VARCHAR(50),
    vlan_name VARCHAR(100),
    sgt_id UUID,
    sgt_value INT,
    dacl_id UUID,
    ipsk VARCHAR(255),
    coa_action VARCHAR(50),
    group_policy VARCHAR(255),
    voice_domain BOOLEAN DEFAULT FALSE,
    redirect_url VARCHAR(512),
    session_timeout INT,
    idle_timeout INT,
    bandwidth_limit_mbps INT,
    destination_whitelist JSONB DEFAULT '[]',
    data_flow_policy_id UUID,
    vendor_attributes JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE policy_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_set_id UUID NOT NULL REFERENCES policy_sets(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    priority INT DEFAULT 1,
    conditions JSONB NOT NULL DEFAULT '[]',
    auth_profile_id UUID REFERENCES authorization_profiles(id),
    action VARCHAR(50) DEFAULT 'permit',
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════
-- SEGMENTATION
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE security_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    tag_value INT NOT NULL,
    description TEXT,
    is_ai_sgt BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, tag_value)
);

CREATE TABLE adaptive_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    src_sgt_id UUID NOT NULL REFERENCES security_groups(id),
    dst_sgt_id UUID NOT NULL REFERENCES security_groups(id),
    action VARCHAR(50) DEFAULT 'deny',
    acl_id UUID,
    description TEXT,
    UNIQUE(tenant_id, src_sgt_id, dst_sgt_id)
);

CREATE TABLE vlans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    vlan_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    site_id UUID,
    UNIQUE(tenant_id, vlan_id)
);

CREATE TABLE acls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    entries JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════
-- SESSIONS
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    session_id_radius VARCHAR(255),
    endpoint_mac VARCHAR(17),
    username VARCHAR(255),
    nas_ip VARCHAR(45),
    nas_port VARCHAR(50),
    eap_type VARCHAR(50),
    auth_result VARCHAR(50),
    vlan_id VARCHAR(50),
    sgt VARCHAR(50),
    auth_profile_id UUID,
    risk_score INT DEFAULT 0,
    ai_agent_id UUID,
    accounting JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE
);
CREATE INDEX idx_session_mac ON sessions(endpoint_mac, is_active);
CREATE INDEX idx_session_tenant ON sessions(tenant_id, is_active);

-- ═══════════════════════════════════════════════════════════════════
-- GUEST & BYOD
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE guest_portals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    portal_type VARCHAR(50) NOT NULL,
    theme JSONB DEFAULT '{}',
    settings JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE guest_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    portal_id UUID REFERENCES guest_portals(id),
    name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    username VARCHAR(255),
    password_hash VARCHAR(255),
    sponsored_by VARCHAR(255),
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_to TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'active'
);

CREATE TABLE sponsor_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    members JSONB DEFAULT '[]',
    permissions JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE byod_registrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    endpoint_mac VARCHAR(17) NOT NULL,
    user_id VARCHAR(255),
    cert_id UUID REFERENCES certificates(id),
    device_name VARCHAR(255),
    registered_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════
-- POSTURE
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE posture_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    conditions JSONB NOT NULL DEFAULT '[]',
    compliant_profile_id UUID REFERENCES authorization_profiles(id),
    noncompliant_profile_id UUID REFERENCES authorization_profiles(id),
    grace_period_hours INT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE posture_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    endpoint_mac VARCHAR(17) NOT NULL,
    policy_id UUID REFERENCES posture_policies(id),
    status VARCHAR(50) NOT NULL DEFAULT 'unknown',
    details JSONB DEFAULT '{}',
    checked_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════
-- SYNC ENGINE
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE sync_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    vector_clock JSONB DEFAULT '{}',
    last_synced_at TIMESTAMPTZ,
    sync_status VARCHAR(50) DEFAULT 'pending',
    UNIQUE(entity_type, entity_id)
);

CREATE TABLE sync_journal (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    operation VARCHAR(50) NOT NULL,
    data JSONB,
    source_node VARCHAR(100),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    delivered BOOLEAN DEFAULT FALSE
);
CREATE INDEX idx_sync_journal_pending ON sync_journal(delivered, timestamp) WHERE NOT delivered;

-- ═══════════════════════════════════════════════════════════════════
-- AI TABLES
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE ai_agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_name VARCHAR(255) NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    delegated_by_user_id UUID,
    delegation_scope JSONB DEFAULT '[]',
    model_type VARCHAR(100),
    runtime VARCHAR(50),
    auth_method VARCHAR(50),
    cert_id UUID REFERENCES certificates(id),
    status VARCHAR(50) DEFAULT 'active',
    max_bandwidth_mbps INT,
    data_classification_allowed JSONB DEFAULT '[]',
    ttl_hours INT DEFAULT 24,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ai_agent_delegations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_agent_id UUID NOT NULL REFERENCES ai_agents(id),
    child_agent_id UUID NOT NULL REFERENCES ai_agents(id),
    delegation_depth INT DEFAULT 1,
    scope JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE TABLE ai_services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,
    dns_patterns JSONB DEFAULT '[]',
    sni_patterns JSONB DEFAULT '[]',
    api_patterns JSONB DEFAULT '[]',
    risk_level VARCHAR(50) DEFAULT 'medium',
    is_approved BOOLEAN DEFAULT FALSE,
    is_builtin BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ai_data_flow_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    priority INT DEFAULT 1,
    source_conditions JSONB DEFAULT '{}',
    dest_conditions JSONB DEFAULT '{}',
    data_classification VARCHAR(50),
    action VARCHAR(50) DEFAULT 'deny',
    max_volume_mb INT,
    time_window VARCHAR(50),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ai_shadow_detections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    endpoint_mac VARCHAR(17),
    user_id VARCHAR(255),
    ai_service_id UUID REFERENCES ai_services(id),
    detection_type VARCHAR(50),
    bytes_uploaded BIGINT DEFAULT 0,
    bytes_downloaded BIGINT DEFAULT 0,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    action_taken VARCHAR(50)
);

CREATE TABLE ai_risk_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    session_id UUID,
    endpoint_mac VARCHAR(17),
    behavioral_score INT DEFAULT 0,
    identity_score INT DEFAULT 0,
    endpoint_score INT DEFAULT 0,
    ai_activity_score INT DEFAULT 0,
    total_score INT DEFAULT 0,
    factors JSONB DEFAULT '[]',
    computed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ai_threat_signatures (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    threat_type VARCHAR(100) NOT NULL,
    indicators JSONB NOT NULL DEFAULT '{}',
    severity VARCHAR(50) DEFAULT 'medium',
    source VARCHAR(50) DEFAULT 'builtin',
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ai_model_registry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    hash_sha256 VARCHAR(64),
    model_type VARCHAR(50) NOT NULL,
    onnx_path VARCHAR(512),
    accuracy_score DECIMAL(5,4),
    is_active BOOLEAN DEFAULT FALSE,
    deployed_at TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════════
-- DATA RETENTION
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE data_retention_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id),
    data_type VARCHAR(100) NOT NULL,
    retention_days INT NOT NULL DEFAULT 90,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(tenant_id, data_type)
);

-- ═══════════════════════════════════════════════════════════════════
-- PRIVACY (GDPR/CCPA)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE privacy_subjects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    subject_type VARCHAR(50) NOT NULL,  -- 'user', 'guest', 'endpoint'
    subject_identifier VARCHAR(255) NOT NULL,
    consent_given BOOLEAN DEFAULT FALSE,
    consent_date TIMESTAMPTZ,
    consent_method VARCHAR(100),
    data_categories JSONB DEFAULT '[]',
    retention_override_days INT,
    erasure_requested BOOLEAN DEFAULT FALSE,
    erasure_requested_at TIMESTAMPTZ,
    erasure_completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, subject_type, subject_identifier)
);

CREATE TABLE privacy_data_exports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES privacy_subjects(id),
    requested_by VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, ready, expired
    export_format VARCHAR(50) DEFAULT 'json',
    file_path VARCHAR(512),
    expires_at TIMESTAMPTZ,
    requested_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE privacy_consent_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES privacy_subjects(id),
    purpose VARCHAR(255) NOT NULL,
    legal_basis VARCHAR(100) NOT NULL,  -- consent, legitimate_interest, contract, legal_obligation
    granted BOOLEAN NOT NULL,
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    source VARCHAR(100),  -- portal, api, admin
    ip_address VARCHAR(45)
);
CREATE INDEX idx_privacy_subject_tenant ON privacy_subjects(tenant_id, subject_type);
CREATE INDEX idx_privacy_exports_status ON privacy_data_exports(status) WHERE status = 'pending';

-- ═══════════════════════════════════════════════════════════════════
-- NeuraNAC INTEGRATION (Coexistence / Migration)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE legacy_nac_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    hostname VARCHAR(255) NOT NULL,
    port INT DEFAULT 443,
    username VARCHAR(255) NOT NULL,
    password_encrypted VARCHAR(512) NOT NULL,
    ers_enabled BOOLEAN DEFAULT TRUE,
    ers_port INT DEFAULT 9060,
    event_stream_enabled BOOLEAN DEFAULT FALSE,
    event_stream_client_cert TEXT,
    event_stream_client_key TEXT,
    event_stream_ca_cert TEXT,
    legacy_nac_version VARCHAR(50),
    verify_ssl BOOLEAN DEFAULT TRUE,
    connection_status VARCHAR(50) DEFAULT 'disconnected',
    last_connected_at TIMESTAMPTZ,
    last_error TEXT,
    deployment_mode VARCHAR(50) DEFAULT 'coexistence',  -- 'coexistence', 'migration', 'readonly'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, hostname)
);

CREATE TABLE legacy_nac_sync_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES legacy_nac_connections(id) ON DELETE CASCADE,
    entity_type VARCHAR(100) NOT NULL,  -- 'network_device', 'internal_user', 'endpoint', 'identity_group', 'sgt', 'auth_profile'
    direction VARCHAR(20) DEFAULT 'legacy_to_neuranac',  -- 'legacy_to_neuranac', 'neuranac_to_legacy', 'bidirectional'
    last_full_sync_at TIMESTAMPTZ,
    last_incremental_sync_at TIMESTAMPTZ,
    last_sync_status VARCHAR(50) DEFAULT 'never',  -- 'never', 'running', 'success', 'failed', 'partial'
    last_sync_error TEXT,
    items_synced INT DEFAULT 0,
    items_failed INT DEFAULT 0,
    items_total INT DEFAULT 0,
    sync_cursor VARCHAR(512),  -- pagination cursor for incremental sync
    config JSONB DEFAULT '{}',  -- entity-specific sync config (filters, mappings)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(connection_id, entity_type)
);

CREATE TABLE legacy_nac_sync_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES legacy_nac_connections(id) ON DELETE CASCADE,
    sync_type VARCHAR(50) NOT NULL,  -- 'full', 'incremental', 'manual', 'event_stream_event'
    entity_type VARCHAR(100),
    direction VARCHAR(20),
    status VARCHAR(50) NOT NULL,  -- 'started', 'success', 'failed', 'partial'
    items_created INT DEFAULT 0,
    items_updated INT DEFAULT 0,
    items_deleted INT DEFAULT 0,
    items_skipped INT DEFAULT 0,
    items_failed INT DEFAULT 0,
    error_details JSONB DEFAULT '[]',
    duration_ms INT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_legacy_nac_sync_log_conn ON legacy_nac_sync_log(connection_id, started_at DESC);

CREATE TABLE legacy_nac_entity_map (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES legacy_nac_connections(id) ON DELETE CASCADE,
    entity_type VARCHAR(100) NOT NULL,
    legacy_nac_id VARCHAR(255) NOT NULL,
    legacy_nac_name VARCHAR(255),
    neuranac_id UUID NOT NULL,
    neuranac_table VARCHAR(100) NOT NULL,
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    legacy_nac_updated_at TIMESTAMPTZ,
    sync_hash VARCHAR(64),  -- SHA-256 of synced data for change detection
    UNIQUE(connection_id, entity_type, legacy_nac_id)
);
CREATE INDEX idx_legacy_nac_entity_map_neuranac ON legacy_nac_entity_map(neuranac_id);

-- ═══════════════════════════════════════════════════════════════════
-- INDEXES FOR PERFORMANCE
-- ═══════════════════════════════════════════════════════════════════

CREATE INDEX idx_endpoints_tenant ON endpoints(tenant_id);
CREATE INDEX idx_sessions_started ON sessions(started_at DESC);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_ai_shadow_tenant ON ai_shadow_detections(tenant_id, detected_at DESC);
CREATE INDEX idx_ai_risk_session ON ai_risk_scores(session_id);
CREATE INDEX idx_certs_expiry ON certificates(not_after) WHERE NOT revoked;
