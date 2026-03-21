-- V004: Hybrid Architecture - Sites, Connectors, Node Registry, Deployment Config
-- Supports 4 deployment scenarios:
--   1. NeuraNAC + Hybrid (on-prem + cloud)
--   2. Cloud only, no NeuraNAC
--   3. On-prem only, no NeuraNAC
--   4. Hybrid (on-prem + cloud), no NeuraNAC

-- ─── Deployment Configuration ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS neuranac_deployment_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_mode VARCHAR(20)  NOT NULL DEFAULT 'standalone' CHECK (deployment_mode IN ('standalone', 'hybrid')),
    legacy_nac_enabled     BOOLEAN      NOT NULL DEFAULT false,
    primary_site_id UUID,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Singleton: only one deployment config row allowed
CREATE UNIQUE INDEX IF NOT EXISTS idx_deployment_config_singleton
    ON neuranac_deployment_config ((true));

-- ─── Sites ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS neuranac_sites (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    site_type       VARCHAR(20)  NOT NULL CHECK (site_type IN ('onprem', 'cloud')),
    deployment_mode VARCHAR(20)  NOT NULL DEFAULT 'standalone' CHECK (deployment_mode IN ('standalone', 'hybrid')),
    api_url         VARCHAR(512),
    peer_site_id    UUID         REFERENCES neuranac_sites(id),
    region          VARCHAR(100),
    description     TEXT,
    status          VARCHAR(20)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'degraded', 'unreachable')),
    last_heartbeat  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sites_site_type ON neuranac_sites(site_type);
CREATE INDEX IF NOT EXISTS idx_sites_status ON neuranac_sites(status);

-- ─── Bridge Connectors ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS neuranac_connectors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         UUID         NOT NULL REFERENCES neuranac_sites(id) ON DELETE CASCADE,
    connector_type  VARCHAR(30)  NOT NULL DEFAULT 'bridge' CHECK (connector_type IN ('bridge', 'meraki', 'dnac')),
    name            VARCHAR(255) NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'disconnected' CHECK (status IN ('connected', 'disconnected', 'error', 'registering')),
    legacy_nac_hostname    VARCHAR(512),
    legacy_nac_ers_port    INTEGER      DEFAULT 9060,
    legacy_nac_event_stream_port INTEGER DEFAULT 8910,
    tunnel_status   VARCHAR(20)  DEFAULT 'closed' CHECK (tunnel_status IN ('open', 'closed', 'reconnecting', 'error')),
    tunnel_latency_ms INTEGER,
    last_heartbeat  TIMESTAMPTZ,
    events_relayed  BIGINT       NOT NULL DEFAULT 0,
    errors_count    BIGINT       NOT NULL DEFAULT 0,
    version         VARCHAR(50),
    metadata        JSONB        DEFAULT '{}',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_connectors_site_id ON neuranac_connectors(site_id);
CREATE INDEX IF NOT EXISTS idx_connectors_status ON neuranac_connectors(status);

-- ─── Node Registry ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS neuranac_node_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         UUID         NOT NULL REFERENCES neuranac_sites(id) ON DELETE CASCADE,
    node_name       VARCHAR(255) NOT NULL,
    role            VARCHAR(30)  NOT NULL DEFAULT 'worker' CHECK (role IN ('primary', 'secondary', 'worker', 'standby')),
    k8s_pod_name    VARCHAR(255),
    k8s_namespace   VARCHAR(255),
    service_type    VARCHAR(50),
    ip_address      VARCHAR(45),
    status          VARCHAR(20)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'draining', 'inactive', 'error')),
    active_sessions INTEGER      NOT NULL DEFAULT 0,
    cpu_pct         REAL         DEFAULT 0,
    mem_pct         REAL         DEFAULT 0,
    last_heartbeat  TIMESTAMPTZ,
    metadata        JSONB        DEFAULT '{}',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_node_registry_site_id ON neuranac_node_registry(site_id);
CREATE INDEX IF NOT EXISTS idx_node_registry_status ON neuranac_node_registry(status);
CREATE INDEX IF NOT EXISTS idx_node_registry_role ON neuranac_node_registry(role);

-- ─── Add site_id to existing tables ─────────────────────────────────────────

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES neuranac_sites(id);
ALTER TABLE network_devices ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES neuranac_sites(id);
ALTER TABLE sync_journal ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES neuranac_sites(id);

CREATE INDEX IF NOT EXISTS idx_sessions_site_id ON sessions(site_id);
CREATE INDEX IF NOT EXISTS idx_network_devices_site_id ON network_devices(site_id);
CREATE INDEX IF NOT EXISTS idx_sync_journal_site_id ON sync_journal(site_id);

-- ─── Update deployment_config FK now that neuranac_sites exists ──────────────────

ALTER TABLE neuranac_deployment_config
    ADD CONSTRAINT fk_deployment_primary_site
    FOREIGN KEY (primary_site_id) REFERENCES neuranac_sites(id);
